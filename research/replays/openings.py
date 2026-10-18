"""The jungler's opening: each time they leave their base —after a back or respawning—, which way they open the map,
what the map was like at that instant and what came out.

It is a decision the jungler makes five or eight times per game and that decides their next minute: which half of the
map they leave through. In the high leagues it is usually clear; lower down it is one of the most common mistakes. To judge it the whole
map at that moment is needed, and the replay has it:

- **the camps** of each half (above and below the diagonal that runs from base to base): theirs and the enemy's,
  alive now or in how many seconds they spawn (each `SpawnNeutral` and each clear), with their real gold in 16.19 (Krugs 109,
  Wolves 85, Gromp 80, Raptors 75, buffs 90), and the crab of each river;
- **the objectives**: the dragon (lower half) and the grubs, the herald or the baron (upper half), alive or how long
  until they spawn;
- **the lanes** of each half (top above, bot below, and mid apart): the enemies' health and flash, their own health and
  ultimates, where the wave is (from 0, against their turret, to 1, against the enemy's: who has
  priority) and the gold difference;
- **the enemy jungler**: through which half and how long ago their team last saw them, and through which half they last
  cleared (their route); and where they really were, which only serves the analysis: the player didn't know.

The **decision** is the half of the map where they are `DECIDE` seconds after leaving (top, bottom or mid) and the first
thing they do in `FIRST` seconds: one of their camps, one of the enemy's (invade), the crab, an objective or a
fight. **What came out**, in `HORIZON` seconds: the gold gained, their team's kills and deaths, the objectives and
the change in their team's WP (with value.py's curve, if there is a timeline).

    python research/replays/openings.py extract <harvest> <output.csv.gz> --leagues <matches.jsonl.gz> \\
        [--value <model.json>] [--processes N] [--only CHALLENGER,GRANDMASTER]
    python research/replays/openings.py model <openings.csv.gz> <folder>   # what the best choose and whether it pays off
    python research/replays/openings.py   # the minimal check, with an invented match
"""

from __future__ import annotations

import bisect
import collections
import csv
import functools
import gzip
import json
import math
import sys
import traceback
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import moments as M
import value as V

# the gold of each camp in 16.19, measured with each one's units (moments.idle_jungle)
GOLD = {"Gromp": 80, "Wolves": 85, "Raptors": 75, "Krugs": 109, "Blue": 90, "Red": 90}
# how the main monster's name starts for each thing on the map (the "Mini" ones don't count: they spawn with the main one)
MAIN = {"sru_gromp": "Gromp", "sru_murkwolf": "Wolves", "sru_razorbeak": "Raptors", "sru_krug": "Krugs",
             "sru_red": "Red", "sru_blue": "Blue", "sru_crab": "Scuttle", "sru_dragon": "Dragon",
             "sru_horde": "Voidgrub", "sru_riftherald": "Herald", "sru_baron": "Baron"}
EPICS_ABOVE = ("Voidgrub", "Herald", "Baron")
LANES = {"top": ("TOP",), "mid": ("MIDDLE",), "bot": ("BOTTOM", "UTILITY")}
BASE = 1200.0  # within this of their fountain, they are in it
OUTSIDE = 3000.0  # beyond this, they have already left: they have chosen where to go
FROM = 150.0  # before that is the start-of-game departure, the first clear: another decision (moments.fullclear)
DECIDE = 30  # seconds after leaving at which the half they are in is looked at
FIRST = 75  # seconds in which the first thing they do is looked for
HORIZON = 90  # seconds in which what came out is looked at
FAR = 600  # "a long time ago": the cap on the seconds since the enemy jungler was last seen
HALF_MARGIN = 1500.0  # within this of the diagonal, it is mid
UNTIL_SUPPORT = 840.0  # the support's opening belongs to the laning phase


def half(x: float, z: float, margin: float = HALF_MARGIN) -> str:
    """The half of the map: above the diagonal joining the two bases, top; below it, bot; against it, mid."""
    return "top" if z - x > margin else "bot" if x - z > margin else "mid"


def _main(name: str) -> str | None:
    n = name.lower()
    if "mini" in n:
        return None
    return next((c for pre, c in MAIN.items() if n.startswith(pre)), None)


class GameMap:
    """Everything in a match needed to see the map at any second."""

    def __init__(self, events: dict, rows: dict, waves: dict | None = None, curve: dict | None = None) -> None:
        self.events, self.rows, self.waves, self.curve = events, rows, waves, curve
        self.table = M._table(events, rows)
        self.bases = M._bases(rows)
        self.players = events["players"]
        self.team_of = {p["champion"]: p["team"] for p in self.players}
        self.net = {p["champion"]: p["net_id"] for p in self.players}
        self.champion_of = {p["net_id"]: p["champion"] for p in self.players}
        self.junglers = {p["team"]: p["champion"] for p in self.players if p["position"] == "JUNGLE"}
        self.position = {p["champion"]: p["position"] for p in self.players}
        _table, self.flash_slot = V._flash(events, rows)
        # each thing on the map, (what, half, which side of the jungle): when it spawns and when it falls
        self.monsters: dict[tuple[str, str, str], dict[str, list[float]]] = collections.defaultdict(
            lambda: {"leaves": [], "falls": []})
        for e in events["events"]:
            if e["type"] == "SpawnNeutral" and (c := _main(e.get("character") or e.get("name") or "")):
                x, z = e["position"]
                self.monsters[self._key(c, x, z)]["leaves"].append(e["time"])
        for c in events["camps"]:
            name = c["camp"].split(" ")[0]
            x, z = c["position"]
            if any(c["position"]):
                self.monsters[self._key(name, x, z)]["falls"].append(c["time"])
        for m in self.monsters.values():
            m["leaves"].sort()
            m["falls"].sort()
        self.deaths = sorted((e["time"], self.champion_of[e["net_id"]]) for e in events["events"]
                              if e["type"] == "Death" and e["net_id"] in self.champion_of)
        self.turrets = {e["net_id"] for e in events["events"]
                         if e["type"] == "SetSpell" and "Turret" in (e.get("name") or "")}
        self.recalls: dict[str, list[float]] = collections.defaultdict(list)
        for e in events["events"]:
            if e["type"] == "AddBuff" and e["buff"].lower() == "recall" and e["net_id"] in self.champion_of:
                self.recalls[self.champion_of[e["net_id"]]].append(e["time"])

    # the marksman's lane (see `botlane`): the crashes against the turrets, the freezes and where each turret is.
    # They are only computed if someone asks for them: the jungler's opening doesn't look at them
    @functools.cached_property
    def clashes(self) -> list[dict]:
        return M.stacks(self.events, self.waves, self.rows, until=UNTIL_SUPPORT + 60) if self.waves else []

    @functools.cached_property
    def cold(self) -> list[dict]:
        return M.freezes(self.events, self.waves, self.rows, until=UNTIL_SUPPORT) if self.waves else []

    @functools.cached_property
    def towers(self) -> dict[tuple[str, str], float]:
        return M._towers(self.events, self.waves) if self.waves else dict(M.TYPICAL_TOWERS)

    @staticmethod
    def _key(name: str, x: float, z: float) -> tuple[str, str, str]:
        return name, half(x, z, margin=0), "blue" if x + z < M.RIVER else "red"

    def available(self, key: tuple[str, str, str], t: float) -> float | None:
        """Seconds until that thing can be taken: 0 if alive, None if it won't spawn again in the match."""
        m = self.monsters.get(key)
        if not m or not m["leaves"]:
            return None
        i = bisect.bisect_right(m["leaves"], t)
        if i and not any(m["leaves"][i - 1] < k <= t for k in m["falls"]):
            return 0.0
        return m["leaves"][i] - t if i < len(m["leaves"]) else None

    def row(self, champion: str, t: float) -> dict | None:
        table = self.table.get(champion, {})
        for d in (0, -1, 1, -2, 2):
            f = table.get(int(t) + d)
            if f and f.get("x"):
                return f
        return None

    def spot(self, champion: str, t: float) -> tuple[float, float] | None:
        f = self.row(champion, t)
        return (float(f["x"]), float(f["z"])) if f else None


def _num(f: dict | None, column: str) -> float | None:
    """moments._num, with the row that may be missing (the second falls outside the match) and without the impossible: the uninitialised
    memory the decoder sometimes lets through (a health of -1.96e18)."""
    v = M._num(f, column) if f else None
    return v if v is not None and abs(v) < 1e7 else None


def _health(f: dict | None) -> float | None:
    """The part of health they have left (0-1), or None if dead or the row doesn't carry it properly."""
    if not f or f.get("alive") != "True":
        return None
    health, maxima = _num(f, "health"), _num(f, "health_max")
    if health is None or not maxima or maxima <= 0:
        return None
    return max(0.0, min(1.0, health / maxima))


