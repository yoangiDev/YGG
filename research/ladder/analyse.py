"""What makes the best players of each role win, measured with WPA (win probability added).

    python research/ladder/analyse.py research/ladder/data

Writes data/findings.json (the report's numbers) and data/dataset.json (everything
computed, accessible). Uses numpy only.

A winrate mixes two things: the effect of a decision and the selection bias of
when it is taken (Mejai is bought when ahead; an inhibitor is taken
when ahead). WPA separates them:

    WPA = winrate - average WP just before the decision

where WP is the win probability given by a model calibrated with the game state
at that instant. The prior WP is the bias; what remains is the average
effect. Here the decisions are dying, killing and taking an objective.

The model only sees what was known before the event: gold and XP of the last closed
minute (the timeline gives one frame per minute; interpolating would put the event's own
gold into the baseline) and, exact by events, kills, players dead at that
instant, turrets by tier, fallen inhibitors, dragons, soul point, soul,
Baron, Elder, grubs, herald and draft strength. It is validated with
calibration by phase and with a placebo: the nexus turrets barely change the
result, so their WPA has to come out near 0.
"""

from __future__ import annotations

import bisect
import gzip
import json
import math
import sys
import zlib
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Any

import numpy as np
from ygg_core.timeline.map_zones import lane_at
from ygg_core.timeline.objectives import OBJECTIVE_PIT_POSITIONS

ROLES = ("TOP", "JUNGLE", "MID", "ADC", "SUPPORT")
PIT_RADIUS = 2500
LANE_OF_ROLE = {"TOP": "TOP_LANE", "MID": "MID_LANE", "ADC": "BOT_LANE", "SUPPORT": "BOT_LANE"}
FIGHT_WINDOW_MS = 15_000
LANE_MINUTE = 14
RESPAWN_MARGIN_S = 12  # walking back from base after the respawn
SAMPLE_EVERY_MS = 30_000  # training states of the win model
PHASES = (0, 10, 15, 20, 25, 30, 35)  # one model per stretch: what a lead is worth changes with the minute
DRAFT_PRIOR_GAMES = 30  # shrinks each champion's winrate toward 50%

# Death timer (wiki): BRW per level and increase per game minute, capped at 50%.
BRW = [10, 10, 12, 12, 14, 16, 20, 25, 28, 32.5, 35, 37.5, 40, 42.5, 45, 47.5, 50, 52.5]


def respawn_seconds(level: int, minute: float) -> float:
    if minute < 15:
        tif = 0.0
    elif minute < 30:
        tif = math.ceil(2 * (minute - 15)) * 0.425
    elif minute < 45:
        tif = 12.75 + math.ceil(2 * (minute - 30)) * 0.30
    else:
        tif = 21.75 + math.ceil(2 * (minute - 45)) * 1.45
    return BRW[max(1, min(18, level)) - 1] * (1 + min(tif, 50) / 100)


# ── Statistics with numpy ─────────────────────────────────────────────────────


def logistic_fit(x: np.ndarray, y: np.ndarray, l2: float = 1.0, iterations: int = 30) -> np.ndarray:
    """Logistic regression by Newton with L2 (not penalising the intercept)."""
    design = np.column_stack([np.ones(len(x)), x])
    w = np.zeros(design.shape[1])
    penalty = l2 * np.diag(np.r_[0.0, np.ones(design.shape[1] - 1)])
    for _ in range(iterations):
        p = 1 / (1 + np.exp(-np.clip(design @ w, -30, 30)))
        gradient = design.T @ (p - y) + penalty @ w
        hessian = (design * (p * (1 - p))[:, None]).T @ design + penalty
        w -= np.linalg.solve(hessian, gradient)
    return w


def logistic_predict(w: np.ndarray, x: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-np.clip(w[0] + x @ w[1:], -30, 30)))


def average_ranks(values: np.ndarray) -> np.ndarray:
    _, inverse, counts = np.unique(values, return_inverse=True, return_counts=True)
    end = np.cumsum(counts)
    return ((end - counts + 1 + end) / 2)[inverse]


def auc(score: np.ndarray, y: np.ndarray) -> float:
    """Probability that a win scores higher than a loss (0.5 = doesn't separate)."""
    positives = y.sum()
    negatives = len(y) - positives
    if not positives or not negatives:
        return float("nan")
    ranks = average_ranks(score)
    return float((ranks[y == 1].sum() - positives * (positives + 1) / 2) / (positives * negatives))


def corr(a: np.ndarray, b: np.ndarray) -> float:
    if a.std() == 0 or b.std() == 0:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def folds(keys: list[str], k: int = 5) -> np.ndarray:
    """Validation fold per match: the same match is never in both training and test."""
    return np.array([zlib.crc32(key.encode()) % k for key in keys])


def phase_of(minute: float) -> int:
    return bisect.bisect_right(PHASES, minute) - 1


def wpa_summary(pairs: list[tuple[float, float]]) -> dict[str, float]:
    """(won, prior WP) → winrate, mean prior WP, WPA and its standard error, in points."""
    won = np.array([p[0] for p in pairs])
    before = np.array([p[1] for p in pairs])
    delta = won - before
    return {
        "n": len(pairs),
        "winrate": round(100 * float(won.mean()), 1),
        "wp_previous": round(100 * float(before.mean()), 1),
        "wpa": round(100 * float(delta.mean()), 2),
        "error": round(100 * float(delta.std() / math.sqrt(len(delta))), 2),
    }


