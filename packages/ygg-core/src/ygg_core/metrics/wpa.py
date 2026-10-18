"""WPA (win probability added) of each event a player takes part in.

Their team's win probability (WP) comes from a model trained on 4,276
EUW Challenger matches (research/ladder/REPORT.md): a logistic regression per stretch of
the game over the game state at that instant. The state only uses what was
known beforehand: gold and XP of the last closed minute (the timeline gives one frame per
minute) plus the gold of the events that have occurred since, and, exact by events,
kills, dead players, turrets by tier, fallen inhibitors, dragons, soul
point, soul, Baron, Elder, grubs and herald. Without that gold, the value of a turret
would arrive a minute late, with the next frame, and would not be attributed to anyone.

The value of an event is how much it moves its team's WP, but measured as if the
game were even (neutral WPA: the change in log-odds between 4, which at 50%
is the change in points). With the real WP, an already lost game crushes everything that
happens afterwards: dying at 10% WP subtracts 2 points and the same death at 50% subtracts 8, and
a 0/11 ended with the grade of a normal defeat. Plays count the same however you
are doing; the curve and the before → after of each event are still the real WP.

The value is split so that what is distributed adds up exactly to that of the event:

- kill: among those of their team who killed or assisted, in equal parts;
- death: entirely to the one who dies;
- own-team objective: half to those who took it, half to those who killed an
  enemy who was still dead (if there is only one of the two groups, all to that one);
- enemy objective: entirely to the teammates who were dead.

"Dead" runs from the moment of death to the respawn (wiki timer) plus 12 s of
walking back from base. The grade compares the total value with that of the Challengers of the same
role on the same scale as the stats grade (match_score): their 10th,
35th, 50th, 65th and 90th percentiles are worth 40, 55, 62.5, 70 and 85, with the percentiles taken from their mean and
their standard deviation (normal distribution). 70 is better than two out of three Challenger
matches of the role; the mean, 62.5.
"""

from __future__ import annotations

import bisect
import math
from dataclasses import dataclass
from statistics import NormalDist
from typing import Any, TypedDict

from ygg_core.domain.roles import role_from_position
from ygg_core.metrics.match_score import metric_score

JsonDict = dict[str, Any]

PHASES = (0, 10, 15, 20, 25, 30, 35)  # one model per stretch of minutes
RESPAWN_MARGIN_MS = 12_000  # walking back from base after the respawn
# Gold per second that a Challenger of each role earns in the mid phase (economy.py, ideal curve): for the
# note of "how much you lost dead". ponytail: a constant per role, a range absorbs its variation with the minute.
GOLD_PER_SEC = {"TOP": 8.0, "JUNGLE": 8.5, "MID": 8.5, "ADC": 10.0, "SUPPORT": 5.5}
# The 10th, 35th, 50th, 65th and 90th percentiles of a normal, in standard deviations: the anchors of the grade.
GRADE_Z: tuple[float, ...] = tuple(NormalDist().inv_cdf(p / 100) for p in (10, 35, 50, 65, 90))

# Events that give gold. How much (WinModel.event_gold) is measured with the gold jump
# between frames. KILL and SHUTDOWN are multipliers of their reward: the kill distributes
# assist gold (≈ 1.7 times) and the shutdown is collected almost only by whoever kills (≈ 1.0).
GOLD_EVENTS = (
    "KILL", "SHUTDOWN", "PLATE", "TOWER_OUTER", "TOWER_INNER", "TOWER_BASE", "TOWER_NEXUS", "INHIBITOR",
    "DRAGON", "ELDER", "BARON_NASHOR", "RIFTHERALD", "HORDE",
)

FEATURES = (
    "gold_k", "xp_k", "kills", "dead", "outer_turrets", "inner_turrets", "base_turrets",
    "nexus_turrets", "inhibitors_down", "dragons", "soul_point", "soul", "baron_active",
    "elder_active", "grubs", "herald", "minute",
)

# Death timer (wiki): BRW per level and increase per game minute, capped at 50%.
_BRW = (10, 10, 12, 12, 14, 16, 20, 25, 28, 32.5, 35, 37.5, 40, 42.5, 45, 47.5, 50, 52.5)


def respawn_seconds(level: int, minute: float) -> float:
    if minute < 15:
        tif = 0.0
    elif minute < 30:
        tif = math.ceil(2 * (minute - 15)) * 0.425
    elif minute < 45:
        tif = 12.75 + math.ceil(2 * (minute - 30)) * 0.30
    else:
        tif = 21.75 + math.ceil(2 * (minute - 45)) * 1.45
    return _BRW[max(1, min(18, level)) - 1] * (1 + min(tif, 50) / 100)