def state(map_: GameMap, team: str, t: float) -> dict:
    """The map at second `t` seen by `team`: camps, objectives, lanes and enemy jungler."""
    own_side = "blue" if team == "100" else "red"
    rival_team = "200" if team == "100" else "100"
    f: dict = {}
    for h in ("top", "bot"):
        disp = {key: map_.available(key, t) for key in map_.monsters if key[1] == h}
        f[f"{h}_gold_now"] = sum(GOLD[c] for (c, _h, side), d in disp.items() if c in GOLD and side == own_side and d == 0)
        f[f"{h}_gold_30"] = sum(GOLD[c] for (c, _h, side), d in disp.items()
                              if c in GOLD and side == own_side and d is not None and d <= 30)
        f[f"{h}_gold_rival"] = sum(GOLD[c] for (c, _h, side), d in disp.items() if c in GOLD and side != own_side and d == 0)
        f[f"{h}_crab"] = int(any(c == "Scuttle" and d is not None and d <= 20 for (c, _h, _l), d in disp.items()))
        epics = sorted((d, c) for (c, _h, _l), d in disp.items() if d is not None
                        and (c == "Dragon" if h == "bot" else c in EPICS_ABOVE))
        f[f"{h}_objective"] = round(epics[0][0], 1) if epics else FAR
        f[f"{h}_objective_which"] = epics[0][1] if epics else ""
    for h, positions in LANES.items():
        own_items = [p["champion"] for p in map_.players if p["team"] == team and p["position"] in positions]
        rivals = [p["champion"] for p in map_.players if p["team"] == rival_team and p["position"] in positions]
        own_health = [v for c in own_items if (v := _health(map_.row(c, t))) is not None]
        rival_health = [v for c in rivals if (v := _health(map_.row(c, t))) is not None]
        f[f"{h}_allies_alive"], f[f"{h}_rivals_alive"] = len(own_health), len(rival_health)
        f[f"{h}_health_ally"] = round(sum(own_health) / len(own_health), 3) if own_health else 0.0
        f[f"{h}_health_rival"] = round(sum(rival_health) / len(rival_health), 3) if rival_health else 1.0
        f[f"{h}_no_flash_rival"] = sum(1 for c in rivals if (fr := map_.row(c, t)) and fr.get("alive") == "True"
                                        and map_.flash_slot.get(c) and fr.get(map_.flash_slot[c]) != "True")
        f[f"{h}_ult_ally"] = sum(1 for c in own_items if (fr := map_.row(c, t)) and fr.get("alive") == "True"
                                    and fr.get("r_ready") == "True")
        gold = [sum(_num(map_.row(c, t), "total_gold") or 0 for c in group) for group in (own_items, rivals)]
        f[f"{h}_gold_diff"] = round(gold[0] - gold[1])
        spot = M._advance(map_.waves, h, t) if map_.waves else None
        f[f"{h}_wave"] = round(min(1.0, max(0.0, spot[0] if team == "100" else 1 - spot[0])), 3) if spot else 0.5
    rival = map_.junglers.get(rival_team)
    sighted, where = None, None
    if rival:
        for s in range(int(t), max(0, int(t) - FAR), -1):
            fr = map_.table.get(rival, {}).get(s)
            if fr and fr.get("seen") == "True" and fr.get("x"):
                sighted, where = t - s, half(float(fr["x"]), float(fr["z"]))
                break
        real = map_.spot(rival, t)
        cleared_at = [(c["time"], c["position"]) for c in map_.events["camps"]
                  if c.get("killer") == map_.net.get(rival) and t - 90 <= c["time"] <= t and any(c["position"])]
        f["rival_half_real"] = half(*real) if real and _health(map_.row(rival, t)) is not None else "dead"
        f["rival_clean"] = half(*cleared_at[-1][1], margin=0) if cleared_at else "nothing"
    f["rival_seen_ago"] = round(sighted, 1) if sighted is not None else FAR
    f["rival_seen_half"] = where or "nothing"
    jungler = map_.junglers.get(team)
    gold = {eq: sum(_num(map_.row(c, t), "total_gold") or 0 for c, e in map_.team_of.items() if e == eq)
           for eq in ("100", "200")}
    f["gold_team_diff"] = round(gold[team] - gold[rival_team])
    f["level_diff"] = round((_num(map_.row(jungler, t), "level") or 0) - (_num(map_.row(rival, t), "level") or 0)) \
        if jungler and rival else 0
    f["minute"] = round(t / 60, 2)
    return f


def departures(map_: GameMap) -> list[dict]:
    """Each time a jungler leaves their base (from being within BASE of their fountain, or dead, to beyond OUTSIDE), from
    FROM: when they arrived, when they leave and whether they came from a back or from dying."""
    out = []
    for team, jungler in map_.junglers.items():
        source = map_.bases.get(team)
        if not source:
            continue
        inside = None
        for s in sorted(map_.table.get(jungler, {})):
            f = map_.table[jungler][s]
            if not f.get("x"):
                continue
            d = math.dist((float(f["x"]), float(f["z"])), source)
            if f.get("alive") != "True" or d < BASE:
                inside = s if inside is None else inside
            elif d > OUTSIDE and inside is not None:
                if s >= FROM and s - inside >= 3:
                    died = any(inside - 2 <= t <= s and c == jungler for t, c in map_.deaths)
                    out.append({"team": team, "jungler": jungler, "arrives": inside, "leaves": s,
                                  "trigger": "death" if died else "back"})
                inside = None
    return sorted(out, key=lambda x: x["leaves"])


def decision(map_: GameMap, jungler: str, t0: float) -> dict:
    """Which way they open: the half they are in DECIDE s after leaving, and the first thing they do in FIRST s."""
    team = map_.team_of[jungler]
    own_side = "blue" if team == "100" else "red"
    spot = map_.spot(jungler, t0 + DECIDE)
    candidates = []
    for c in map_.events["camps"]:
        if t0 < c["time"] <= t0 + FIRST and c.get("killer") == map_.net[jungler] and any(c["position"]):
            name = c["camp"].split(" ")[0]
            kind = ("crab" if name == "Scuttle" else "objective" if name not in GOLD else
                    "camp" if map_._key(name, *c["position"])[2] == own_side else "invasion")
            candidates.append((c["time"], kind, name, half(*c["position"], margin=0)))
    for e in map_.events["events"]:
        if e["type"] == "Damage" and t0 < e["time"] <= t0 + FIRST and e["net_id"] in map_.champion_of \
                and e.get("source") in map_.champion_of and map_.net[jungler] in (e["net_id"], e.get("source")) \
                and map_.team_of[map_.champion_of[e["net_id"]]] != map_.team_of[map_.champion_of[e["source"]]]:
            where = map_.spot(jungler, e["time"])
            candidates.append((e["time"], "fight", "", half(*where) if where else "mid"))
            break
    first = min(candidates, default=None)
    side = half(*spot) if spot and _health(map_.row(jungler, t0 + DECIDE)) is not None else "dead"
    # the opening is where they go first: the half of the first thing they do, if it comes early; otherwise, where they are at
    # DECIDE s (clearing the top Wolves and then going down through mid is opening top)
    opens = first[3] if first and first[0] - t0 <= 45 and first[3] else side
    return {"opens": opens, "side": side,
            "first": first[1] if first else "nothing", "first_which": first[2] if first else "",
            "first_side": first[3] if first else "", "first_t": round(first[0] - t0, 1) if first else ""}


def result(map_: GameMap, jungler: str, t0: float) -> dict:
    """What came out in HORIZON s: their gold, their team's kills and deaths, the objectives and the WP change."""
    team = map_.team_of[jungler]
    end = t0 + HORIZON
    gold = [_num(map_.row(jungler, t), "total_gold") for t in (t0, end)]
    at = [(t, c) for t, c in map_.deaths if t0 < t <= end]
    epics = [c for c in map_.events["camps"] if t0 < c["time"] <= t0 + HORIZON + 30
              and c["camp"].split(" ")[0] in ("Dragon", "Baron", "Herald", "Voidgrub")]
    own_items = sum(map_.team_of.get(map_.champion_of.get(c.get("killer"), "")) == team for c in epics)
    out = {"gold_90": round(gold[1] - gold[0]) if None not in gold else "",
             "kills_90": sum(map_.team_of[c] != team for _t, c in at),
             "deaths_90": sum(map_.team_of[c] == team for _t, c in at),
             "dies_jungler_90": int(any(c == jungler for _t, c in at)),
             "objectives_120": own_items - (len(epics) - own_items), "value_90": ""}
    if map_.curve is not None:
        before, after = V._windows(map_.curve, [t0], [end])
        a, d = float(before[0, 0]), float(after[0, 0])
        if not (math.isnan(a) or math.isnan(d)):
            out["value_90"] = round((1.0 if team == "100" else -1.0) * V.NEUTRAL * (d - a), 3)
    return out


# ── The support's opening ──────────────────────────────────────────────────────────────────────────────
#
# In the laning phase the support leaves base and chooses: going straight down to their lane or opening through the middle (vision in the river and
# in the jungle on that side, pressure on the enemy mid) and reaching bot later. What decides it is how the
# wave leaves it for their marksman: if it has just crashed into the enemy turret, the marksman has time; if the enemy is
# building a slow push (they will be thrown under their turret) or has it frozen (they have to go past the middle of the
# lane to farm), they don't.

DECIDE_SUPPORT = 30  # seconds after leaving in which it is looked at whether they step into the mid lane
ENTERS_MID = 5000.0  # beyond this from their fountain and above the diagonal, they go through the middle (past their inhibitor turret)
CRASH = 40.0  # seconds "the wave has just crashed" lasts: how long the next one takes to return
SLOWPUSH = 3  # extra minions of the enemy in the lane for it to be a slow push against them (moments.acumulaciones)
ARRIVES = 2000.0  # within this of their marksman, they have reached the lane
A_BASE = 25  # if that many seconds after leaving their marksman they are in their base, they haven't roamed: they have gone back to base