# ── Loading ────────────────────────────────────────────────────────────────────


def load(data: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    players = json.loads((data / "players.json").read_text(encoding="utf-8"))
    matches: dict[str, Any] = {}
    try:
        with gzip.open(data / "matches.jsonl.gz", "rt", encoding="utf-8") as fh:
            for line in fh:
                record = json.loads(line)
                if record.get("frames") and not record.get("remake"):
                    matches[record["match_id"]] = record
    except (EOFError, OSError, json.JSONDecodeError):
        pass  # the download is still writing: the last line may be half-written
    return players, matches


# ── Match and leak-free state ─────────────────────────────────────────────────

WP_FEATURES = [
    "gold_k", "xp_k", "kills", "dead", "outer_turrets", "inner_turrets", "base_turrets",
    "nexus_turrets", "inhibitors_down", "dragons", "soul_point", "soul", "baron_active",
    "elder_active", "grubs", "herald", "draft", "minute",
]


class Match:
    """A match with the game state at any instant, without looking into the future."""

    def __init__(self, record: dict[str, Any]) -> None:
        self.id = record["match_id"]
        self.version = ".".join((record.get("game_version") or "").split(".")[:2])
        self.duration = record["duration"]
        self.participants = {p["participantId"]: p for p in record["participants"]}
        self.team_of = {pid: p["teamId"] for pid, p in self.participants.items()}
        self.winner = next(t["teamId"] for t in record["teams"] if t["win"])
        self.frames = {int(pid): np.array(rows, dtype=float) for pid, rows in record["frames"].items()}
        self.events = sorted(record["events"], key=lambda e: e.get("timestamp", 0))
        self.kills = [e for e in self.events if e["type"] == "CHAMPION_KILL"]
        self.objectives = self._objectives()
        self.draft = 0.0  # blue's draft advantage, set by set_draft_prior

        # Blue's gold and XP minus red's at each frame (one frame per minute).
        frames = min(len(rows) for rows in self.frames.values())
        sign = {pid: 1 if team == 100 else -1 for pid, team in self.team_of.items()}
        self.gold_diff = np.zeros(frames)
        self.xp_diff = np.zeros(frames)
        for pid, rows in self.frames.items():
            self.gold_diff += sign.get(pid, 0) * rows[:frames, 1]
            self.xp_diff += sign.get(pid, 0) * rows[:frames, 2]

        # Accumulated kills (blue - red) and who is dead from when to when.
        self.kill_times = [k.get("timestamp", 0) for k in self.kills]
        self.kill_balance = np.cumsum([0] + [
            1 if self.team_of.get(k.get("victimId")) == 200 else -1 for k in self.kills
        ])
        self.dead_spans = []
        for k in self.kills:
            t, victim = k.get("timestamp", 0), k.get("victimId")
            if victim in self.team_of:
                timer = respawn_seconds(self.level_at(victim, t), t / 60_000)
                self.dead_spans.append((t, t + timer * 1000, self.team_of[victim], victim))

    def _objectives(self) -> list[dict[str, Any]]:
        """Objectives in order: who, what, when and who took part (dragons numbered per team)."""
        out: list[dict[str, Any]] = []
        dragons: dict[int, int] = defaultdict(int)
        for e in self.events:
            t = e.get("timestamp", 0)
            ids = [i for i in [e.get("killerId"), *(e.get("assistingParticipantIds") or [])] if i in self.team_of]
            if e["type"] == "ELITE_MONSTER_KILL":
                team = e.get("killerTeamId") or self.team_of.get(e.get("killerId"), 0)
                monster = e.get("monsterType")
                if monster == "DRAGON" and e.get("monsterSubType") == "ELDER_DRAGON":
                    kind = "ELDER"
                elif monster == "DRAGON":
                    dragons[team] += 1
                    kind = f"DRAGON_{min(dragons[team], 4)}"
                else:
                    kind = monster  # BARON_NASHOR · RIFTHERALD · HORDE · ATAKHAN
                out.append({"t": t, "team": team, "kind": kind, "ids": [i for i in ids if self.team_of.get(i) == team]})
            elif e["type"] == "BUILDING_KILL":
                owner = e.get("teamId")
                taker = 300 - owner if owner in (100, 200) else 0
                if e.get("buildingType") == "INHIBITOR_BUILDING":
                    kind = "INHIBITOR"
                else:
                    tower = (e.get("towerType") or "").replace("_TURRET", "")
                    lane = (e.get("laneType") or "").replace("_LANE", "")
                    kind = f"TOWER_{tower}_{lane}" if tower in ("OUTER", "INNER") else f"TOWER_{tower}"
                out.append({"t": t, "team": taker, "kind": kind, "ids": [i for i in ids if self.team_of.get(i) == taker]})
        return out

    def level_at(self, pid: int, t: float) -> int:
        rows = self.frames.get(pid)
        if rows is None or not len(rows):
            return 1
        return int(rows[min(int(t // 60_000), len(rows) - 1), 3])

    def dead_at(self, team: int, t: float, exclude: int | None = None) -> int:
        return sum(1 for start, end, who, pid in self.dead_spans if who == team and start < t < end and pid != exclude)

    def state(self, t: float) -> np.ndarray:
        """Win model features from blue at t, using only what happened before t."""
        frame = min(int(t // 60_000), len(self.gold_diff) - 1)
        kills = self.kill_balance[bisect.bisect_left(self.kill_times, t)]
        dead = self.dead_at(200, t) - self.dead_at(100, t)
        towers = defaultdict(float)
        inhibs = dragons = soul = baron = elder = grubs = herald = 0.0
        count = {100: 0, 200: 0}
        soul_given = False
        for o in self.objectives:
            if o["t"] >= t:
                break
            sign = 1 if o["team"] == 100 else -1 if o["team"] == 200 else 0
            kind, age = o["kind"], t - o["t"]
            if kind.startswith("TOWER"):
                towers[kind.split("_")[1]] += sign  # OUTER · INNER · BASE · NEXUS
            elif kind == "INHIBITOR" and age < 300_000:
                inhibs += sign
            elif kind.startswith("DRAGON"):
                dragons += sign
                count[o["team"]] = count.get(o["team"], 0) + 1
                if kind == "DRAGON_4":
                    soul += sign
                    soul_given = True
            elif kind == "BARON_NASHOR" and age < 180_000:
                baron += sign
            elif kind == "ELDER" and age < 150_000:
                elder += sign
            elif kind == "HORDE":
                grubs += sign
            elif kind == "RIFTHERALD":
                herald += sign
        soul_point = 0.0 if soul_given else float(count[100] == 3) - float(count[200] == 3)
        return np.array([
            self.gold_diff[frame] / 1000, self.xp_diff[frame] / 1000, kills, dead,
            towers["OUTER"], towers["INNER"], towers["BASE"], towers["NEXUS"], inhibs,
            dragons, soul_point, soul, baron, elder, grubs, herald, self.draft, t / 60_000,
        ])


def mirror(x: np.ndarray) -> np.ndarray:
    """The same state seen from red: everything changes sign except the minute."""
    y = -x
    y[-1] = x[-1]
    return y


def set_draft_prior(matches: list[Match]) -> None:
    """Draft advantage: each champion's winrate in the sample not counting this match, shrunk toward 50%."""
    wins: dict[str, float] = defaultdict(float)
    games: dict[str, float] = defaultdict(float)
    for m in matches:
        for p in m.participants.values():
            games[p["championName"]] += 1
            wins[p["championName"]] += p["teamId"] == m.winner
    k = DRAFT_PRIOR_GAMES
    for m in matches:
        advantage = 0.0
        for p in m.participants.values():
            champion, won = p["championName"], p["teamId"] == m.winner
            rate = (wins[champion] - won + 0.5 * k) / (games[champion] - 1 + k)
            advantage += (rate - 0.5) * (1 if p["teamId"] == 100 else -1)
        m.draft = advantage


class WinModel:
    def __init__(self, weights: list[np.ndarray]) -> None:
        self.w = weights  # one logistic regression per PHASES stretch

    def blue_from_state(self, x: np.ndarray) -> float:
        return float(logistic_predict(self.w[phase_of(x[-1])], x[None, :])[0])

    def team(self, match: Match, team: int, t: float) -> float:
        p = self.blue_from_state(match.state(t))
        return p if team == 100 else 1 - p

    def team_from_state(self, x: np.ndarray, team: int) -> float:
        p = self.blue_from_state(x)
        return p if team == 100 else 1 - p


def fit_win_model(matches: list[Match]) -> tuple[WinModel, dict[str, Any]]:
    """One logistic regression per stretch of the game, over states every 30 s seen from both teams."""
    rows, labels, keys = [], [], []
    for m in matches:
        blue_won = 1.0 if m.winner == 100 else 0.0
        for t in range(60_000, int(m.duration * 1000), SAMPLE_EVERY_MS):
            x = m.state(t)
            rows += [x, mirror(x)]
            labels += [blue_won, 1 - blue_won]
            keys += [m.id, m.id]
    x, y = np.array(rows), np.array(labels)
    phase = np.array([phase_of(minute) for minute in x[:, -1]])
    fold = folds(keys)
    held_out = np.zeros(len(y))
    for k in range(5):
        for p in range(len(PHASES)):
            train, test = (fold != k) & (phase == p), (fold == k) & (phase == p)
            if test.any():
                held_out[test] = logistic_predict(logistic_fit(x[train], y[train]), x[test])
    weights = [logistic_fit(x[phase == p], y[phase == p]) for p in range(len(PHASES))]

    # Calibration: in each decile of predicted WP, how much was really won.
    bins = np.minimum((held_out * 10).astype(int), 9)
    calibration = [
        {"prediction": round(100 * float(held_out[bins == b].mean()), 1),
         "real": round(100 * float(y[bins == b].mean()), 1), "n": int((bins == b).sum())}
        for b in range(10) if (bins == b).any()
    ]
    ece = sum(abs(c["prediction"] - c["real"]) * c["n"] for c in calibration) / len(y)
    by_phase = {}
    for p, start in enumerate(PHASES):
        mask = phase == p
        pb = np.minimum((held_out[mask] * 10).astype(int), 9)
        err = sum(abs(held_out[mask][pb == b].mean() - y[mask][pb == b].mean()) * (pb == b).sum() for b in range(10) if (pb == b).any())
        label = f"{start}-{PHASES[p + 1]}" if p + 1 < len(PHASES) else f"{start}+"
        by_phase[label] = {"auc": round(auc(held_out[mask], y[mask]), 3), "calibration_error_pp": round(100 * err / mask.sum(), 2)}
    quality = {
        "states": len(y) // 2,
        "auc": round(auc(held_out, y), 3),
        "log_loss": round(float(-np.mean(y * np.log(held_out + 1e-9) + (1 - y) * np.log(1 - held_out + 1e-9))), 4),
        "brier": round(float(np.mean((held_out - y) ** 2)), 4),
        "calibration_error_pp": round(ece, 2),
        "calibration": calibration,
        "by_stretch": by_phase,
        "coefficients_per_stretch": {
            (f"{s}-{PHASES[i + 1]}" if i + 1 < len(PHASES) else f"{s}+"): dict(
                zip(["intercept", *WP_FEATURES], (round(float(v), 4) for v in weights[i]), strict=True)
            )
            for i, s in enumerate(PHASES)
        },
    }
    return WinModel(weights), quality


# ── WPA of the objectives ─────────────────────────────────────────────────────


def objective_wpa(matches: list[Match], model: WinModel) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """WPA of taking each objective: winrate of whoever takes it - their WP just before."""
    groups: dict[str, list[tuple[float, float]]] = defaultdict(list)
    mid_outer: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for m in matches:
        for o in m.objectives:
            if o["team"] not in (100, 200):
                continue
            pair = (1.0 if m.winner == o["team"] else 0.0, model.team(m, o["team"], o["t"] - 1))
            groups[o["kind"]].append(pair)
            if o["kind"] == "TOWER_OUTER_MID":
                minute = o["t"] / 60_000
                mid_outer["before 12" if minute < 12 else "12-16" if minute < 16 else "16-20" if minute < 20 else "20+"].append(pair)
    table = [{"objective": kind, **wpa_summary(pairs)} for kind, pairs in groups.items() if len(pairs) >= 30]
    table.sort(key=lambda row: -row["wpa"])
    return table, {bucket: wpa_summary(pairs) for bucket, pairs in sorted(mid_outer.items())}


# ── Deaths ────────────────────────────────────────────────────────────────────


def zone(x: float, y: float, team: int) -> str:
    """Where they died, from their team's side: base, their half, river, enemy half; and whether in a lane."""
    side = (x + y - 14_700) * (1 if team == 100 else -1)  # > 0 = toward the enemy base
    if (team == 100 and x < 3000 and y < 3000) or (team == 200 and x > 12_000 and y > 12_000):
        half = "own base"
    elif abs(side) <= 1300:
        half = "river"
    else:
        half = "own half" if side < 0 else "rival half"
    return f"{half} · {'lane' if lane_at(x, y) else 'jungler'}"


def near_pit(x: float, y: float) -> str | None:
    for pit, (px, py) in OBJECTIVE_PIT_POSITIONS.items():
        if (x - px) ** 2 + (y - py) ** 2 <= PIT_RADIUS**2:
            return pit
    return None


def allies_near(match: Match, victim: int, x: float, y: float, t: float) -> int:
    """Allies within 2000 of the death spot in the nearest frame (1 per minute: approximate)."""
    minute = round(t / 60_000)
    count = 0
    for pid, rows in match.frames.items():
        if pid == victim or match.team_of.get(pid) != match.team_of.get(victim) or minute >= len(rows):
            continue
        if (rows[minute, 6] - x) ** 2 + (rows[minute, 7] - y) ** 2 <= 2000**2:
            count += 1
    return count


def death_rows(match: Match, model: WinModel) -> list[dict[str, Any]]:
    out = []
    for e in match.kills:
        victim, t = e.get("victimId"), e.get("timestamp", 0)
        team = match.team_of.get(victim)
        if team is None:
            continue
        minute = t / 60_000
        level = match.level_at(victim, t)
        timer = respawn_seconds(level, minute)
        window_end = t + (timer + RESPAWN_MARGIN_S) * 1000
        x, y = (e.get("position") or {}).get("x", 0), (e.get("position") or {}).get("y", 0)
        fight = [k for k in match.kills if abs(k.get("timestamp", 0) - t) <= FIGHT_WINDOW_MS]
        allied_deaths = sum(1 for k in fight if match.team_of.get(k.get("victimId")) == team)
        wp_before = model.team(match, team, t - 1)
        victim_p = match.participants[victim]
        won = match.winner == team
        out.append({
            "match_id": match.id,
            "puuid": victim_p["puuid"],
            "victim": victim,
            "killer": e.get("killerId", 0),
            "assisting": [i for i in (e.get("assistingParticipantIds") or []) if i in match.team_of],
            "role": victim_p["role"],
            "minute": round(minute, 2),
            "level": level,
            "respawn_s": round(timer, 1),
            "bounty": e.get("bounty", 0),
            "shutdown": e.get("shutdownBounty", 0),
            "assisters": len(e.get("assistingParticipantIds") or []),
            "damage_dealt": e.get("victim_dealt", 0),
            "tower_damage": e.get("victim_received_tower", 0),
            "zone": zone(x, y, team),
            "near_pit": near_pit(x, y),
            "allies_near": allies_near(match, victim, x, y, t),
            "allies_dead_before": match.dead_at(team, t - 1, exclude=victim),
            "enemies_dead_before": match.dead_at(300 - team, t - 1),
            "trade": len(fight) - 2 * allied_deaths,  # their team's kills - their team's deaths within ±15 s
            "fight_size": len(fight),
            "conceded": [o["kind"] for o in match.objectives if t < o["t"] <= window_end and o["team"] == 300 - team],
            "won": won,
            "wp_before": round(wp_before, 4),
            "wpa": round((1.0 if won else 0.0) - wp_before, 4),
        })
    return out


def phase_label(minute: float) -> str:
    return "0-14" if minute < 14 else "14-25" if minute < 25 else "25+"


def group(rows: list[dict[str, Any]], key) -> list[dict[str, Any]]:
    """WPA of the deaths by group, with its decomposition: winrate and prior WP."""
    groups: dict[Any, list[tuple[float, float]]] = defaultdict(list)
    for r in rows:
        groups[key(r)].append((1.0 if r["won"] else 0.0, r["wp_before"]))
    out = [{"group": name, **wpa_summary(pairs)} for name, pairs in groups.items() if len(pairs) >= 40]
    return sorted(out, key=lambda g: g["wpa"])


def death_findings(deaths: list[dict[str, Any]], values: dict[str, float]) -> dict[str, Any]:
    def concedes(d: dict[str, Any]) -> str:
        return "nothing" if not d["conceded"] else max(d["conceded"], key=lambda k: values.get(k, 0))

    def fight(d: dict[str, Any]) -> str:
        return "wins the fight" if d["trade"] > 0 else "ties" if d["trade"] == 0 else "loses the fight"

    return {
        "all": wpa_summary([(1.0 if d["won"] else 0.0, d["wp_before"]) for d in deaths]),
        "per_phase": group(deaths, lambda d: phase_label(d["minute"])),
        "per_objective_conceded": group(deaths, concedes),
        "per_fight": group(deaths, fight),
        "phase_x_fight": group(deaths, lambda d: f"{phase_label(d['minute'])} · {fight(d)}"),
        "phase_x_conceded": group(deaths, lambda d: f"{phase_label(d['minute'])} · {'concedes' if d['conceded'] else 'nothing'}"),
        "by_teammates_already_dead": group(deaths, lambda d: f"{min(d['allies_dead_before'], 3)}{'+' if d['allies_dead_before'] >= 3 else ''} already dead"),
        "per_assisters": group(deaths, lambda d: f"{min(d['assisters'], 3)}{'+' if d['assisters'] >= 3 else ''} assisters"),
        "per_allies_near": group(deaths, lambda d: f"{min(d['allies_near'], 2)}{'+' if d['allies_near'] >= 2 else ''} allies near"),
        "per_zone": group(deaths, lambda d: d["zone"]),
        "per_pit": group(deaths, lambda d: d["near_pit"] or "far from pits"),
        "per_shutdown": group(deaths, lambda d: "shutdown ≥ 300" if d["shutdown"] >= 300 else "shutdown < 300"),
        "per_tower": group(deaths, lambda d: "tower hits them" if d["tower_damage"] > 0 else "no tower"),
        "per_role": group(deaths, lambda d: d["role"]),
    }


def death_model(deaths: list[dict[str, Any]], values: dict[str, float]) -> dict[str, Any]:
    """Expected WPA of each death according to its features, to score a single death.

    A single death's WPA is noisy (the whole game decides the result); its
    expected value given its features is not. Features: minute, how the fight ended and the WPA
    of what the enemy took while they were dead. The prior WP enters as a control
    and is left neutral when predicting: WPA already discounts the state, and that way a game that
    was already lost doesn't count twice.
    """
    names = ["minute/10", "(minute/10)²", "trade", "wpa_conceded/10", "wp_previous-0.5"]

    def features(d: dict[str, Any]) -> list[float]:
        m = d["minute"] / 10
        return [m, m * m, d["trade"], sum(values.get(k, 0) for k in d["conceded"]) / 10, d["wp_before"] - 0.5]

    x = np.array([features(d) for d in deaths])
    y = np.array([d["wpa"] for d in deaths])
    design = np.column_stack([np.ones(len(x)), x])
    coef, *_ = np.linalg.lstsq(design, y, rcond=None)
    neutral = design.copy()
    neutral[:, -1] = 0.0
    for d, expected in zip(deaths, neutral @ coef, strict=True):
        d["expected_wpa"] = round(float(expected), 4)
    return {
        "coefficients": dict(zip(["intercept", *names], (float(c) for c in coef), strict=True)),
        "r2": round(float(1 - np.var(y - design @ coef) / np.var(y)), 4),
    }


# ── WPA of each player in each match ──────────────────────────────────────────


def gold_per_cs(matches: list[Match]) -> float:
    """Gold per CS at 14, discounting that from kills: regression over all players."""
    rows, target = [], []
    for m in matches:
        early = [k for k in m.kills if k.get("timestamp", 0) < LANE_MINUTE * 60_000]
        for pid, frames in m.frames.items():
            if len(frames) <= LANE_MINUTE:
                continue
            f = frames[LANE_MINUTE]
            takedowns = sum(1 for k in early if k.get("killerId") == pid or pid in (k.get("assistingParticipantIds") or []))
            rows.append([f[4] + f[5], takedowns])
            target.append(f[1])
    design = np.column_stack([np.ones(len(rows)), np.array(rows)])
    coef, *_ = np.linalg.lstsq(design, np.array(target), rcond=None)
    return float(coef[1])


def player_wpa(match: Match, pid: int, role: str, deaths: list[dict[str, Any]], values: dict[str, float],
               model: WinModel, cs_gold: float) -> dict[str, float]:
    """The player's WPA in the match, in points: deaths, takedowns, objectives and farm advantage at 14.

    - Deaths: expected WPA of each one (almost always negative).
    - Takedowns: for each enemy death they kill or assist in, what that death took from
      the enemy, split in equal parts among those who took part.
    - Objectives: the objective's WPA, split among those who took part.
    - Farm: what the CS difference with their opponent at 14 is worth in WP, converted to gold.
      CS only, so as not to count the kills' gold twice.
    """
    team = match.team_of[pid]
    own_deaths = sum(d["expected_wpa"] for d in deaths if d["victim"] == pid)
    takedowns = 0.0
    for d in deaths:
        if match.team_of.get(d["victim"]) == team:
            continue
        credited = [i for i in [d["killer"], *d["assisting"]] if match.team_of.get(i) == team]
        if pid in credited:
            takedowns += -d["expected_wpa"] / len(credited)
    objectives = sum(
        values.get(o["kind"], 0) / 100 / len(o["ids"])
        for o in match.objectives if o["team"] == team and pid in o["ids"]
    )
    farm = 0.0
    opponent = next((p["participantId"] for p in match.participants.values() if p["teamId"] != team and p["role"] == role), None)
    mine, theirs = match.frames.get(pid), match.frames.get(opponent) if opponent else None
    if match.duration > LANE_MINUTE * 60 and mine is not None and theirs is not None and len(mine) > LANE_MINUTE and len(theirs) > LANE_MINUTE:
        cs_diff = (mine[LANE_MINUTE, 4] + mine[LANE_MINUTE, 5]) - (theirs[LANE_MINUTE, 4] + theirs[LANE_MINUTE, 5])
        x = match.state(LANE_MINUTE * 60_000)
        without = x.copy()
        without[0] -= (1 if team == 100 else -1) * cs_diff * cs_gold / 1000
        farm = model.team_from_state(x, team) - model.team_from_state(without, team)
    parts = {"wpa_deaths": own_deaths, "wpa_takedowns": takedowns, "wpa_objectives": objectives, "wpa_farm": farm}
    parts = {k: round(100 * v, 3) for k, v in parts.items()}
    parts["wpa_total"] = round(sum(parts.values()), 3)
    return parts


# ── Descriptive metrics (association, not effect) ─────────────────────────────


def frame_at(rows: np.ndarray, minute: int) -> np.ndarray:
    return rows[min(minute, len(rows) - 1)]


CHALLENGES = [
    "laneMinionsFirst10Minutes", "maxCsAdvantageOnLaneOpponent", "maxLevelLeadLaneOpponent",
    "earlyLaningPhaseGoldExpAdvantage", "laningPhaseGoldExpAdvantage", "turretPlatesTaken", "soloKills",
    "takedownsFirstXMinutes", "killsNearEnemyTurret", "killsUnderOwnTurret", "outnumberedKills",
    "pickKillWithAlly", "immobilizeAndKillWithAlly", "knockEnemyIntoTeamAndKill", "saveAllyFromDeath",
    "survivedSingleDigitHpCount", "skillshotsHit", "skillshotsDodged", "enemyJungleMonsterKills",
    "jungleCsBefore10Minutes", "moreEnemyJungleThanOpponent", "epicMonsterSteals", "epicMonsterKillsNearEnemyJungler",
    "dragonTakedowns", "baronTakedowns", "riftHeraldTakedowns", "voidMonsterKill", "visionScorePerMinute",
    "visionScoreAdvantageLaneOpponent", "controlWardsPlaced", "wardTakedowns", "wardTakedownsBefore20M",
    "stealthWardsPlaced", "wardsGuarded", "effectiveHealAndShielding", "damageTakenOnTeamPercentage",
    "teamDamagePercentage", "damagePerMinute", "goldPerMinute", "kda", "killParticipation",
    "enemyChampionImmobilizations", "landSkillShotsEarlyGame", "quickSoloKills", "multikills",
    "teleportTakedowns", "getTakedownsInAllLanesEarlyJungleAsLaner", "junglerKillsEarlyJungle",
    "killsOnLanersEarlyJungleAsJungler", "firstTurretKilledTime", "takedownsBeforeJungleMinionSpawn",
    "buffsStolen", "scuttleCrabKills", "initialCrabCount", "alliedJungleMonsterKills", "deathsByEnemyChamps",
]
PARTICIPANT = [
    "kills", "deaths", "assists", "timeCCingOthers", "totalTimeSpentDead", "longestTimeSpentLiving",
    "damageSelfMitigated", "totalDamageTaken", "totalHealsOnTeammates", "totalDamageShieldedOnTeammates",
    "wardsPlaced", "wardsKilled", "visionWardsBoughtInGame", "detectorWardsPlaced", "damageDealtToBuildings",
    "damageDealtToObjectives", "turretKills", "firstBloodKill", "firstBloodAssist", "firstTowerKill",
    "firstTowerAssist", "totalMinionsKilled", "neutralMinionsKilled", "goldEarned", "totalDamageDealtToChampions",
]


def game_row(match: Match, puuid: str, role: str, model: WinModel) -> dict[str, Any] | None:
    me = next((p for p in match.participants.values() if p["puuid"] == puuid), None)
    if me is None:
        return None
    pid, team = me["participantId"], me["teamId"]
    opponent = next((p for p in match.participants.values() if p["teamId"] != team and p["role"] == role), None)
    minutes = match.duration / 60
    row: dict[str, Any] = {
        "match_id": match.id, "puuid": puuid, "pid": pid, "role": role, "champion": me["championName"],
        "opponent": opponent["championName"] if opponent else None, "win": match.winner == team,
        "duration_min": round(minutes, 1), "patch": match.version,
    }
    mine = match.frames.get(pid)
    theirs = match.frames.get(opponent["participantId"]) if opponent else None
    for minute in (10, 14):
        if mine is not None and theirs is not None and len(mine):
            a, b = frame_at(mine, minute), frame_at(theirs, minute)
            row[f"gold_diff_{minute}"] = int(a[1] - b[1])
            row[f"xp_diff_{minute}"] = int(a[2] - b[2])
            row[f"cs_diff_{minute}"] = int(a[4] + a[5] - b[4] - b[5])
    row["wp_15"] = round(model.team(match, team, 15 * 60_000), 4) if match.duration > 15 * 60 else None
    plates = [e for e in match.events if e["type"] == "TURRET_PLATE_DESTROYED" and e.get("timestamp", 0) < LANE_MINUTE * 60_000]
    lane = LANE_OF_ROLE.get(role)
    if lane:
        taken = sum(1 for e in plates if e.get("laneType") == lane and e.get("teamId") != team)
        lost = sum(1 for e in plates if e.get("laneType") == lane and e.get("teamId") == team)
        row["lane_plates_diff_pre14"] = taken - lost
    row["cs_per_min"] = round((me.get("totalMinionsKilled", 0) + me.get("neutralMinionsKilled", 0)) / minutes, 2)
    all_damage = sum(p.get("totalDamageDealtToChampions", 0) for p in match.participants.values())
    row["damage_vs_game"] = round(me.get("totalDamageDealtToChampions", 0) / (all_damage / 10), 3) if all_damage else None
    for key in PARTICIPANT:
        row[key] = me.get(key)
    for key in CHALLENGES:
        value = me["challenges"].get(key)
        row[f"ch_{key}"] = value if isinstance(value, (int, float)) else None
    return row


def descriptive(games: list[dict[str, Any]]) -> dict[str, Any]:
    """AUC of each metric against the result by role. It is association, like a winrate: it doesn't measure effect."""
    skip = {"match_id", "puuid", "pid", "player", "role", "champion", "opponent", "win", "patch", "wp_15", "decisive", "grade"}
    out = {}
    for role in ROLES:
        rows = [g for g in games if g["role"] == role]
        y = np.array([1.0 if g["win"] else 0.0 for g in rows])
        metrics = []
        for key in sorted({k for g in rows for k in g} - skip):
            values = np.array([np.nan if g.get(key) is None else float(g[key]) for g in rows])
            known = ~np.isnan(values)
            if known.sum() < 0.8 * len(rows) or np.nanstd(values) == 0:
                continue
            metrics.append({"metric": key, "auc": round(auc(values[known], y[known]), 3)})
        out[role] = sorted(metrics, key=lambda m: -abs(m["auc"] - 0.5))
    return out


# ── Grade: the player's WPA against the Challengers of their role ─────────────


def grades(games: list[dict[str, Any]]) -> dict[str, Any]:
    out = {}
    for role in ROLES:
        rows = [g for g in games if g["role"] == role]
        total = np.array([g["wpa_total"] for g in rows])
        y = np.array([1.0 if g["win"] else 0.0 for g in rows])
        mean, sd = float(total.mean()), float(total.std())
        for g in rows:
            g["grade"] = round(100 * 0.5 * (1 + math.erf((g["wpa_total"] - mean) / (sd * math.sqrt(2)))))
        grade = np.array([g["grade"] for g in rows])
        parts = {k: round(float(np.mean([g[k] for g in rows])), 2) for k in ("wpa_deaths", "wpa_takedowns", "wpa_objectives", "wpa_farm")}
        out[role] = {
            "wpa_media": round(mean, 2),
            "wpa_deviation": round(sd, 2),
            "components_mean": parts,
            "components_deviation": {k: round(float(np.std([g[k] for g in rows])), 2) for k in parts},
            "auc_result": round(auc(total, y), 3),
            "grade_mean_win": round(float(grade[y == 1].mean()), 1),
            "grade_mean_loss": round(float(grade[y == 0].mean()), 1),
            "losses_with_grade_70_or_more": round(float(np.mean(grade[y == 0] >= 70)), 3),
            "wins_with_grade_30_or_less": round(float(np.mean(grade[y == 1] <= 30)), 3),
        }
    return out


def players_by_wpa(games: list[dict[str, Any]], players: dict[str, Any]) -> list[dict[str, Any]]:
    """Mean WPA per player against their LP and their winrate in the sample: external validation."""
    out = []
    for entry in players.values():
        rows = [g for g in games if g["player"] == entry["riot_id"]]
        if not rows:
            continue
        out.append({
            "player": entry["riot_id"], "role": entry["role"], "lp": int(entry["rank"].split()[2]) if entry.get("rank") else None,
            "winrate": round(100 * float(np.mean([g["win"] for g in rows])), 1),
            "wpa_mid": round(float(np.mean([g["wpa_total"] for g in rows])), 2),
            "grade_mean": round(float(np.mean([g["grade"] for g in rows])), 1),
        })
    return sorted(out, key=lambda p: (p["role"], -p["wpa_mid"]))


# ── Why it was won or lost ────────────────────────────────────────────────────


def decisive_moment(match: Match, model: WinModel, team: int, pid: int, values: dict[str, float]) -> dict[str, Any]:
    """Point of no return: the last 2-minute stretch in which the game was still open (WP 40-60%)."""
    last = int(match.duration // 60)
    if last < 3:
        return {}
    wp = [model.team(match, team, m * 60_000) for m in range(last + 1)]
    won = match.winner == team
    open_minutes = [m for m in range(last + 1) if (wp[m] <= 0.6 if won else wp[m] >= 0.4)]
    start = min(open_minutes[-1], last - 2) if open_minutes else 0
    t0, t1 = start * 60_000, (start + 2) * 60_000
    beneficiary = team if won else 300 - team
    taken = [o["kind"] for o in match.objectives if t0 < o["t"] <= t1 and o["team"] == beneficiary]
    window_kills = [k for k in match.kills if t0 < k.get("timestamp", 0) <= t1]
    for_beneficiary = sum(1 for k in window_kills if match.team_of.get(k.get("killerId")) == beneficiary)
    against = len(window_kills) - for_beneficiary
    if taken:
        what = max(taken, key=lambda k: values.get(k, 0))
    elif for_beneficiary - against >= 2:
        what = "FIGHT"
    else:
        what = "PRESSURE_NO_OBJECTIVE"
    return {
        "minute": start, "from_start": not open_minutes, "what": what, "kills_for": for_beneficiary,
        "kills_against": against, "player_died": any(k.get("victimId") == pid for k in window_kills),
        "player_takedown": any(k.get("killerId") == pid or pid in (k.get("assistingParticipantIds") or []) for k in window_kills),
    }


def outcome_findings(games: list[dict[str, Any]]) -> dict[str, Any]:
    out = {}
    for role in ROLES:
        rows = [g for g in games if g["role"] == role and g.get("decisive")]
        result = {}
        for label, won in (("defeats", False), ("wins", True)):
            subset = [g for g in rows if g["win"] == won]
            counts: dict[str, int] = defaultdict(int)
            for g in subset:
                counts[g["decisive"]["what"]] += 1
            result[label] = {
                "n": len(subset),
                "moment": {k: round(v / len(subset), 3) for k, v in sorted(counts.items(), key=lambda kv: -kv[1])},
                "minute_median": median(g["decisive"]["minute"] for g in subset),
                "player_died": round(float(np.mean([g["decisive"]["player_died"] for g in subset])), 3),
                "player_took_part": round(float(np.mean([g["decisive"]["player_takedown"] for g in subset])), 3),
            }
        out[role] = result
    return out


# ── Principal ─────────────────────────────────────────────────────────────────


def main() -> None:
    data = Path(sys.argv[1])
    players, records = load(data)
    matches = [Match(r) for r in records.values()]
    set_draft_prior(matches)
    print(f"{len(matches)} games with timeline")

    model, wp_quality = fit_win_model(matches)
    print(f"win model: AUC {wp_quality['auc']} · log-loss {wp_quality['log_loss']} · calibration ±{wp_quality['calibration_error_pp']} pp")

    objectives, mid_outer = objective_wpa(matches, model)
    values = {o["objective"]: o["wpa"] for o in objectives}
    by_match = {m.id: m for m in matches}
    deaths_by_match = {m.id: death_rows(m, model) for m in matches}
    all_deaths = [d for rows in deaths_by_match.values() for d in rows]
    print(f"{len(all_deaths)} deaths")
    death_info = death_model(all_deaths, values)
    cs_gold = gold_per_cs(matches)

    games: list[dict[str, Any]] = []
    for entry in players.values():
        for match_id in entry.get("games") or []:
            match = by_match.get(match_id)
            row = game_row(match, entry["puuid"], entry["role"], model) if match else None
            if row is None:
                continue
            row["player"] = entry["riot_id"]
            row.update(player_wpa(match, row["pid"], entry["role"], deaths_by_match[match_id], values, model, cs_gold))
            row["decisive"] = decisive_moment(match, model, match.team_of[row["pid"]], row["pid"], values)
            games.append(row)
    print(f"{len(games)} games by roster players in their role")

    grade_info = grades(games)
    result = {
        "games_with_timeline": len(matches),
        "patches": sorted({m.version for m in matches if m.version}),
        "model_win": wp_quality,
        "value_objectives": objectives,
        "outer_tower_mid_per_minute": mid_outer,
        "deaths": death_findings(all_deaths, values),
        "model_wpa_death": death_info,
        "gold_per_cs": round(cs_gold, 2),
        "grade": grade_info,
        "players": players_by_wpa(games, players),
        "why": outcome_findings(games),
        "association_by_role": descriptive(games),
    }
    (data / "findings.json").write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    sample = {(g["match_id"], g["puuid"]): g["player"] for g in games}
    roster_deaths = [dict(d, player=sample[(d["match_id"], d["puuid"])]) for d in all_deaths if (d["match_id"], d["puuid"]) in sample]
    dataset = {
        "description": "Games in their role by the 50 best players of EUW (10 per role), with WPA. See research/ladder/REPORT.md.",
        "players": list(players.values()),
        "games": games,
        "roster_player_deaths": roster_deaths,
        **{k: result[k] for k in ("model_win", "value_objectives", "model_wpa_death", "grade")},
    }
    (data / "dataset.json").write_text(json.dumps(dataset, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {data / 'findings.json'} and {data / 'dataset.json'}")


if __name__ == "__main__":
    main()