@dataclass(frozen=True, slots=True)
class WinModel:
    # Per stretch of PHASES: intercept and one weight per FEATURES feature.
    coefficients: tuple[tuple[float, ...], ...]
    # Gold that each GOLD_EVENTS event gives to the team that gets it.
    event_gold: dict[str, float]
    # Role → (mean, standard deviation) of the Challengers' total WPA per match.
    reference: dict[str, tuple[float, float]]


class WpaDriver(TypedDict):
    """Which part of the state changed with the event and how many points of its value it explains."""

    factor: str  # a FEATURES feature
    change: float  # how much it changed in favour of their team (gold and XP, in units, not in thousands)
    wpa: float  # points of the event's value that it explains


class WpaEvent(TypedDict):
    time: int  # seconds
    # KILL · ASSIST · DEATH · OBJECTIVE · OBJECTIVE_AFTER_KILL · CONCEDED_WHILE_DEAD
    kind: str
    target: str  # champion (the victim, or whoever killed them in DEATH) or objective (BARON_NASHOR, TOWER_OUTER_MID…)
    wp_before: float  # their team's WP, 0-100
    wp_after: float
    wpa: float  # points attributed to the player = team_wpa · share
    team_wpa: float  # value of the event for their team: WP points as if the game were even
    share: float  # the part attributed to them, 0-1
    shared_with: int  # among how many players it is split (them included)
    drivers: list[WpaDriver]  # why the WP changed: the features that weigh most, from highest to lowest
    bounty: int  # gold of the kill, without shutdown (0 on objectives)
    shutdown: int  # gold of the shutdown that was collected or given
    gold_lost: list[int]  # only on DEATH: [gold you stopped earning with the respawn, with respawn + walk back to the lane]


@dataclass(frozen=True, slots=True)
class WpaReport:
    events: list[WpaEvent]
    wp_curve: list[float]  # their team's WP at each minute, 0-100
    total: float
    grade: int | None  # None if their role has no reference


@dataclass(frozen=True, slots=True)
class _Objective:
    time: int
    team: int  # whoever takes it
    kind: str  # DRAGON_1…4 (per team) · ELDER · BARON_NASHOR · RIFTHERALD · HORDE · TOWER_OUTER_MID… · INHIBITOR
    takers: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class _Death:
    time: int
    end: int  # respawn
    team: int
    victim: int
    killers: tuple[int, ...]  # whoever killed and assistants, enemy champions only


def _phase(minute: float) -> int:
    return bisect.bisect_right(PHASES, minute) - 1