def departures_of(map_: GameMap, position: str, since: float = FROM, until: float = math.inf) -> list[dict]:
    """`departures`, for the players of any position: each time they leave their base between `since` and `until`."""
    out = []
    for p in map_.players:
        if p["position"] != position:
            continue
        champion, team = p["champion"], p["team"]
        source = map_.bases.get(team)
        if not source:
            continue
        inside = None
        for s in sorted(map_.table.get(champion, {})):
            f = map_.table[champion][s]
            if not f.get("x"):
                continue
            d = math.dist((float(f["x"]), float(f["z"])), source)
            if f.get("alive") != "True" or d < BASE:
                inside = s if inside is None else inside
            elif d > OUTSIDE and inside is not None:
                if since <= s <= until and s - inside >= 3:
                    died = any(inside - 2 <= t <= s and c == champion for t, c in map_.deaths)
                    out.append({"team": team, "champion": champion, "arrives": inside, "leaves": s,
                                  "trigger": "death" if died else "back"})
                inside = None
    return sorted(out, key=lambda x: x["leaves"])


def _own(advance: float, team: str) -> float:
    """A lane's advance seen by `team`: 0 at their turret, 1 at the enemy's."""
    return advance if team == "100" else 1 - advance


def botlane(map_: GameMap, team: str, t: float) -> dict:
    """How the bottom lane is for `team`'s marksman at second `t`: what decides whether their support can
    leave. `botlane_state` summarises it: "without marksman" (dead or in base: nobody to leave alone), "crash" (their wave
    crashed into the enemy turret less than CRASH s ago), "slowpush rival" (the enemy has SLOWPUSH
    extra minions and the wave is coming toward their turret), "freeze rival" (the enemy has it frozen on their side: to
    farm you have to go past the middle), "pushed" (past the middle, in their favour), "at their tower" and "neutral"."""
    own_side, rival = ("blue", "red") if team == "100" else ("red", "blue")
    rival_team = "200" if team == "100" else "100"
    position = {p["position"]: p["champion"] for p in map_.players if p["team"] == team}
    rivals = [p["champion"] for p in map_.players if p["team"] == rival_team and p["position"] in ("BOTTOM", "UTILITY")]
    adc = position.get("BOTTOM")
    f: dict = {}
    spot = M._advance(map_.waves, "bot", t) if map_.waves else None
    f["botlane_wave"] = round(_own(spot[0], team), 3) if spot else 0.5
    before = M._advance(map_.waves, "bot", t - 20) if map_.waves else None
    f["botlane_moves"] = round(_own(spot[0], team) - _own(before[0], team), 3) if spot and before else 0.0
    f["botlane_minions"] = (M._alive(map_.waves, "bot", own_side, t) - M._alive(map_.waves, "bot", rival, t)) if map_.waves else 0
    clash = max((c["ends"] for c in map_.clashes if c["lane"] == "bot" and c["side"] == own_side and c["ends"] <= t),
                 default=None)
    f["botlane_crash_ago"] = round(t - clash, 1) if clash is not None else FAR
    rival_clash = max((c["ends"] for c in map_.clashes if c["lane"] == "bot" and c["side"] == rival and c["ends"] <= t),
                       default=None)
    f["botlane_crash_rival_ago"] = round(t - rival_clash, 1) if rival_clash is not None else FAR
    f["botlane_freeze_rival"] = int(any(c["lane"] == "bot" and c["side"] == rival and c["since"] <= t <= c["until"]
                                      for c in map_.cold))
    fa = map_.row(adc, t) if adc else None
    is_alive = bool(fa) and fa.get("alive") == "True"
    where = (float(fa["x"]), float(fa["z"])) if is_alive else None
    axis = map_.waves["axis"].get("bot") if map_.waves else None
    f["adc_alive"] = int(is_alive)
    f["adc_in_base"] = int(bool(where) and math.dist(where, map_.bases[team]) < OUTSIDE)
    f["adc_health"] = _health(fa) if is_alive and _health(fa) is not None else 0.0
    f["adc_advance"] = round(_own((where[0] + where[1] - axis["blue"]) / (axis["red"] - axis["blue"]), team), 3) \
        if where and axis else 0.0
    in_botlane = [c for c in rivals if (q := map_.spot(c, t)) and _health(map_.row(c, t)) is not None
                and M._lane(*q) == "bot" and math.dist(q, map_.bases[rival_team]) > OUTSIDE]
    f["botlane_rivals"] = len(in_botlane)
    in_lane = is_alive and not f["adc_in_base"]
    f["botlane_state"] = ("without marksman" if not in_lane else
                         "crash" if f["botlane_crash_ago"] <= CRASH else
                         "freeze rival" if f["botlane_freeze_rival"] else
                         "slowpush rival" if f["botlane_minions"] <= -SLOWPUSH and f["botlane_wave"] < 0.6 else
                         "pushed" if f["botlane_wave"] >= 0.55 else
                         "at their tower" if f["botlane_wave"] <= 0.42 else "neutral")
    return f


def support_state(map_: GameMap, team: str, t: float) -> dict:
    """The map when the support leaves base: that of `state` (camps, objectives, lanes, enemy jungler) plus the
    lane of their marksman (`botlane`), where their own jungler is and the lane's gold against the enemy's."""
    f = state(map_, team, t) | botlane(map_, team, t)
    jungler = map_.junglers.get(team)
    q = map_.spot(jungler, t) if jungler and _health(map_.row(jungler, t)) is not None else None
    f["jungler_half"] = half(*q) if q else "dead"
    support = next((p["net_id"] for p in map_.players if p["team"] == team and p["position"] == "UTILITY"), None)
    # they already have the support item's wards (the first quest, around 7:20): there is vision to renew
    f["has_support_item"] = int(any(e["type"] == "BuyItem" and e["net_id"] == support and e["item_id"] in M.SUPPORT_ITEM
                                and e["time"] <= t for e in map_.events["events"]))
    return f


def roams(map_: GameMap) -> list[dict]:
    """The support's roams in the laning phase and the moments when they stay with their marksman
    (`value.roam_decisions`: what happens when they leave against what happens when they stay, in the same state), each
    with how the lane was when deciding (`botlane`) and, if the marksman dies in the next minute, how. Without the
    value curve there is no table."""
    if map_.curve is None:
        return []
    out = []
    for f in V.roam_decisions(map_.curve, map_.events, map_.rows):
        # leaving the marksman to go back to base is not a roam: `base_in`, the seconds it takes to be in their base
        # from leaving (blank if they don't step on it while away from them)
        base_in = next((s - int(f["time"]) for s in range(int(f["time"]), int(f["time"] + (f["lasts"] or 0)) + 1)
                        if (q := map_.spot(f["support"], s)) and math.dist(q, map_.bases[f["team"]]) < OUTSIDE), "") \
            if f["leaves"] else ""
        out.append(f | {"base_in": base_in} | botlane(map_, f["team"], f["time"])
                     | marksman_death(map_, f["team"], f["support"], f["time"], f["time"] + 60))
    return out


def decision_support(map_: GameMap, support: str, t0: float) -> dict:
    """Where the support opens: "mid" if within DECIDE_SUPPORT seconds they step on the mid lane past their inhibitor
    turret (above the diagonal, more than ENTERS_MID from their fountain); otherwise, the half they are in at 20 s
    (bottom is going straight down to their lane). With how long they take to reach their marksman, the seconds they spend in
    mid and in view of the enemy mid, and the wards they place in the first minute."""
    team = map_.team_of[support]
    source = map_.bases[team]
    position = {p["position"]: p["champion"] for p in map_.players if p["team"] == team}
    adc = position.get("BOTTOM")
    rival_mid = next((p["champion"] for p in map_.players if p["team"] != team and p["position"] == "MIDDLE"), None)
    in_mid = [s for s in range(int(t0), int(t0) + 61)
              if (q := map_.spot(support, s)) and half(*q) == "mid" and math.dist(q, source) > ENTERS_MID]
    at_20 = map_.spot(support, t0 + 20)
    is_alive = _health(map_.row(support, t0 + 20)) is not None
    opens = ("mid" if any(s <= t0 + DECIDE_SUPPORT for s in in_mid) else
            half(*at_20, margin=0) if at_20 and is_alive else "dead")
    arrives = next((s - t0 for s in range(int(t0), int(t0) + 181)
                  if adc and (q := map_.spot(support, s)) and (r := map_.spot(adc, s))
                  and _health(map_.row(adc, s)) is not None and math.dist(q, r) <= ARRIVES), "")
    seen_mid = sum(1 for s in range(int(t0), int(t0) + 61)
                    if rival_mid and (f := map_.table[support].get(s)) and f.get("seen") == "True"
                    and (q := map_.spot(support, s)) and (r := map_.spot(rival_mid, s))
                    and _health(map_.row(rival_mid, s)) is not None and math.dist(q, r) <= M.PRESSURE)
    wards = [(e["time"], tuple(e["target"])) for e in map_.events["events"]
             if e["type"] == "CastSpell" and e["net_id"] == map_.net[support] and e["spell"] in M.WARDS
             and t0 <= e["time"] <= t0 + 60]
    side = "blue" if team == "100" else "red"
    return {"opens": opens, "arrives_bot": arrives, "in_mid_60": len(in_mid), "seen_mid_60": seen_mid,
            "wards_60": len(wards),
            "ward_deep_60": round(max((M._depth(*w, side) for _t, w in wards), default=0.0), 3)}


def marksman_death(map_: GameMap, team: str, support: str, since: float, until: float) -> dict:
    """If `team`'s marksman dies in (since, until], how: `adc_dies_exposed` if they were past the middle of
    their lane (farming there without their support is exposing themselves in a window they had to respect), `adc_dies_under_tower`
    if they fall against their turret (they are dived: that is down to the wave they were left), `adc_dies_alone` if the support
    hadn't arrived, and how many enemies were on them. Blank if they don't die."""
    rival_team = "200" if team == "100" else "100"
    adc = next((p["champion"] for p in map_.players if p["team"] == team and p["position"] == "BOTTOM"), None)
    out = {"adc_dies": "", "adc_dies_advance": "", "adc_dies_exposed": "", "adc_dies_under_tower": "",
             "adc_dies_alone": "", "adc_dies_rivals": ""}
    when = next((t for t, c in map_.deaths if c == adc and since < t <= until), None)
    axis = map_.waves["axis"].get("bot") if map_.waves else None
    if when is None or not axis or not (q := map_.spot(adc, when - 1) or map_.spot(adc, when - 3)):
        return out
    advance = _own((q[0] + q[1] - axis["blue"]) / (axis["red"] - axis["blue"]), team)
    tower = _own(map_.towers[("bot", "blue" if team == "100" else "red")], team)
    s = map_.spot(support, when - 1)
    return {"adc_dies": round(when - since, 1), "adc_dies_advance": round(advance, 3),
            "adc_dies_exposed": int(advance > 0.5), "adc_dies_under_tower": int(advance <= tower + 0.04),
            "adc_dies_alone": int(not s or math.dist(s, q) > ARRIVES),
            "adc_dies_rivals": sum(1 for p in map_.players if p["team"] == rival_team
                                     and (r := map_.spot(p["champion"], when - 1)) and math.dist(r, q) <= 1500)}


def support_result(map_: GameMap, support: str, t0: float) -> dict:
    """What came out in HORIZON s of the support's opening: in the lane (whether the marksman dies and how —past
    the middle of the lane, which is exposing themselves, or under their turret, which is being dived—, the minions lost),
    on the map (team kills and deaths, their own, the pressure on mid) and the WP change."""
    team = map_.team_of[support]
    rival_team = "200" if team == "100" else "100"
    position = {p["position"]: p["champion"] for p in map_.players if p["team"] == team}
    adc = position.get("BOTTOM")
    end = t0 + HORIZON
    at = [(t, c) for t, c in map_.deaths if t0 < t <= end]
    adc_dies = next((t for t, c in at if c == adc), None)
    out = {"dies_adc_60": int(any(c == adc and t <= t0 + 60 for t, c in at)), "dies_adc_90": int(adc_dies is not None),
             "dies_support_90": int(any(c == support for _t, c in at)),
             "kills_90": sum(map_.team_of[c] != team for _t, c in at),
             "deaths_90": sum(map_.team_of[c] == team for _t, c in at),
             "value_60": "", "value_90": ""} | marksman_death(map_, team, support, t0, end)
    # the seconds the marksman spends past the middle of their lane before the support arrives (or the whole time)
    axis = map_.waves["axis"].get("bot") if map_.waves else None
    only = 0
    for s in range(int(t0), int(end) + 1):
        q, r = (map_.spot(adc, s) if adc and _health(map_.row(adc, s)) is not None else None), map_.spot(support, s)
        if q and r and math.dist(q, r) <= ARRIVES:
            break
        if q and axis and _own((q[0] + q[1] - axis["blue"]) / (axis["red"] - axis["blue"]), team) > 0.5 \
                and M._lane(*q) == "bot":
            only += 1
    out["adc_past_s"] = only
    owner_of = {p["net_id"]: p["team"] for p in map_.players}
    fall, lost = M._cs_lost(map_.waves, "bot", team, t0, end, owner_of) if map_.waves else (0, 0)
    out |= {"botlane_cs": fall, "botlane_cs_lost": lost}
    # what they collect: the takedowns in which they hit in the previous 10 s
    hit_damage = [e["time"] for e in map_.events["events"] if e["type"] == "Damage" and e.get("source") == map_.net[support]
            and t0 < e["time"] <= end and e["net_id"] in map_.champion_of]
    victims = {(t, c) for t, c in at if map_.team_of[c] != team}
    suffers = collections.defaultdict(list)
    for e in map_.events["events"]:
        if e["type"] == "Damage" and e.get("source") == map_.net[support] and t0 < e["time"] <= end \
                and e["net_id"] in map_.champion_of:
            suffers[map_.champion_of[e["net_id"]]].append(e["time"])
    out["takes_part_90"] = sum(1 for t, c in victims if any(t - 10 <= x <= t for x in suffers[c]))
    out["fight_90"] = int(bool(hit_damage))
    # pressure on mid: the enemy mid, in range and seeing it, retreats or goes back to base (moments._presionados)
    mid = [p for p in map_.players if p["team"] == rival_team and p["position"] == "MIDDLE"]
    pressure = M._pressured(map_.table, map_.waves, support, mid, map_.recalls, int(t0), int(t0) + 60, 8.0) \
        if map_.waves else []
    out["presses_mid"] = int(bool(pressure))
    out["mid_retreats"] = int(any(h for _r, _c, h in pressure))
    before, after = (M._advance(map_.waves, "mid", t0), M._advance(map_.waves, "mid", t0 + 60)) if map_.waves else (None, None)
    out["mid_wave_60"] = round(_own(after[0], team) - _own(before[0], team), 3) if before and after else ""
    if map_.curve is not None:
        for h in (60, 90):
            a, d = V._windows(map_.curve, [t0], [t0 + h])
            x, y = float(a[0, 0]), float(d[0, 0])
            if not (math.isnan(x) or math.isnan(y)):
                out[f"value{h}"] = round((1.0 if team == "100" else -1.0) * V.NEUTRAL * (y - x), 3)
    return out


# ── The opening to the objectives, from minute 14 onward ───────────────────────────────────────────────
#
# After the laning phase the opening that matters is the objective's: 45 seconds before a dragon or a
# baron spawns, the jungler and support want to already be setting up their zone (vision, a catch nearby). Going to another
# place is only justified if something is gained there.

FROM_OBJECTIVES = 840.0
BEFORE = 45  # seconds before the objective spawns in which where each one is gets looked at
ZONE = 4000.0  # within this of the pit, they are in the objective's zone (the river and the jungle entrances)
PREPARES = 15  # seconds in the zone, out of those BEFORE, to count as setting it up
EPIC_OBJECTIVE = {"sru_dragon": "Dragon", "sru_baron": "Baron", "sru_riftherald": "Herald", "sru_atakhan": "Atakhan"}


def what_it_does(in_zone: int, at_base: int, dead: int) -> str:
    """What they do in the BEFORE seconds before an objective: `prepares` if they spend PREPARES or more in their zone; `reset`
    if they spend PREPARES or more in base or dead (they don't have those seconds to choose: they either return from shopping or respawn); otherwise
    `other spot`: they were on the map and chose something else."""
    return "prepares" if in_zone >= PREPARES else "reset" if at_base + dead >= PREPARES else "other spot"