class GameState:
    """State of a match at any instant, without looking into the future, from Riot's payload."""

    def __init__(self, match_data: JsonDict, timeline: JsonDict) -> None:
        info = match_data["info"]
        self.participants: dict[int, JsonDict] = {int(p["participantId"]): p for p in info["participants"]}
        self.team_of: dict[int, int] = {pid: int(p["teamId"]) for pid, p in self.participants.items()}
        self.duration_ms = int(info.get("gameDuration", 0)) * 1000

        frames: list[JsonDict] = sorted(timeline.get("info", {}).get("frames", []), key=lambda f: f.get("timestamp", 0))
        self._gold: list[float] = []
        self._xp: list[float] = []
        self._levels: list[dict[int, int]] = []
        self._frame_times = [int(f.get("timestamp", 0)) for f in frames]
        for frame in frames:
            gold = xp = 0.0
            levels: dict[int, int] = {}
            for key, data in (frame.get("participantFrames") or {}).items():
                pid = int(key)
                sign = 1 if self.team_of.get(pid) == 100 else -1
                gold += sign * data.get("totalGold", 0)
                xp += sign * data.get("xp", 0)
                levels[pid] = int(data.get("level", 1))
            self._gold.append(gold)
            self._xp.append(xp)
            self._levels.append(levels)

        events = sorted((e for f in frames for e in f.get("events", [])), key=lambda e: e.get("timestamp", 0))
        self.kills: list[JsonDict] = [e for e in events if e.get("type") == "CHAMPION_KILL"]
        self.objectives = self._read_objectives(events)
        self._kill_times = [int(k.get("timestamp", 0)) for k in self.kills]
        balance = [0]
        for k in self.kills:
            balance.append(balance[-1] + (1 if self.team_of.get(k.get("victimId", 0)) == 200 else -1))
        self._kill_balance = balance
        self._gold_events = self._read_gold_events(events)
        self._gold_event_times = [g[0] for g in self._gold_events]
        self.deaths: list[_Death] = []
        for k in self.kills:
            victim, t = int(k.get("victimId", 0)), int(k.get("timestamp", 0))
            if victim not in self.team_of:
                continue
            timer = respawn_seconds(self.level_at(victim, t), t / 60_000)
            killers = tuple(
                i for i in (k.get("killerId", 0), *(k.get("assistingParticipantIds") or []))
                if self.team_of.get(i, self.team_of[victim]) != self.team_of[victim]
            )
            self.deaths.append(_Death(t, t + int(timer * 1000), self.team_of[victim], victim, killers))

    def _read_gold_events(self, events: list[JsonDict]) -> list[tuple[int, float, str, float]]:
        """(time, +1 if collected by blue or -1 by red, GOLD_EVENTS type, base amount)."""
        out: list[tuple[int, float, str, float]] = []
        for e in events:
            t, kind, team, amount = int(e.get("timestamp", 0)), "", 0, 1.0
            if e.get("type") == "CHAMPION_KILL" and e.get("killerId") in self.team_of:
                kind, team = "KILL", self.team_of[e["killerId"]]
                amount = float(e.get("bounty", 0))
                if e.get("shutdownBounty"):
                    out.append((t, 1.0 if team == 100 else -1.0, "SHUTDOWN", float(e["shutdownBounty"])))
            elif e.get("type") == "TURRET_PLATE_DESTROYED" and e.get("teamId") in (100, 200):
                kind, team = "PLATE", 300 - int(e["teamId"])
            elif e.get("type") == "BUILDING_KILL" and e.get("teamId") in (100, 200):
                team = 300 - int(e["teamId"])
                tower = str(e.get("towerType") or "").replace("_TURRET", "")
                kind = "INHIBITOR" if e.get("buildingType") == "INHIBITOR_BUILDING" else f"TOWER_{tower}"
            elif e.get("type") == "ELITE_MONSTER_KILL":
                team = int(e.get("killerTeamId") or 0)
                kind = "ELDER" if e.get("monsterSubType") == "ELDER_DRAGON" else str(e.get("monsterType", ""))
            if kind in GOLD_EVENTS and team in (100, 200):
                out.append((t, 1.0 if team == 100 else -1.0, kind, amount))
        return out

    def gold_intervals(self) -> list[tuple[dict[str, float], float]]:
        """For each minute: gold events (signed, by type) and the blue - red gold jump until the next frame."""
        out = []
        for m in range(len(self._gold) - 1):
            start, end = self._frame_times[m], self._frame_times[m + 1]
            counts: dict[str, float] = {}
            for t, sign, kind, amount in self._gold_events:
                if start < t <= end:
                    counts[kind] = counts.get(kind, 0.0) + sign * amount
            out.append((counts, self._gold[m + 1] - self._gold[m]))
        return out

    def _read_objectives(self, events: list[JsonDict]) -> list[_Objective]:
        out: list[_Objective] = []
        dragons = {100: 0, 200: 0}
        for e in events:
            t = int(e.get("timestamp", 0))
            ids = [i for i in (e.get("killerId", 0), *(e.get("assistingParticipantIds") or [])) if i in self.team_of]
            if e.get("type") == "ELITE_MONSTER_KILL":
                team = int(e.get("killerTeamId") or self.team_of.get(e.get("killerId", 0), 0))
                monster = str(e.get("monsterType", ""))
                if monster == "DRAGON" and e.get("monsterSubType") == "ELDER_DRAGON":
                    kind = "ELDER"
                elif monster == "DRAGON":
                    dragons[team] = dragons.get(team, 0) + 1
                    kind = f"DRAGON_{min(dragons[team], 4)}"
                else:
                    kind = monster
            elif e.get("type") == "BUILDING_KILL":
                owner = e.get("teamId")
                team = 300 - owner if owner in (100, 200) else 0
                if e.get("buildingType") == "INHIBITOR_BUILDING":
                    kind = "INHIBITOR"
                else:
                    tower = str(e.get("towerType") or "").replace("_TURRET", "")
                    lane = str(e.get("laneType") or "").replace("_LANE", "")
                    kind = f"TOWER_{tower}_{lane}" if tower in ("OUTER", "INNER") else f"TOWER_{tower}"
            else:
                continue
            out.append(_Objective(t, team, kind, tuple(i for i in ids if self.team_of[i] == team)))
        return out

    @property
    def has_frames(self) -> bool:
        return bool(self._gold)

    def level_at(self, pid: int, t: float) -> int:
        if not self._levels:
            return 1
        return self._levels[min(int(t // 60_000), len(self._levels) - 1)].get(pid, 1)

    def dead_at(self, team: int, t: float) -> int:
        return sum(1 for d in self.deaths if d.team == team and d.time < t < d.end)

    def features(self, t: float, event_gold: dict[str, float]) -> list[float]:
        """Model features from blue at t (red is the same with the sign changed, except for the minute)."""
        frame = min(bisect.bisect_right(self._frame_times, t) - 1, len(self._gold) - 1) if self._gold else -1
        gold = self._gold[frame] if frame >= 0 else 0.0
        if frame >= 0:
            first = bisect.bisect_right(self._gold_event_times, self._frame_times[frame])
            for _when, sign, kind, amount in self._gold_events[first:bisect.bisect_left(self._gold_event_times, t)]:
                gold += sign * event_gold.get(kind, 0.0) * amount
        xp = self._xp[frame] if frame >= 0 else 0.0
        kills = float(self._kill_balance[bisect.bisect_left(self._kill_times, t)])
        dead = float(self.dead_at(200, t) - self.dead_at(100, t))
        towers = {"OUTER": 0.0, "INNER": 0.0, "BASE": 0.0, "NEXUS": 0.0}
        inhibs = dragons = soul = baron = elder = grubs = herald = 0.0
        count = {100: 0, 200: 0}
        soul_given = False
        for o in self.objectives:
            if o.time >= t:
                break
            sign = 1.0 if o.team == 100 else -1.0 if o.team == 200 else 0.0
            age = t - o.time
            if o.kind.startswith("TOWER"):
                tier = o.kind.split("_")[1]
                if tier in towers:
                    towers[tier] += sign
            elif o.kind == "INHIBITOR" and age < 300_000:
                inhibs += sign
            elif o.kind.startswith("DRAGON"):
                dragons += sign
                count[o.team] = count.get(o.team, 0) + 1
                if o.kind == "DRAGON_4":
                    soul += sign
                    soul_given = True
            elif o.kind == "BARON_NASHOR" and age < 180_000:
                baron += sign
            elif o.kind == "ELDER" and age < 150_000:
                elder += sign
            elif o.kind == "HORDE":
                grubs += sign
            elif o.kind == "RIFTHERALD":
                herald += sign
        soul_point = 0.0 if soul_given else float(count[100] == 3) - float(count[200] == 3)
        return [
            gold / 1000, xp / 1000, kills, dead, towers["OUTER"], towers["INNER"], towers["BASE"],
            towers["NEXUS"], inhibs, dragons, soul_point, soul, baron, elder, grubs, herald, t / 60_000,
        ]


def blue_log_odds(features: list[float], model: WinModel) -> float:
    weights = model.coefficients[_phase(features[-1])]
    z = weights[0] + sum(w * x for w, x in zip(weights[1:], features, strict=True))
    return max(-30.0, min(30.0, z))


def blue_win_probability(features: list[float], model: WinModel) -> float:
    return 1 / (1 + math.exp(-blue_log_odds(features, model)))


def team_win_probability(state: GameState, team: int, t: float, model: WinModel) -> float:
    p = blue_win_probability(state.features(t, model.event_gold), model)
    return p if team == 100 else 1 - p


def _drivers(before: list[float], after: list[float], team: int, value: float, model: WinModel) -> list[WpaDriver]:
    """Distributes the event's value among the features that changed, according to what each weighs in the model."""
    weights = model.coefficients[_phase(after[-1])][1:]
    parts = [w * (a - b) for w, a, b in zip(weights, after, before, strict=True)]
    total = sum(parts)
    if abs(total) < 1e-9:
        return []
    sign = 1.0 if team == 100 else -1.0
    drivers = [
        WpaDriver(
            factor=FEATURES[i],
            change=round(sign * (after[i] - before[i]) * (1000 if FEATURES[i] in ("gold_k", "xp_k") else 1), 1),
            wpa=round(100 * value * part / total, 2),
        )
        for i, part in enumerate(parts)
        if FEATURES[i] != "minute" and abs(100 * value * part / total) >= 0.05
    ]
    return sorted(drivers, key=lambda d: -abs(d["wpa"]))[:3]


def _champion(state: GameState, pid: int) -> str:
    return str(state.participants.get(pid, {}).get("championName") or "")


def wpa_report(match_data: JsonDict, timeline: JsonDict, puuid: str, model: WinModel) -> WpaReport | None:
    """The player's events with their WPA, their team's WP curve and the grade. None if they are not in the match."""
    state = GameState(match_data, timeline)
    me = next((pid for pid, p in state.participants.items() if p.get("puuid") == puuid), None)
    if me is None or not state.has_frames:
        return None
    team = state.team_of[me]
    my_role = role_from_position(state.participants[me].get("teamPosition"))

    def wp(t: float) -> float:
        return team_win_probability(state, team, t, model)

    def dead_window(d: _Death, t: int) -> bool:
        return d.time < t <= d.end + RESPAWN_MARGIN_MS

    # Kills and objectives at the same time (same millisecond) share the WP change in equal parts.
    plays: dict[int, list[JsonDict | _Objective]] = {}
    for k in state.kills:
        plays.setdefault(int(k.get("timestamp", 0)), []).append(k)
    for o in state.objectives:
        plays.setdefault(o.time, []).append(o)

    events: list[WpaEvent] = []
    Context = tuple[int, float, float, float, list[WpaDriver]]  # instant, WP before, WP after, value, why

    def add(ctx: Context, kind: str, target: str, wpa: float, shared_with: int, kill: JsonDict | None = None) -> None:
        t, before, after, value, drivers = ctx
        gold_lost = [0, 0]
        if kind == "DEATH":  # gold you stop earning dead: from the respawn alone to respawn + walk back to the lane
            rate = GOLD_PER_SEC.get(my_role, 8.0)
            respawn = respawn_seconds(state.level_at(me, t), t / 60_000)
            gold_lost = [round(rate * respawn / 10) * 10, round(rate * (respawn + RESPAWN_MARGIN_MS / 1000) / 10) * 10]
        events.append(WpaEvent(
            time=t // 1000, kind=kind, target=target, wp_before=round(100 * before, 1),
            wp_after=round(100 * after, 1), wpa=round(100 * wpa, 2), team_wpa=round(100 * value, 2),
            share=round(wpa / value, 3) if value else 0.0, shared_with=shared_with, drivers=drivers,
            bounty=int((kill or {}).get("bounty", 0)), shutdown=int((kill or {}).get("shutdownBounty", 0)),
            gold_lost=gold_lost,
        ))

    sign = 1.0 if team == 100 else -1.0
    for t in sorted(plays):
        x_before, x_after = state.features(t - 1, model.event_gold), state.features(t + 1, model.event_gold)
        z_before, z_after = sign * blue_log_odds(x_before, model), sign * blue_log_odds(x_after, model)
        before, after = 1 / (1 + math.exp(-z_before)), 1 / (1 + math.exp(-z_after))
        # Neutral: the change in log-odds at 50% WP, where one log-odds point is 25 of WP.
        value = (z_after - z_before) / 4 / len(plays[t])
        ctx: Context = (t, before, after, value, _drivers(x_before, x_after, team, value, model))
        for play in plays[t]:
            if isinstance(play, _Objective):
                if play.team not in (100, 200):
                    continue
                if play.team == team:
                    enabling = [d for d in state.deaths if d.team != team and d.killers and dead_window(d, t)]
                    split = (0.5, 0.5) if play.takers and enabling else (1.0, 0.0) if play.takers else (0.0, 1.0)
                    if me in play.takers:
                        add(ctx, "OBJECTIVE", play.kind, value * split[0] / len(play.takers), len(play.takers))
                    credit = sum(value * split[1] / len(enabling) / len(d.killers) for d in enabling if me in d.killers)
                    if credit:
                        add(ctx, "OBJECTIVE_AFTER_KILL", play.kind, credit, len({i for d in enabling for i in d.killers}))
                else:
                    dead = [d for d in state.deaths if d.team == team and dead_window(d, t)]
                    if any(d.victim == me for d in dead):
                        add(ctx, "CONCEDED_WHILE_DEAD", play.kind, value / len(dead), len(dead))
                continue
            victim = int(play.get("victimId", 0))
            if victim == me:
                add(ctx, "DEATH", _champion(state, int(play.get("killerId", 0))), value, 1, play)
            elif state.team_of.get(victim) != team:
                credited = [i for i in (play.get("killerId", 0), *(play.get("assistingParticipantIds") or []))
                            if state.team_of.get(i) == team]
                if me in credited:
                    kind = "KILL" if play.get("killerId") == me else "ASSIST"
                    add(ctx, kind, _champion(state, victim), value / len(credited), len(credited), play)

    total = round(sum(e["wpa"] for e in events), 2)
    minutes = max(1, state.duration_ms // 60_000)
    curve = [round(100 * wp(m * 60_000), 1) for m in range(minutes + 1)]
    grade = None
    if my_role in model.reference:
        mean, sd = model.reference[my_role]
        p10, p35, p50, p65, p90 = (mean + z * sd for z in GRADE_Z)
        grade = max(0, min(100, round(metric_score("wpa", total, (p10, p35, p50, p65, p90)))))
    return WpaReport(events=events, wp_curve=curve, total=total, grade=grade)