def preparations(map_: GameMap, positions: tuple[str, ...] = ("JUNGLE", "UTILITY")) -> list[dict]:
    """For each epic objective spawning from FROM_OBJECTIVES onward and each jungler and support: where they are in the
    BEFORE seconds before (`what_it_does`), what they get out of it there (a takedown in which they hit, a summoner spell
    burning an enemy next to them, turret gold) and who takes the objective."""
    spawn_times = []
    for e in map_.events["events"]:
        if e["type"] == "SpawnNeutral" and e["time"] >= FROM_OBJECTIVES and any(e["position"]):
            name = (e.get("character") or "").lower()
            what = next((v for k, v in EPIC_OBJECTIVE.items() if name.startswith(k)), None)
            if what:
                spawn_times.append((e["time"], what, tuple(e["position"]), e["net_id"]))
    died = {e["net_id"]: (e["time"], e.get("killer")) for e in map_.events["events"] if e["type"] == "UnitDeath"}
    summoners = [(e["time"], map_.champion_of[e["net_id"]]) for e in map_.events["events"]
                   if e["type"] == "CastSpell" and e["net_id"] in map_.champion_of and e["slot"] in (4, 5)
                   and M._gets_burned(e["spell"])]
    game_end = map_.events["game_length"]
    out = []
    for leaves, what, pit, net in sorted(spawn_times):
        if leaves + 5 > game_end:
            continue
        falls_, killed_by = died.get(net, (math.inf, None))
        takes_it = map_.team_of.get(map_.champion_of.get(killed_by, ""), "")
        gold = {eq: sum(_num(map_.row(c, leaves - BEFORE), "total_gold") or 0 for c, e in map_.team_of.items() if e == eq)
               for eq in ("100", "200")}
        for p in map_.players:
            if p["position"] not in positions:
                continue
            c, team = p["champion"], p["team"]
            rival_team = "200" if team == "100" else "100"
            in_zone = at_base = dead = 0
            for s in range(int(leaves) - BEFORE, int(leaves) + 1):
                f = map_.table[c].get(s)
                if not f or not f.get("x"):
                    continue
                q = (float(f["x"]), float(f["z"]))
                if f.get("alive") != "True":
                    dead += 1
                elif math.dist(q, map_.bases[team]) < OUTSIDE:
                    at_base += 1
                elif math.dist(q, pit) <= ZONE:
                    in_zone += 1
            arrives = next((round(leaves - s) for s in range(int(leaves) - 90, int(leaves) + 61)
                          if (q := map_.spot(c, s)) and _health(map_.row(c, s)) is not None
                          and math.dist(q, pit) <= ZONE), "")
            does = what_it_does(in_zone, at_base, dead)
            where = map_.spot(c, leaves - BEFORE // 2)
            # what they get where they are: a takedown in which they hit, a summoner burning an enemy next to them, a turret
            hit_damage = collections.defaultdict(list)
            for e in map_.events["events"]:
                if e["type"] == "Damage" and e.get("source") == map_.net[c] and e["net_id"] in map_.champion_of \
                        and leaves - BEFORE - 10 <= e["time"] <= leaves + 10:
                    hit_damage[map_.champion_of[e["net_id"]]].append(e["time"])
            kills = sum(1 for t, v in map_.deaths if leaves - BEFORE <= t <= leaves + 10 and map_.team_of[v] == rival_team
                        and any(t - 10 <= x <= t for x in hit_damage[v]))
            burns = sum(1 for t, v in summoners if leaves - BEFORE <= t <= leaves + 10 and map_.team_of[v] == rival_team
                        and (q := map_.spot(c, t)) and (r := map_.spot(v, t)) and math.dist(q, r) <= 1500)
            tower = sum(1 for e in map_.events["events"] if e["type"] == "Gold" and e["net_id"] == map_.net[c]
                        and e["unit"] in map_.turrets and leaves - BEFORE <= e["time"] <= leaves + 10)
            out.append({"objective": what, "leaves": round(leaves, 1), "team": team, "champion": c, "position": p["position"],
                          "does": does, "in_zone": in_zone, "at_base": at_base, "dead": dead, "arrives": arrives,
                          "x": round(where[0]) if where else "", "z": round(where[1]) if where else "",
                          "distance": round(math.dist(where, pit)) if where else "",
                          "kills": kills, "burns": burns, "tower": int(tower > 0),
                          "gets": int(bool(kills or burns or tower)),
                          "gold_team_diff": round(gold[team] - gold[rival_team]),
                          "falls_in": round(falls_ - leaves, 1) if falls_ < math.inf else "",
                          "takes_it": int(takes_it == team) if takes_it else "",
                          "pit_x": round(pit[0]), "pit_z": round(pit[1])})
    return out


def one_game(state_path: Path, events_path: Path, record: dict | None = None,
                model: Path | None = None) -> dict[str, list[dict]]:
    """A match's tables: `jungler` (one row per opening of each jungler: the map, the decision and what
    came out), `support` (the same for each support in the laning phase), `objectives` (where each jungler and each
    support is before each objective that spawns after 14) and `roams` (each time the support leaves their marksman or
    stays with them, with the lane at that moment; only with the value curve)."""
    with M.open_file(events_path) as fh:
        events = M.drop_revived(json.load(fh))
    rows = M.read_state(state_path)
    curve = None
    if record is not None and model is not None:
        try:
            curve = V.curve(record, events, state_path, V.coefficients(model))
        except Exception:  # without the WP, but with everything else
            curve = None
    map_ = GameMap(events, rows, M.lane_waves(events), curve)
    game = state_path.name.split(".")[0]
    wins = {p["team"]: s.get("WIN") == "Win" for p, s in zip(events["players"], events["stats"], strict=True)}
    out: dict[str, list[dict]] = {"jungler": [], "support": [], "objectives": [], "roams": []}
    for s in departures(map_):
        t0 = s["leaves"]
        out["jungler"].append(
            {"game": game, **s, "wins": int(wins.get(s["team"], False))}
            | state(map_, s["team"], t0) | decision(map_, s["jungler"], t0) | result(map_, s["jungler"], t0))
    for s in departures_of(map_, "UTILITY", until=UNTIL_SUPPORT):
        t0 = s["leaves"]
        out["support"].append(
            {"game": game, **s, "wins": int(wins.get(s["team"], False))}
            | support_state(map_, s["team"], t0) | decision_support(map_, s["champion"], t0)
            | support_result(map_, s["champion"], t0)
            # the lane when they started going back to base (8 s before arriving): the tempo is leaving with the wave crashed
            | {f"back_{k}": v for k, v in botlane(map_, s["team"], s["arrives"] - 8).items() if k.startswith("botlane")})
    out["objectives"] = [{"game": game, **f, "wins": int(wins.get(f["team"], False))} for f in preparations(map_)]
    out["roams"] = [{"game": game, **f, "wins": int(wins.get(f["team"], False))} for f in roams(map_)]
    return out


def _task(pair: tuple) -> dict[str, list[dict]] | str:
    state_path, events_path, record, model = pair
    try:
        return one_game(Path(state_path), Path(events_path), record, Path(model) if model else None)
    except Exception:  # a strange match doesn't stop the others
        return f"{Path(state_path).name}: {traceback.format_exc(limit=2).strip().splitlines()[-1]}"


def extract(harvest: Path, output: Path, leagues_path: Path, model: Path | None, processes: int,
           only: set[str] | None) -> None:
    import wp_per_second as W

    with gzip.open(leagues_path, "rt", encoding="utf-8") as fh:
        league = {(m := json.loads(line))["match_id"].replace("_", "-"): m["tier"] for line in fh}
    games = [e for e in sorted(harvest.glob("*.state.csv.gz"))
                if not only or league.get(e.name.split(".")[0]) in only]
    names = {e.name.split(".")[0] for e in games}
    records = W.records(leagues_path, names) if model else {}
    pairs = [(str(e), str(harvest / f"{e.name.split('.')[0]}.events.json.gz"),
              records.get(e.name.split(".")[0]), str(model) if model else None) for e in games]
    print(f"{len(pairs)} games · {processes} processes · value: {'yes' if model else 'no'}", flush=True)
    tables: dict[str, list[dict]] = {"jungler": [], "support": [], "objectives": [], "roams": []}
    bad_ones = []
    with ProcessPoolExecutor(processes) as pool:
        for i, r in enumerate(pool.map(_task, pairs, chunksize=4), 1):
            if isinstance(r, str):
                bad_ones.append(r)
                continue
            for name, rows in r.items():
                for f in rows:
                    f["league"] = league.get(f["game"], "")
                tables[name] += rows
            if i % 100 == 0:
                print(f"  {i}/{len(pairs)} · " + " · ".join(f"{len(v)} of {k}" for k, v in tables.items()), flush=True)
    # the jungler's in `output` (openings.csv.gz); the others, alongside: openings.support.csv.gz, openings.objectives.csv.gz and openings.roams.csv.gz
    for name, rows in tables.items():
        path = output if name == "jungler" else output.with_name(output.name.replace(".csv", f".{name}.csv"))
        columns = list(dict.fromkeys(k for f in rows for k in f))
        with gzip.open(path, "wt", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=columns, restval="")
            writer.writeheader()
            writer.writerows(rows)
        print(f"{path}: {len(rows)} rows from {len(pairs) - len(bad_ones)} games")
    if bad_ones:
        print(f"{len(bad_ones)} failed: {bad_ones[:5]}")


# ── What those who know most choose ────────────────────────────────────────────────────────────────────

def _diff(f: dict, key: str, scale: float = 1.0) -> float:
    return (float(f[f"top_{key}"]) - float(f[f"bot_{key}"])) / scale


def _near(seconds) -> float:
    """1 if the objective is alive, dropping to 0 when a minute or more remains before it spawns."""
    return max(0.0, 1.0 - float(seconds) / 60.0)


def _side(v: str) -> float:
    return 1.0 if v == "top" else -1.0 if v == "bot" else 0.0


# What can decide the opening, each thing as the difference between the top half and the bottom half (in favour of opening
# top). Gold in hundreds; health from 0 to 1; the wave, the advance in the lane (toward the enemy is priority).
ALL_FEATURES: list[tuple[str, str]] = [
    ("gold_now", "own living camps (gold)"),
    ("gold_30", "own camps alive or leaving within 30 s (gold)"),
    ("gold_rival", "rival's living camps (gold)"),
    ("crab", "crab alive or leaving within 20 s"),
    ("objective", "objective alive or leaving in under a minute"),
    ("rival_touched", "health the rivals of that lane are missing"),
    ("rival_no_flash", "rivals of that lane without flash"),
    ("rivals_alive", "living rivals in that lane"),
    ("allies_alive", "living allies in that lane"),
    ("health_ally", "health of the allies in that lane"),
    ("ult_ally", "allies in that lane with the ultimate"),
    ("priority", "wave pushed toward the rival (priority)"),
    ("lane_gold", "gold of their lane against the rival's (thousands)"),
    ("rival_seen", "rival jungler seen in that half recently"),
    ("rival_clean", "rival jungler clearing in that half"),
    ("blue", "plays on the blue side"),
]


def vector(f: dict) -> list[float]:
    """The ALL_FEATURES of an opening (a row of `state` + `team`), in their order."""
    return [_diff(f, "gold_now", 100), _diff(f, "gold_30", 100), _diff(f, "gold_rival", 100), _diff(f, "crab"),
            _near(f["top_objective"]) - _near(f["bot_objective"]),
            float(f["bot_health_rival"]) - float(f["top_health_rival"]), _diff(f, "no_flash_rival"),
            _diff(f, "rivals_alive"), _diff(f, "allies_alive"), _diff(f, "health_ally"), _diff(f, "ult_ally"),
            _diff(f, "wave"), _diff(f, "gold_diff", 1000),
            _side(f["rival_seen_half"]) * math.exp(-float(f["rival_seen_ago"]) / 60.0), _side(f["rival_clean"]),
            1.0 if f["team"] == "100" else 0.0]


UNTIL_JUNGLE = 14.0  # minutes: the opening from leaving base is judged in the laning phase; after that, the objective's
HIGH, LOW = ("CHALLENGER", "GRANDMASTER"), ("GOLD", "PLATINUM")
LEAGUE_ORDER = ["GOLD", "PLATINUM", "EMERALD", "DIAMOND", "MASTER", "GRANDMASTER", "CHALLENGER"]
CLEAR = 0.2  # an opening is "clear" if those above choose a side with 70% or more


def _logistic(z, w) -> float:
    import numpy as np

    return float(1 / (1 + np.exp(-np.clip(w[0] + z @ np.array(w[1:]), -30, 30))))


def scores(f: dict, model_: dict) -> float:
    """The probability that a Challenger or a Grandmaster opens top on that map (`model_` from `model()`)."""
    import numpy as np

    return _logistic((np.array(vector(f)) - np.array(model_["mean"])) / np.array(model_["scale"]), model_["weights"][0])


# What can decide the support's opening: how it leaves the lane for their marksman, what is in the middle and the rest
SUPPORT_FEATURES: list[tuple[str, str]] = [
    ("botlane_wave", "bot wave pushed toward the rival (0 at their tower, 1 at the rival's)"),
    ("botlane_minions", "extra minions in bot (theirs minus the rival's)"),
    ("crash", "their wave crashed into the rival tower less than 40 s ago"),
    ("crash_rival", "the rival's crashed into theirs less than 40 s ago"),
    ("freeze_rival", "the rival has it frozen on their side"),
    ("slowpush_rival", "the rival has three extra minions and the wave is coming"),
    ("adc_in_lane", "their marksman is alive and in the lane"),
    ("adc_health", "their marksman's health"),
    ("adc_advance", "how far their marksman is in the lane"),
    ("botlane_rivals", "bot rivals in the lane"),
    ("bot_health_rival", "bot rivals' health"),
    ("mid_wave", "mid wave pushed toward the rival"),
    ("mid_rival_touched", "health the rival mid is missing"),
    ("mid_health_ally", "health of their mid"),
    ("mid_no_flash_rival", "the rival mid, without flash"),
    ("dragon", "dragon alive or leaving in under a minute"),
    ("above", "grubs or herald alive or leaving in under a minute"),
    ("rival_seen_bot", "rival jungler seen at the bottom recently"),
    ("rival_seen_mid", "rival jungler seen in mid recently"),
    ("jungler_mid", "their jungler is in the middle"),
    ("has_support_item", "already has the support item's wards"),
    ("minute", "game minute"),
    ("after_dying", "leaves from respawning (not from a back)"),
    ("gold_team", "team gold against the rival (thousands)"),
    ("gold_botlane", "botlane gold against the rival's (thousands)"),
    ("blue", "plays on the blue side"),
]


def vector_support(f: dict) -> list[float]:
    """The SUPPORT_FEATURES of a support opening (a row of `support_state` + `team` + `trigger`)."""
    sighted = math.exp(-float(f["rival_seen_ago"]) / 60.0)
    minions, wave = float(f["botlane_minions"]), float(f["botlane_wave"])
    return [wave, max(-10.0, min(10.0, minions)) / 5, float(float(f["botlane_crash_ago"]) <= CRASH),
            float(float(f["botlane_crash_rival_ago"]) <= CRASH), float(f["botlane_freeze_rival"]),
            float(minions <= -SLOWPUSH and wave < 0.6),
            float(int(f["adc_alive"]) and not int(f["adc_in_base"])), float(f["adc_health"]), float(f["adc_advance"]),
            float(f["botlane_rivals"]), float(f["bot_health_rival"]), float(f["mid_wave"]),
            1.0 - float(f["mid_health_rival"]), float(f["mid_health_ally"]), float(f["mid_no_flash_rival"]),
            _near(f["bot_objective"]), _near(f["top_objective"]),
            sighted * (f["rival_seen_half"] == "bot"), sighted * (f["rival_seen_half"] == "mid"),
            float(f["jungler_half"] == "mid"), float(f["has_support_item"]), float(f["minute"]),
            float(f["trigger"] == "death"), float(f["gold_team_diff"]) / 1000, float(f["bot_gold_diff"]) / 1000,
            1.0 if f["team"] == "100" else 0.0]


def scores_support(f: dict, model_: dict) -> float:
    """The probability that a Challenger or Grandmaster support opens through the middle on that map."""
    import numpy as np

    return _logistic((np.array(vector_support(f)) - np.array(model_["mean"])) / np.array(model_["scale"]),
                      model_["weights"][0])


def _difference(v, matches_, game, times: int = 200) -> tuple[float, float, float, float]:
    """(mean if it matches, mean if not, and the 90% interval of the difference resampling whole matches)."""
    import numpy as np

    unique_, which = np.unique(game, return_inverse=True)
    rng, diffs = np.random.default_rng(0), []
    for _ in range(times):
        weight = np.bincount(rng.integers(0, len(unique_), len(unique_)), minlength=len(unique_))[which]
        diffs.append(np.average(v[matches_], weights=weight[matches_] + 1e-12)
                    - np.average(v[~matches_], weights=weight[~matches_] + 1e-12))
    lo, hi = np.percentile(diffs, [5, 95])
    return float(v[matches_].mean()), float(v[~matches_].mean()), float(lo), float(hi)


def _read(path: Path) -> list[dict]:
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _of_those_above(x, y, league, game):
    """What those in HIGH choose, to compare everyone against it: (mean, scale, weights in HIGH, weights in LOW, and the
    probability that the HIGH model gives each row, out of fold by match among those in HIGH)."""
    import zlib

    import numpy as np
    from analyse import logistic_fit, logistic_predict

    mean, scale = x.mean(0), x.std(0) + 1e-9
    z = (x - mean) / scale
    high_, low_ = np.isin(league, HIGH), np.isin(league, LOW)
    weights_high, weights_low = logistic_fit(z[high_], y[high_]), logistic_fit(z[low_], y[low_])
    fold = np.array([zlib.crc32(str(p).encode()) % 5 for p in game])
    p = logistic_predict(weights_high, z)
    for k in range(5):
        test = high_ & (fold == k)
        if test.any():
            p[test] = logistic_predict(logistic_fit(z[high_ & (fold != k)], y[high_ & (fold != k)]), z[test])
    return mean, scale, weights_high, weights_low, p


def _column(rows: list[dict], key: str, by: float = 1.0):
    import numpy as np

    return np.array([by * float(f[key]) if f.get(key) not in (None, "") else np.nan for f in rows])


def jungle_model(rows: list[dict]) -> tuple[dict, list[str]]:
    """Which half Challenger and Grandmaster junglers choose on leaving base in the laning phase, how much
    each league matches that and whether matching pays off: (what the coach uses, the report)."""
    import numpy as np
    from analyse import auc

    rows = [f for f in rows if f["opens"] in ("top", "bot") and float(f["minute"]) < UNTIL_JUNGLE]
    x = np.array([vector(f) for f in rows])
    y = np.array([f["opens"] == "top" for f in rows], float)
    league = np.array([f["league"] for f in rows])
    ids = {p: i for i, p in enumerate(sorted({f["game"] for f in rows}))}
    game = np.array([ids[f["game"]] for f in rows])
    wins = np.array([int(f["wins"]) for f in rows])
    mean, scale, weights_high, weights_low, p = _of_those_above(x, y, league, game)
    clear = np.abs(p - 0.5) >= CLEAR
    matches_ = (p >= 0.5) == (y == 1)
    value, gold, died = _column(rows, "value_90"), _column(rows, "gold_90"), _column(rows, "dies_jungler_90", 100.0)

    lines = ["# Jungler openings: what the best choose and whether following them pays off", "",
              f"{len(rows)} openings (departures from base after a back or a death, up to minute {UNTIL_JUNGLE:.0f}, "
              f"opening top or bottom) from {len(ids)} games. Model: a logistic regression fitted on {' and '.join(HIGH)}, "
              "evaluated out of fold by game. An opening is **clear** if the model gives one side "
              f"{50 + 100 * CLEAR:.0f}% or more.", "",
              "| league | openings | AUC | clear | match (clear) | win | lose | gold 90 s, match minus not | "
              "WP 90 s, match minus not |", "|" + "---|" * 9]
    agreement = {}
    for name in LEAGUE_ORDER:
        m = league == name
        if not m.any():
            continue
        c = m & clear
        g, pi = c & (wins == 1), c & (wins == 0)
        agreement[name] = {"all": round(float(matches_[c].mean()), 4), "winners": round(float(matches_[g].mean()), 4),
                           "losers": round(float(matches_[pi].mean()), 4)}
        diff = []
        for v in (gold, value):
            ok = c & ~np.isnan(v)
            yes_, no_ = v[ok & matches_], v[ok & ~matches_]
            diff.append(f"{yes_.mean() - no_.mean():+.1f}" if len(yes_) and len(no_) else "—")
        lines.append(f"| {name} | {m.sum()} | {auc(p[m], y[m]):.3f} | {c[m].mean():.0%} | {matches_[c].mean():.0%} | "
                      f"{matches_[g].mean():.0%} | {matches_[pi].mean():.0%} | {diff[0]} | {diff[1]} |")
    lines += ["", "Following those above, in the clear openings of all leagues (90% interval, resampling "
                  "games):", ""]
    follow = {}
    for key, name, v in (("gold", "jungler gold at 90 s", gold),
                             ("wp", "team WP at 90 s (neutral points)", value),
                             ("dies_pp", "jungler dies in 90 s (pp)", died)):
        ok = clear & ~np.isnan(v)
        if not (ok & matches_).any() or not (ok & ~matches_).any():
            continue
        yes_, no_, lo, hi = _difference(v[ok], matches_[ok], game[ok])
        follow[key] = {"matches": round(yes_, 2), "no": round(no_, 2), "interval": [round(lo, 2), round(hi, 2)]}
        lines.append(f"- {name}: matches {yes_:.1f}, does not match {no_:.1f}: **{yes_ - no_:+.1f}** [{lo:+.1f}, {hi:+.1f}]")
    lines += ["", "What weighs, in the high leagues and in Gold and Platinum (weights on the standardized "
                  "features; positive, in favour of opening top):", "", "| feature | high | Gold-Plat |", "|---|---|---|"]
    for i, (_key, what) in enumerate(ALL_FEATURES, 1):
        lines.append(f"| {what} | {weights_high[i]:+.2f} | {weights_low[i]:+.2f} |")
    return {"features": [c for c, _q in ALL_FEATURES], "mean": mean.round(6).tolist(), "scale": scale.round(6).tolist(),
            "until": UNTIL_JUNGLE, "weights": [weights_high.round(6).tolist()], "leagues": list(HIGH), "clear": CLEAR,
            "agreement": agreement, "follow": follow}, lines


BOTLANES = ("crash", "pushed", "neutral", "at their tower", "slowpush rival", "freeze rival", "without marksman")


def support_model(rows: list[dict]) -> tuple[dict, list[str]]:
    """Where supports open in the laning phase according to how they leave the lane for their marksman, what those of
    Challenger and Grandmaster do, how much each league matches and what comes of opening through the middle: (the coach's, the report)."""
    import numpy as np
    from analyse import auc

    rows = [f for f in rows if f["opens"] in ("mid", "bot")]
    x = np.array([vector_support(f) for f in rows])
    y = np.array([f["opens"] == "mid" for f in rows], float)
    league = np.array([f["league"] for f in rows])
    ids = {p: i for i, p in enumerate(sorted({f["game"] for f in rows}))}
    game = np.array([ids[f["game"]] for f in rows])
    wins = np.array([int(f["wins"]) for f in rows])
    botlane_ = np.array([f["botlane_state"] for f in rows])
    mean, scale, weights_high, weights_low, p = _of_those_above(x, y, league, game)
    clear = np.abs(p - 0.5) >= CLEAR
    matches_ = (p >= 0.5) == (y == 1)
    high_ = np.isin(league, HIGH)
    value = _column(rows, "value_90")
    died = _column(rows, "dies_adc_90", 100.0)
    exposed = _column(rows, "adc_dies_exposed", 100.0)
    tower = _column(rows, "adc_dies_under_tower", 100.0)
    mid = y == 1

    lines = ["# Support openings: where they leave base in the laning phase", "",
              f"{len(rows)} support departures from base (after a back or a death, from 2:30 to 14:00) from {len(ids)} "
              "games: it opens **through the middle** if within 30 s it steps on the mid lane past its inhibitor turret, and **bottom** "
              "if it goes straight down to its botlane.", "",
              "## How many open through the middle", "",
              "| league | departures | open through the middle | those who win | those who lose |", "|---|---|---|---|---|"]
    opens_mid = {}
    for name in LEAGUE_ORDER:
        m = league == name
        if m.any():
            opens_mid[name] = round(float(y[m].mean()), 4)
            lines.append(f"| {name} | {m.sum()} | **{y[m].mean():.0%}** | {y[m & (wins == 1)].mean():.0%} | "
                          f"{y[m & (wins == 0)].mean():.0%} |")
    lines += ["", "## According to the state of their marksman's botlane on leaving", "",
               "`crash`: their wave has crashed into the rival tower less than 40 s ago. `slowpush rival`: "
               "the rival has three extra minions and the wave is coming. `freeze rival`: the rival has it "
               "frozen on their side. `without marksman`: dead or in base.", "",
               "| botlane | departures | open through the middle, Challenger and GM | Gold and Platinum | "
               "marksman dies in 90 s: through the middle | bottom | WP 90 s: through the middle minus bottom "
               "|", "|" + "---|" * 7]
    by_botlane = {}
    low_ = np.isin(league, LOW)
    for state_ in BOTLANES:
        m = botlane_ == state_
        if not m.any():
            continue
        ok = m & ~np.isnan(value)
        diff, value_ = "—", None
        if (ok & mid).sum() > 30 and (ok & ~mid).sum() > 30:
            yes_, no_, lo, hi = _difference(value[ok], mid[ok], game[ok])
            diff = f"{yes_ - no_:+.2f} [{lo:+.2f}, {hi:+.2f}]"
            value_ = [round(yes_ - no_, 2), round(lo, 2), round(hi, 2)]
        by_botlane[state_] = {"high": round(float(y[m & high_].mean()), 4) if (m & high_).any() else None,
                              "low": round(float(y[m & low_].mean()), 4) if (m & low_).any() else None,
                              "n": int(m.sum()), "dies_mid": round(float(np.nanmean(died[m & mid])), 2),
                              "dies_bot": round(float(np.nanmean(died[m & ~mid])), 2), "value": value_}
        lines.append(f"| {state_} | {m.sum()} | **{by_botlane[state_]['high']:.0%}** | {by_botlane[state_]['low']:.0%} | "
                      f"{np.nanmean(died[m & mid]):.1f} % | {np.nanmean(died[m & ~mid]):.1f} % | {diff} |")
    # the tempo: with which wave they start going back to base (backs only; after dying they don't choose)
    goes_back = np.array([f.get("back_botlane_state", "") if f["trigger"] == "back" else "" for f in rows])
    if (goes_back != "").any():
        lines += ["", "## The tempo: which wave they go back with, and where they open afterwards", "",
                   "The botlane 8 s before reaching base (when the recall starts), backs only.", "",
                   "| botlane when the recall starts | backs | share of backs, Challenger and GM | Gold and "
                   "Platinum | open through the middle afterwards, Challenger and GM | Gold and Platinum |", "|" + "---|" * 6]
        for state_ in BOTLANES:
            m = goes_back == state_
            if m.sum() < 30:
                continue
            a_, b_ = m & high_, m & low_
            lines.append(f"| {state_} | {m.sum()} | {a_.sum() / max(1, ((goes_back != '') & high_).sum()):.0%} | "
                          f"{b_.sum() / max(1, ((goes_back != '') & low_).sum()):.0%} | "
                          + (f"**{y[a_].mean():.0%}**" if a_.any() else "—") + " | " + (f"{y[b_].mean():.0%}" if b_.any() else "—") + " |")
    lines += ["", "## When the marksman dies with the support opening through the middle", "",
               "| botlane | deaths | past the half of their lane (exposed) | stuck to their tower (they take him down) |",
               "|---|---|---|---|"]
    death = {}
    for state_ in BOTLANES:
        m = (botlane_ == state_) & mid & ~np.isnan(exposed)
        if m.sum() >= 20:
            death[state_] = {"exposed": round(float(exposed[m].mean()), 1), "tower": round(float(tower[m].mean()), 1),
                               "n": int(m.sum())}
            lines.append(f"| {state_} | {m.sum()} | {exposed[m].mean():.0f} % | {tower[m].mean():.0f} % |")
    lines += ["", "## What those above choose, and how much each league matches", "",
               f"A logistic regression fitted on {' and '.join(HIGH)} (probability of opening through the middle), out of fold by "
               f"game. Clear: the model gives one side {50 + 100 * CLEAR:.0f}% or more.", "",
               "| league | AUC | clear | match (clear) | win | lose |", "|---|---|---|---|---|---|"]
    agreement = {}
    for name in LEAGUE_ORDER:
        m = league == name
        c = m & clear
        if not c.any():
            continue
        g, pi = c & (wins == 1), c & (wins == 0)
        agreement[name] = {"all": round(float(matches_[c].mean()), 4), "winners": round(float(matches_[g].mean()), 4),
                           "losers": round(float(matches_[pi].mean()), 4)}
        lines.append(f"| {name} | {auc(p[m], y[m]):.3f} | {c[m].mean():.0%} | {matches_[c].mean():.0%} | "
                      f"{matches_[g].mean():.0%} | {matches_[pi].mean():.0%} |")
    lines += ["", "Where those above open through the middle (the model gives it 70% or more), opening "
                  "through the middle against going straight down (90% interval, resampling games):", ""]
    follow = {}
    goes_mid = p >= 0.5 + CLEAR
    for key, name, v in (("wp", "team WP at 90 s (neutral points)", value),
                             ("dies_adc_pp", "marksman dies in 90 s (pp)", died)):
        ok = goes_mid & ~np.isnan(v)
        if (ok & mid).sum() > 30 and (ok & ~mid).sum() > 30:
            yes_, no_, lo, hi = _difference(v[ok], mid[ok], game[ok])
            follow[key] = {"matches": round(yes_, 2), "no": round(no_, 2), "interval": [round(lo, 2), round(hi, 2)]}
            lines.append(f"- {name}: through the middle {yes_:.1f}, bottom {no_:.1f}: **{yes_ - no_:+.1f}** [{lo:+.1f}, {hi:+.1f}]")
    lines += ["", "What weighs (weights on the standardized features; positive, in favour of opening through the middle):", "",
               "| feature | Challenger and GM | Gold and Platinum |", "|---|---|---|"]
    for i, (_key, what) in enumerate(SUPPORT_FEATURES, 1):
        lines.append(f"| {what} | {weights_high[i]:+.2f} | {weights_low[i]:+.2f} |")
    return {"features": [c for c, _q in SUPPORT_FEATURES], "mean": mean.round(6).tolist(),
            "scale": scale.round(6).tolist(), "weights": [weights_high.round(6).tolist()], "leagues": list(HIGH),
            "clear": CLEAR, "agreement": agreement, "opens_mid": opens_mid, "by_botlane": by_botlane, "death": death,
            "follow": follow}, lines


def roams_report(rows: list[dict]) -> tuple[dict, list[str]]:
    """The support's roam from the lane, against staying with their marksman in the same game state
    (`value.effect`), according to how the wave was when leaving: what says whether the roam belonged to that window or not."""
    import numpy as np

    n = len(rows)
    col = {k: _column(rows, k) for k in ("time", "gold_team", "gold_botlane", "alive", "rival_in_botlane", "health_marksman",
                                           "leaves", "lasts", "short", "value_60", "botlane_60", "map_60")}
    died = _column(rows, "dies_60", 100.0)
    league = np.array([LEAGUE_ORDER.index(f["league"]) if f["league"] in LEAGUE_ORDER else -1 for f in rows])
    ids = {p: i for i, p in enumerate(sorted({f["game"] for f in rows}))}
    game = np.array([ids[f["game"]] for f in rows])
    botlane_ = np.array([f["botlane_state"] for f in rows])
    exposed, tower = _column(rows, "adc_dies_exposed", 100.0), _column(rows, "adc_dies_under_tower", 100.0)
    stays = col["leaves"] == 0
    a_base = _column(rows, "base_in") <= A_BASE  # goes to base, not to another lane: not a roam
    roam = (col["leaves"] == 1) & ~a_base & ((col["lasts"] >= 15) | (col["short"] == 1))
    state_ = V._stratum(league, V._spans(col["time"], (240, 360, 480, 600, 720)),
                         V._spans(col["gold_team"], (-1.5, -0.5, 0.5, 1.5)), V._spans(col["gold_botlane"], (-0.5, 0.5)),
                         np.sign(col["alive"]), col["rival_in_botlane"], V._spans(col["health_marksman"], (0.5, 0.8)))
    lines = ["# Support roams from the botlane, according to the wave they leave", "",
              f"{int(roam.sum())} roams (15 s or more, or cut short by a death; not counting the {int(((col['leaves'] == 1) & a_base).sum())} "
              f"times they leave to go back to base) and {int(stays.sum())} moments in which "
              f"the support stays with their marksman, from {len(ids)} games ({n} rows). Leaving minus staying in the "
              "same state (league, minute, team and botlane gold, living, rival support in the botlane, marksman's "
              "health), with the bot wave as it was when deciding. Neutral WP points; 90% interval.", "",
              "| botlane on leaving | roams | balance at 60 s | in the botlane | on the map | marksman dies "
              "(pp) | of the marksmen who die: past the half | stuck to their tower |", "|" + "---|" * 8]
    out = {}
    for name in (*BOTLANES[:-1], "all"):
        m = np.ones(n, bool) if name == "all" else botlane_ == name
        used = m & (roam | stays)
        if (used & roam).sum() < 50:
            continue

        def eff(v, used=used):
            return V.effect(roam[used].astype(float), v[used], state_[used], game[used])

        balance, in_botlane, on_map, dying = eff(col["value_60"]), eff(col["botlane_60"]), eff(col["map_60"]), eff(died)
        fall = used & roam & ~np.isnan(exposed)
        out[name] = {"roams": int((used & roam).sum()), "value_60": [round(v, 2) for v in balance[:3]],
                         "dies_60": [round(v, 2) for v in dying[:3]],
                         "exposed": round(float(exposed[fall].mean()), 1) if fall.any() else None,
                         "tower": round(float(tower[fall].mean()), 1) if fall.any() else None}
        lines.append(f"| {name} | {int((used & roam).sum())} | **{V._cell(balance)}** | {V._cell(in_botlane)} | "
                      f"{V._cell(on_map)} | {V._cell(dying)} | "
                      + (f"{exposed[fall].mean():.0f} % ({fall.sum()}) | {tower[fall].mean():.0f} % |" if fall.any() else "— | — |"))
    return out, lines


def objectives_report(rows: list[dict]) -> tuple[dict, list[str]]:
    """Where the jungler and support are the 45 s before each objective that spawns after 14, by league, and what
    happens to the objective depending on what they do."""
    import numpy as np

    league = np.array([f["league"] for f in rows])
    position = np.array([f["position"] for f in rows])
    does = np.array([what_it_does(int(f["in_zone"]), int(f["at_base"]), int(f["dead"])) for f in rows])
    gets = _column(rows, "gets")
    carries = _column(rows, "takes_it", 100.0)
    wins = _column(rows, "wins")
    lines = ["# Objective openings, from minute 14 onwards", "",
              f"{len(rows)} rows: each dragon, baron and herald that spawns after 14:00 and each jungler and support of the "
              f"game. **Prepares** if they spend {PREPARES} s or more of the preceding {BEFORE} within {ZONE:.0f} of the pit; "
              f"**reset** if they spend {PREPARES} or more in base or dead; otherwise, **other spot** (and if there they get something: a kill "
              "they hit in, a summoner spell that burns a rival next to them or a turret).", "",
              "The percentages are of the times they are on the map to choose (without the resets).", "",
              "| league | position | objectives | of them, reset | prepares | other spot and gets something | "
              "other spot and nothing | winners prepare | losers |", "|" + "---|" * 9]
    out: dict = {}
    chooses = does != "reset"
    for name in LEAGUE_ORDER:
        for role in ("JUNGLE", "UTILITY"):
            all_ = (league == name) & (position == role)
            m = all_ & chooses
            if not m.any():
                continue
            other = m & (does == "other spot")
            d = {"prepares": float((does[m] == "prepares").mean()),
                 "other_takes": float((other & (gets == 1)).sum() / m.sum()), "nothing": float((other & (gets == 0)).sum() / m.sum()),
                 "winners": float((does[m & (wins == 1)] == "prepares").mean()),
                 "losers": float((does[m & (wins == 0)] == "prepares").mean())}
            out.setdefault(name, {})[role] = {k: round(v, 4) for k, v in d.items()}
            lines.append(f"| {name} | {role} | {all_.sum()} | {1 - m.sum() / all_.sum():.0%} | **{d['prepares']:.0%}** | "
                          f"{d['other_takes']:.0%} | {d['nothing']:.0%} | {d['winners']:.0%} | {d['losers']:.0%} |")
    lines += ["", "Who takes the objective according to what each one does (all leagues; of the objectives that fall):", "",
               "| position | does | times | their team takes it |", "|---|---|---|---|"]
    carried_by = {}
    for role in ("JUNGLE", "UTILITY"):
        for what, m in (("prepares", does == "prepares"), ("reset", does == "reset"),
                       ("other spot and gets something", (does == "other spot") & (gets == 1)),
                       ("other spot and nothing", (does == "other spot") & (gets == 0))):
            ok = m & (position == role) & ~np.isnan(carries)
            if ok.any():
                carried_by.setdefault(role, {})[what] = round(float(carries[ok].mean()), 1)
                lines.append(f"| {role} | {what} | {ok.sum()} | {carries[ok].mean():.0f} % |")
    return {"leagues": out, "takes_it": carried_by, "before": BEFORE, "zone": ZONE}, lines


def model(path: Path, folder: Path) -> None:
    """From the `extract` tables (the jungler's in `path`; the others, alongside), what the coach uses (`model.json`: the
    jungler's above, and `support`, `roams` and `objectives`) and the whole report (`report.md`)."""
    out, lines = jungle_model(_read(path))
    for name, function in (("support", support_model), ("roams", roams_report), ("objectives", objectives_report)):
        another = path.with_name(path.name.replace(".csv", f".{name}.csv"))
        if another.exists():
            out[name], own_rows = function(_read(another))
            lines += ["", *own_rows]
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (folder / "model.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "model":
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ladder"))
        model(Path(sys.argv[2]), Path(sys.argv[3]))
    elif len(sys.argv) > 1 and sys.argv[1] == "extract":
        rest = sys.argv[4:]
        extract(Path(sys.argv[2]), Path(sys.argv[3]), Path(rest[rest.index("--leagues") + 1]),
               Path(rest[rest.index("--value") + 1]) if "--value" in rest else None,
               int(rest[rest.index("--processes") + 1]) if "--processes" in rest else 4,
               set(rest[rest.index("--only") + 1].split(",")) if "--only" in rest else None)
    else:  # the minimal check: a departure from base and the live camps, in an invented match
        players = [{"net_id": "a", "champion": "Blue", "team": "100", "position": "JUNGLE"},
                     {"net_id": "r", "champion": "Red", "team": "200", "position": "JUNGLE"}]

        def row(s, x, z, is_alive="True"):
            return {"time": str(s), "x": str(x), "z": str(z), "alive": is_alive, "seen": "False", "health": "1",
                    "health_max": "1", "total_gold": "1000", "level": "5", "team": "100"}
        # at their fountain (400, 400) until 200, leaves upward (the blue Gromp, above the diagonal)
        blue = [row(s, 400, 400) for s in range(0, 201)] + [row(200 + k, 400 + 20 * k, 400 + 150 * k) for k in range(1, 60)]
        red = [row(s, 14000, 14000) | {"team": "200"} for s in range(0, 260)]
        events = {"players": players, "stats": [{"SUMMONER_SPELL_1": "4"}, {"SUMMONER_SPELL_1": "4"}],
                   "game_length": 260.0, "camps": [], "events": [
                       {"type": "SpawnNeutral", "time": 90.0, "net_id": "g", "character": "SRU_Gromp", "position": [2100, 8400]},
                       {"type": "SpawnNeutral", "time": 90.0, "net_id": "k", "character": "SRU_Krug", "position": [8400, 2700]}]}
        map_ = GameMap(events, {"Blue": blue, "Red": red})
        deps = departures(map_)
        assert len(deps) == 1 and deps[0]["trigger"] == "back" and 200 < deps[0]["leaves"] < 230, deps
        e = state(map_, "100", deps[0]["leaves"])
        assert (e["top_gold_now"], e["bot_gold_now"]) == (80, 109), e  # the Gromp above, the Krugs below
        assert decision(map_, "Blue", deps[0]["leaves"])["side"] == "top"
        assert half(2000, 9000) == "top" and half(9000, 2000) == "bot" and half(7400, 7600) == "mid"
        print("ok")
