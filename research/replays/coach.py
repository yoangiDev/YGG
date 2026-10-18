"""What a coach would teach a player about a match: when, where, what happened and how much it cost them.

`features.py` summarises a match in one row per player. This is what lies behind that row for a single one,
with its minute and its place on the map, so that you can go to the match recording and see it:

- **deaths**: all of them, with who killed, whether it could be seen coming, in which fight and with how much less gold, how much gold
  was given away, how long they were dead and what the enemy took meanwhile;
- **stalled camps** (jungle): each time their small camps were alive without being cleared, what it
  cost with each one's real gold and what they were doing meanwhile;
- **leaving the fog** (jungle): each time the enemy sees them in the laning phase, with what they got out of it or without getting anything;
- **fights** their team lost (especially with less gold in items) and teamfights it won;
- **objectives**: each dragon, baron, herald and grubs, with how each team arrived in the minute and a half before;
- **swings**: where their team's WP collapsed while ahead, with what happened in that time;
- **flashes** spent with the dragon on the way, **backs** that let minions die, **lane departures** that
  got nothing;
- for the **jungler**, the **plays** they make with their own camps alive (with what everyone involved
  from both teams got) and the **camp pairs** they break;
- for the **support**, where they **open** on leaving base, their **roams** from the lane and their **vision** (each ward with
  what it showed and what it risked, and the support item);
- for the **marksman**, what they hit in each fight against what their teammates hit, the **trades** in their lane with their
  verdict, the **mid turret** that reaches 14 alive and the **slow pushes** that come at them with nobody near;
- for both, where they are before each **objective** that spawns after 14.

Each moment carries a coach text with its numbers, in English because it is what the web shows, its cost in gold or
in WP and a severity to order them. The reference prices (what a kill, a teamfight, a dragon is worth)
are those of value.md. `patterns` joins the moments of several matches and compares them with those of their league and role.

Each match also yields the post-game **scoreboard** (`scoreboard`) and a **1 to 100 grade**
(`grade` and `grades`): each moment adds or subtracts according to its kind and how big it was, is brought to a 30-minute
match and compared with what players of their league in their position add up to (`grades.py` measures that distribution). The
match's fights, objectives and swings do not count towards the grade: the team decides them.

    python research/replays/coach.py   # the minimal check, with an invented match
"""

from __future__ import annotations

import collections
import functools
import json
import math
import re
import statistics
from pathlib import Path

import moments as M
import value as V

# What each thing is worth in neutral WP points (value.md): a kill ~4.7; the mean of all matches.
WORTH = {"kill": 4.7, "teamfight": 19.9, "skirmish": 7.5, "dragon": 12.0, "baron": 17.5, "herald": 4.0, "grubs": 3.8}
DRAGONS = {"fire": "Infernal Drake", "water": "Ocean Drake", "earth": "Mountain Drake", "air": "Cloud Drake",
            "hextech": "Hextech Drake", "chemtech": "Chemtech Drake", "elder": "Elder Dragon"}
EPICS = {"Baron": "Baron Nashor", "Herald": "Rift Herald", "Voidgrub": "Voidgrubs", "Atakhan": "Atakhan"}
CAMPS = {"Gromp": "Gromp", "Wolves": "Wolves", "Raptors": "Raptors", "Krugs": "Krugs"}
LANING_PHASE = 840.0  # until 14:00, like the laning-phase concepts of moments.py
MINION_PRICE = 21  # ~average gold of a minion in the laning phase (melee 21, casters 14, cannon 60-90)
BASE = 2500.0  # within this of their fountain, they are in base
ZONES = Path(__file__).with_name("zones.json")  # the named places on the map: edited in `zone_map.py`
BUSHES = Path(__file__).with_name("bushes.json")  # the named bushes, drawn in `zone_map.py` (http://localhost:8765/?map=bushes)
GAP_MARGIN = 150.0  # units: between two hand-drawn zones there are slits (median 17, maximum 113 with 24,000 positions); a point in one belongs to the nearest zone
BUSH_MARGIN = 50.0  # units: the position is that of one second and the champion has a radius, so a point one cell from the edge counts as inside


def _clock(t: float) -> str:
    return M._clock(t)


def _duration(s: float) -> str:
    s = round(s)
    return f"{s // 60}:{s % 60:02d}" if s >= 60 else f"{s} s"


def _list(things: list[str]) -> str:
    things = [c for c in things if c]
    return things[0] if len(things) == 1 else ", ".join(things[:-1]) + " and " + things[-1] if things else ""


def _objective(name: str) -> str:
    """"Dragon (fire)" → "the Infernal Drake"; "Baron" → "Baron Nashor"; "Voidgrub x3" → "the Voidgrubs"."""
    if name.startswith("Voidgrub"):
        return "the Voidgrubs"
    if name.startswith("Dragon"):
        kind = name.split("(")[-1].rstrip(")") if "(" in name else ""
        return "the " + DRAGONS.get(kind, "Dragon")
    return EPICS.get(name, name)


@functools.cache
def _zones() -> list[dict]:
    """The places on the map, from `zones.json` (drawn and edited with `zone_map.py`). The order is the priority."""
    return json.loads(ZONES.read_text(encoding="utf-8"))["zones"]


def _inside(x: float, z: float, polygon: list[list[float]]) -> bool:
    """Whether the point falls inside the polygon (the ray to the right crosses an odd number of sides)."""
    inside = False
    for (x1, z1), (x2, z2) in zip(polygon, polygon[1:] + polygon[:1]):
        if (z1 > z) != (z2 > z) and x < x1 + (z - z1) / (z2 - z1) * (x2 - x1):
            inside = not inside
    return inside


@functools.cache
def _bushes() -> list[dict]:
    """The bushes from `bushes.json`, each with its name and its polygon."""
    return json.loads(BUSHES.read_text(encoding="utf-8"))["zones"]


def _distance_to(polygon: list[list[float]], x: float, z: float) -> float:
    """How far the point is from the polygon's edge (0 if inside)."""
    if _inside(x, z, polygon):
        return 0.0
    best = math.inf
    for (x1, z1), (x2, z2) in zip(polygon, polygon[1:] + polygon[:1]):
        length = (x2 - x1) ** 2 + (z2 - z1) ** 2
        t = 0.0 if length == 0 else max(0.0, min(1.0, ((x - x1) * (x2 - x1) + (z - z1) * (z2 - z1)) / length))
        best = min(best, math.hypot(x - (x1 + t * (x2 - x1)), z - (z1 + t * (z2 - z1))))
    return best


def bush_at(x: float, z: float) -> str | None:
    """The name of the bush the point is in (or within `BUSH_MARGIN` of its edge), or None. If two fit, the nearest."""
    near = [(d, b["name"]) for b in _bushes() if (d := _distance_to(b["polygon"], x, z)) <= BUSH_MARGIN]
    return min(near)[1] if near else None


def place(x: float, z: float, team: str, bush: bool = True) -> str:
    """The place on the map in words, from the point of view of `team`: "the bot side river", "your jungle (top
    side)", "top lane"… It comes from the zones in `zones.json`: the first that contains the point. A zone with a side is said
    "your …" for their team and "the enemy …" for the other. If the point is in a named bush (`bushes.json`) it goes first and
    the zone after: "the Banana bush in the bot side river". With `bush=False`, the zone only."""
    zone_ = "the map"
    is_ = next((q for q in _zones() if _inside(x, z, q["polygon"])), None)
    if is_ is None:  # in a slit between zones: the nearest, if within reach
        d, is_ = min(((_distance_to(q["polygon"], x, z), q) for q in _zones()), key=lambda t: t[0])
        is_ = is_ if d <= GAP_MARGIN else None
    if is_ is not None:
        zone_ = (is_["name"] if is_["side"] is None else
                 f"{'your' if (is_['side'] == 'blue') == (team == '100') else 'the enemy'} {is_['name']}")
    name = bush_at(x, z) if bush else None
    if name is None:
        return zone_
    return f"{name if name.lower().startswith('the ') else 'the ' + name} in {zone_}"


def _row(table: dict[int, dict], t: float, margin: int = 3) -> dict | None:
    """The row of that second, or the nearest one within `margin` that carries a position."""
    for d in range(margin + 1):
        for s in (int(t) - d, int(t) + d):
            f = table.get(s)
            if f and f.get("x"):
                return f
    return None


def _spot(table: dict[int, dict], t: float) -> tuple[float, float] | None:
    f = _row(table, t)
    return (float(f["x"]), float(f["z"])) if f else None


def _num(f: dict | None, column: str) -> float:
    return (M._num(f, column) or 0.0) if f else 0.0


def _value(c: dict | None, team: str, starts: float, ends: float) -> tuple[int | None, int | None, float | None]:
    """(their team's WP before and after, in %, and the change in neutral WP points), with the 5 s windows of
    `value.annotate`; (None, None, None) without a curve or outside it."""
    if c is None:
        return None, None, None
    before, after = V._windows(c, [starts], [ends])
    a, d = float(before[0, 0]), float(after[0, 0])
    if math.isnan(a) or math.isnan(d):
        return None, None, None
    s = 1.0 if team == "100" else -1.0
    return round(100 / (1 + math.exp(-s * a))), round(100 / (1 + math.exp(-s * d))), round(s * V.NEUTRAL * (d - a), 1)


def _wp(c: dict | None, team: str, t: float) -> float | None:
    """Their team's WP at that second (0-1)."""
    if c is None or not len(c["t"]):
        return None
    i = min(int(c["t"].searchsorted(t)), len(c["t"]) - 1)
    wp = float(c["wp"][i])
    return wp if team == "100" else 1 - wp


def _wp_phrase(before: int | None, after: int | None) -> str:
    return f"Your team's win chance: {before}% → {after}%." if before is not None and before != after else ""


class Game:
    """What is needed at hand from a match to describe its moments: who is who, where each one is
    each second, the kills and the objectives (from Riot's timeline if there is one; otherwise, from the replay itself)."""

    def __init__(self, raw: dict, record: dict | None, champion: str) -> None:
        self.raw, self.events, self.rows = raw, raw["events"], raw["rows"]
        self.curve = raw.get("curve")
        self.table = M._table(self.events, self.rows)
        self.pits = M._pits(self.events)
        self.bases = M._bases(self.rows)
        players = self.events["players"]
        self.me = next(p for p in players if p["champion"].lower() == champion.lower())
        self.champion, self.team, self.position = self.me["champion"], self.me["team"], self.me["position"]
        self.rival_team = "200" if self.team == "100" else "100"
        self.team_of = {p["champion"]: p["team"] for p in players}
        self.champion_of = {p["net_id"]: p["champion"] for p in players}
        self.rival = next((p["champion"] for p in players if p["team"] == self.rival_team
                           and p["position"] == self.position), None)
        self.kills = self._kills(record)
        self.objectives = self._objectives(record)

    def _kills(self, record: dict | None) -> list[dict]:
        """Each kill: (t, victim, killer, assists, bounty). From Riot's timeline, which carries the killer and the bounty;
        without it, from the replay: the killer is the last enemy that hit them and those who hit them in 10 s assist."""
        if record and record.get("events") and record.get("participants"):
            name = {}
            for p in record["participants"]:
                own_side = next((j["champion"] for j in self.events["players"]
                               if j["champion"].lower() == str(p.get("championName", "")).lower()), None)
                own_side = own_side or next((j["champion"] for j in self.events["players"]
                                         if j["team"] == str(p.get("teamId")) and j["position"] == p.get("teamPosition")), None)
                name[p["participantId"]] = own_side
            return [{"t": e["timestamp"] / 1000, "victim": name.get(e.get("victimId")),
                     "killer": name.get(e.get("killerId")),
                     "assists": [name.get(a) for a in e.get("assistingParticipantIds") or [] if name.get(a)],
                     "reward": (e.get("bounty") or 0) + (e.get("shutdownBounty") or 0),
                     "shutdown": e.get("shutdownBounty") or 0}
                    for e in record["events"] if e.get("type") == "CHAMPION_KILL"]
        hits = collections.defaultdict(list)
        for e in self.events["events"]:
            if e["type"] == "Damage" and e.get("source") in self.champion_of and e["net_id"] in self.champion_of:
                hits[self.champion_of[e["net_id"]]].append((e["time"], self.champion_of[e["source"]]))
        out = []
        for e in self.events["events"]:
            if e["type"] == "Death" and e["net_id"] in self.champion_of:
                victim, t = self.champion_of[e["net_id"]], e["time"]
                own_items = [(tt, q) for tt, q in hits[victim] if t - 10 <= tt <= t
                         and self.team_of[q] != self.team_of[victim]]
                killer = own_items[-1][1] if own_items else None
                out.append({"t": t, "victim": victim, "killer": killer,
                              "assists": sorted({q for _t, q in own_items} - {killer}), "reward": None, "shutdown": 0})
        return out

    def _objectives(self, record: dict | None) -> list[dict]:
        """Objectives and turrets that fall: (t, team that takes it, name, place). The epics come from the replay
        (`camps`, with their place and who finishes them); the turrets, from Riot's timeline if there is one."""
        out = []
        for c in self.events["camps"]:
            if c["camp"].startswith("Dragon") or c["camp"] in EPICS:
                team = self.team_of.get(self.champion_of.get(c.get("killer"), ""))
                out.append({"t": c["time"], "team": team, "name": _objective(c["camp"]),
                              "spot": tuple(c["position"]), "epic": c["camp"]})
        for e in (record or {}).get("events") or []:
            if e.get("type") == "BUILDING_KILL" and e.get("buildingType") == "TOWER_BUILDING":
                owner = str(e.get("teamId"))
                lane = {"TOP_LANE": "top", "MID_LANE": "mid", "BOT_LANE": "bot"}.get(e.get("laneType"), "")
                level = {"OUTER_TURRET": "outer", "INNER_TURRET": "inner", "BASE_TURRET": "inhibitor",
                         "NEXUS_TURRET": "nexus"}.get(e.get("towerType"), "")
                p = e.get("position") or {}
                out.append({"t": e["timestamp"] / 1000, "team": "200" if owner == "100" else "100",
                              "name": f"the {lane} {level} turret".replace("  ", " "),
                              "spot": (p.get("x", 0), p.get("y", 0)), "epic": None})
        return sorted(out, key=lambda o: o["t"])

    def where(self, champion: str, t: float) -> tuple[float, float] | None:
        return _spot(self.table.get(champion, {}), t)

    def place(self, spot: tuple[float, float] | None, bush: bool = True) -> str:
        return place(*spot, self.team, bush) if spot else "an unknown spot"

    @property
    def laning_end(self) -> float:
        """When the laning phase ends: 14:00 as a guide, or earlier if the marksman is already in mid (reference review: the midgame
        starts when the ADC is in mid, not at a fixed time)."""
        if not hasattr(self, "_laning_end"):
            end, waves = LANING_PHASE, self.raw.get("waves")
            if self.position == "BOTTOM" and waves:
                in_mid = lambda t: bool((q := self.where(self.champion, t)) and self.is_alive(self.champion, t) and M._corridor(waves, *q) == "mid")  # noqa: E731
                # reaches mid and stays: most of the following 3 minutes there (a passing roam doesn't start the midgame)
                end = next((t for t in range(480, int(LANING_PHASE) + 1, 10)
                            if sum(in_mid(t + d) for d in range(0, 180, 10)) >= 0.6 * 18), end)
            self._laning_end = float(end)
        return self._laning_end

    def is_alive(self, champion: str, t: float) -> bool:
        f = self.table.get(champion, {}).get(int(t))
        return bool(f) and f["alive"] == "True"

    def activity(self, since: float, until: float) -> list[tuple[str, int]]:
        """What they did in those seconds, from most to least time: ("dead", 28), ("top lane", 70)…"""
        count: collections.Counter = collections.Counter()
        base = self.bases.get(self.team)
        for s in range(int(since), int(until) + 1):
            f = self.table.get(self.champion, {}).get(s)
            if not f or not f.get("x"):
                continue
            if f["alive"] != "True":
                count["dead"] += 1
                continue
            spot = (float(f["x"]), float(f["z"]))
            count["in base" if base and math.dist(spot, base) < BASE else f"in {self.place(spot, bush=False)}"] += 1  # by zones: a bush splits the time into meaningless pieces
        return count.most_common()

    def earns(self, since: float, until: float) -> list[str]:
        """What they get in those seconds: their kills and assists, and their team's objectives and turrets."""
        kills, assists = [], []
        for k in self.kills:
            if since <= k["t"] <= until and self.team_of.get(k["victim"]) == self.rival_team:
                if k["killer"] == self.champion:
                    kills.append(k["victim"])
                elif self.champion in k["assists"]:
                    assists.append(k["victim"])
        out = [f"{len(v)} {what}{'s' if len(v) > 1 else ''} ({_list(sorted(set(v)))})"
                 for v, what in ((kills, "kill"), (assists, "assist")) if v]
        return out + [o["name"] for o in self.objectives if since <= o["t"] <= until and o["team"] == self.team]


def _moment(p: Game, t: float, spot, kind: str, tone: str, severity: int, title: str, text: str,
             **extra) -> dict:
    x, z = spot if spot else (None, None)
    return {"t": round(t, 1), "clock": _clock(t), "x": None if x is None else round(x), "z": None if z is None else round(z),
            "kind": kind, "tone": tone, "severity": int(max(1, min(3, severity))), "title": title, "text": text.strip(),
            "where": p.place(spot) if spot else None} | ({"zone": p.place(spot, bush=False), "bush": bush_at(*spot)} if spot and bush_at(*spot) else
                                                           {"zone": p.place(spot, bush=False)} if spot else {}) | {k: v for k, v in extra.items() if v is not None}


def deaths(p: Game) -> list[dict]:
    """Each of their deaths, with what explains it: whether they saw who killed them, the fight they were in, the gold they
    gave away, the dead time and what the enemy took meanwhile."""
    out = []
    net = p.me["net_id"]
    gold_per_second = _production(p)
    for e in p.events["events"]:
        if e["type"] != "Death" or e["net_id"] != net:
            continue
        t, dead = e["time"], e["respawn_time"]
        spot = p.where(p.champion, t - 1) or p.where(p.champion, t)
        kill = min((k for k in p.kills if k["victim"] == p.champion and abs(k["t"] - t) < 3),
                   key=lambda k: abs(k["t"] - t), default=None)
        killer = kill["killer"] if kill else None
        assists = kill["assists"] if kill else []
        sighted = M._visible(p.rows, killer, t - 3, 7) if killer and p.team_of.get(killer) else None
        context = M.context(p.rows, p.champion, t)
        fight = next((f for f in p.raw["fights"] if p.champion in f["who"] and f["since"] - 1 <= t <= f["until"] + 3),
                     None)
        losers = [o for o in p.objectives if t <= o["t"] <= t + dead + 10 and o["team"] == p.rival_team]
        before, after, value = _value(p.curve, p.team, t, t)
        labels, phrases = [], []

        who = _list([killer, *assists]) if killer else "The enemy"
        phrases.append(f"{who} killed you in {p.place(spot)} at {_clock(t)}.")
        if sighted == 0:
            labels.append("no vision")
            phrases.append(f"You never saw {killer} coming: your team hadn't had eyes on them in the 7 seconds before.")
        deficit = 0
        if fight:
            own_items, own_rival = fight[f"champions_{p.team}"], fight[f"champions_{p.rival_team}"]
            deficit = fight[f"gold_{p.rival_team}"] - fight[f"gold_{p.team}"]
            if own_items < own_rival:
                labels.append("outnumbered")
            if deficit >= 1000 and own_items >= own_rival:
                labels.append("item deficit")
            phrase = f"It was a {own_items}v{own_rival}"
            if deficit >= 1000 and own_items >= own_rival:  # with fewer people, the gold deficit is already in the count
                phrase += f" with your side {deficit:,.0f} gold behind in items"
            phrases.append(phrase + ".")
        elif (near := context.get("nearest_ally")) is None or near > 2000:
            labels.append("alone")
            phrases.append("No teammate was close enough to help.")
        gift = kill["reward"] if kill else None
        parts = []
        if gift:
            parts.append(f"gave {gift:,} gold" + (" (a shutdown)" if kill["shutdown"] else ""))
        parts.append(f"spent {_duration(dead)} dead (about {gold_per_second * dead:,.0f} gold of farm lost)")
        phrases.append("You " + " and ".join(parts) + ".")
        if losers:
            labels.append("objective lost")
            phrases.append(f"While you were dead they took {_list([o['name'] for o in losers])}.")
        # not spent: ready one second before and one second after (a Flash used in the fight itself doesn't count), and without the Smite
        my_row, spells = p.table[p.champion], next(s for q, s in zip(p.events["players"], p.events["stats"], strict=True) if q["champion"] == p.champion)
        ready = sum(my_row.get(int(t) - 1, {}).get(k) == "True" and my_row.get(int(t) + 1, {}).get(k) == "True"
                     for k, gap in (("d_ready", "SUMMONER_SPELL_1"), ("f_ready", "SUMMONER_SPELL_2")) if spells.get(gap) != "11")
        if ready:
            labels.append("summoners up")
            phrases.append(f"You died with {'both summoner spells' if ready == 2 else 'a summoner spell'} still up: resources you "
                          "didn't use.")
        # an enemy who came out of the fog: how long they had gone unseen before appearing, and how many seconds they were seen coming
        if "no vision" not in labels:
            leaving = {c: _from_the_fog(p, c, t) for c in {killer, *assists} if c and p.team_of.get(c) == p.rival_team}
            if leaving and leaving[(worst := max(leaving, key=lambda c: leaving[c][0]))][0] >= 20:
                hidden, visible = leaving[worst]
                labels.append("unseen enemy")
                phrases.append(f"Nobody on your team had seen {worst} for {_duration(hidden)}, until it came out of the fog "
                              f"{_duration(visible)} before it killed you." if visible >= 3 else
                              f"Nobody on your team had seen {worst} for {_duration(hidden)} before it came out on you.")
        if bad_ := _bad_wave(p, t, spot):
            labels.append("bad wave state")
            phrases.append(bad_)
        elif p.position in ("TOP", "MIDDLE", "BOTTOM") and t <= LANING_PHASE and spot and _own_crash(p, M.LANES[p.position], t) and not any(
                e["type"] == "AddBuff" and e["buff"].lower() == "recall" and e["net_id"] == net and t - 20 <= e["time"] <= t
                for e in p.events["events"]):
            labels.append("overstay")
            phrases.append("Your wave was pushing into their tower: that is your recall timer. You stayed in the lane instead of "
                          "recalling straight away.")
        unspent = _num(_row(p.table[p.champion], t - 10), "gold")
        if unspent >= 1500:
            labels.append("unspent gold")
            phrases.append(f"You were carrying {unspent:,.0f} unspent gold.")
        if value is not None and value < 0:
            phrases.append(_wp_phrase(before, after))
        elif value is not None and value > 0:
            phrases.append("The fight around it still went your team's way.")
        title = ("Caught without vision" if {"no vision", "unseen enemy"} & set(labels) else "Fought outnumbered" if "outnumbered" in labels
                  else "Fought behind on items" if "item deficit" in labels else "Caught alone" if "alone" in labels
                  else "Died")
        loses = -(value or 0)
        severity = 1 + (loses >= 3) + (loses >= 6 or bool(losers))
        if before is not None and before < 10:  # with the game already decided, one more death teaches little
            severity = 1
        out.append(_moment(p, t, spot, "death", "bad", severity, title, " ".join(phrases), gold=-(gift or 0) or None,
                              wp_before=before, wp_after=after, value=value, tags=labels, killer=killer,
                              dead_for=round(dead)))
    return out


def _from_the_fog(p: Game, champion: str, t: float, cap: int = 300) -> tuple[int, int]:
    """(seconds their team had gone without seeing them before they appeared, seconds they are seen up to `t`): the enemy who comes out of the fog
    and kills. If they were never seen in `cap`, the first is `cap`."""
    cap = min(cap, int(t))  # at the start of the game one doesn't go unseen longer than the game has lasted
    table = p.table.get(champion, {})

    def sighted(s_: int) -> bool:
        return bool((f := table.get(s_)) and f.get("seen") == "True" and f.get("alive") == "True")

    end = int(t)
    while end > t - cap and not sighted(end):
        end -= 1
    if not sighted(end):
        return cap, 0
    start_ = end
    while sighted(start_ - 1):
        start_ -= 1
    before = start_ - 1
    while before > t - cap and not sighted(before):
        before -= 1
    return (start_ - before if sighted(before) else cap), int(t) - start_


def _own_crash(p: Game, lane: str, t: float, before: float | None = None) -> tuple[float, float] | None:
    """(first, last) second in which their minions die in the enemy turret's range, if `t` falls within that stretch or in the
    `AT_CRASH` s before (the wave is going toward it: hard-pushed) or after. At least 3 of their minions dying there count, whoever
    finishes them: the turret doesn't always get to kill three."""
    waves = p.raw.get("waves")
    if not waves:
        return None
    side, rival = ("blue", "red") if p.team == "100" else ("red", "blue")
    tower = OUTER_TOWER[(lane, rival)]
    ts = sorted(x["died"] for x in waves["minions"].values() if x["lane"] == lane and x["side"] == side and x.get("where")
                and math.dist(tuple(x["where"]), tower) <= CRASH_RANGE)
    groups, current = [], []
    for x in ts:
        if current and x - current[-1] > 20:
            groups.append(current)
            current = []
        current.append(x)
    groups.append(current) if current else None
    prior_ = AT_CRASH if before is None else before
    return next(((g[0], g[-1]) for g in groups if len(g) >= 3 and g[0] - prior_ <= t <= g[-1] + AT_CRASH), None)


def _bad_wave(p: Game, t: float, spot: tuple[float, float] | None) -> str | None:
    """The phrase "you moved with the wave in a bad state" if, at `MOVE` units or more from their turret, their wave wasn't crashed
    under the enemy turret (reference review: always suboptimal). None if they were near their turret or the wave was crashed."""
    if p.position not in ("TOP", "MIDDLE", "BOTTOM") or not spot or t > p.laning_end:
        return None  # after 14:00 a lane's wave no longer rules (and crashes are only measured in the laning phase)
    lane, side = M.LANES[p.position], ("blue" if p.team == "100" else "red")
    far = math.dist(spot, OUTER_TOWER[(lane, side)])
    if far < MOVE or _own_crash(p, lane, t):
        return None
    return (f"You were {far:,.0f} units from your tower with your wave not crashed under theirs: moving with the wave in a bad "
            "state is always suboptimal.")


def _production(p: Game) -> float:
    """The gold they earn per living second in the match: what they stop earning each second they are dead."""
    own_rows = [f for f in p.rows.get(p.champion, []) if f.get("total_gold")]
    is_alive = sum(1 for f in own_rows if f["alive"] == "True")
    if not own_rows or not is_alive:
        return 0.0
    return (_num(own_rows[-1], "total_gold") - _num(own_rows[0], "total_gold")) / is_alive


def camps(p: Game) -> list[dict]:
    """Each stretch in which their small camps were alive without being cleared in the laning phase (merging those
    that overlap), with each one's gold and XP measured in the match, what they were doing meanwhile and whether they got something
    that made up for it."""
    idle = p.raw["idle"].get(p.champion)
    if not idle or p.position != "JUNGLE":
        return []
    period = idle["period"]
    windows = sorted((a, b, d["camp"], d["gold_camp"], d.get("xp_camp", 0.0))
                      for d in idle["detail"] for a, b in d["windows"] if b - a >= 10)
    groups: list[list] = []
    for v in windows:
        if groups and v[0] <= groups[-1][1]:
            groups[-1][1] = max(groups[-1][1], v[1])
            groups[-1][2].append(v)
        else:
            groups.append([v[0], v[1], [v]])
    out = []
    spots = {c["camp"]: tuple(c["position"]) for c in p.events["camps"]
              if c["camp"] in CAMPS and c["side"] == ("blue" if p.team == "100" else "red")}
    plays_ = [x for x in _own(p) if x["camps"]]
    for a, b, parts in groups:
        gold = sum((end - start_) / period * o for start_, end, _c, o, _x in parts)
        xp = sum((end - start_) / period * x for start_, end, _c, _o, x in parts)
        if gold < 40:
            continue
        # the stretch already counted by a play (`plays`) doesn't come out again as stalled camps
        if sum(max(0.0, min(b, x["end"]) - max(a, x["start"])) for x in plays_) >= 0.5 * (b - a):
            continue
        names = sorted({c for _a, _b, c, _o, _x in parts})
        what = p.activity(a, b)
        doing = _list([f"{_duration(s)} {where}" for where, s in what[:2]])
        gets = p.earns(a, b + 8)
        spot = p.where(p.champion, (a + b) / 2) or spots.get(names[0])
        price = _list([f"{CAMPS[c]} {next(o for _a, _b, cc, o, _x in parts if cc == c):.0f} g" for c in names])
        until = f"{_clock(a)} to at least 14:00" if b >= LANING_PHASE - 1 else f"{_clock(a)} to {_clock(b)}"
        text = (f"Your {_list(names)} stood up uncleared for {_duration(b - a)} ({until}): "
                 f"about {gold:,.0f} gold and {xp:,.0f} XP you never got back ({price} per clear). "
                 f"Meanwhile you spent {doing}.")
        if gets:
            text += f" That time got you {_list(gets)}, so the detour paid for itself."
        elif what and what[0][0] == "dead":
            text += " Dying is what left them standing."
        else:
            text += " It produced nothing: no kill, no assist, no objective."
        severity = 1 if gets else 1 + (gold >= 120) + (gold >= 220)
        out.append(_moment(p, a, spot, "camps", "neutral" if gets else "bad", severity,
                              f"{len(names)} camp{'s' if len(names) > 1 else ''} left standing" if not gets
                              else "Camps traded for a play", text, gold=-round(gold), end=round(b, 1),
                              camps=names, camp_spots=[list(spots[c]) for c in names if c in spots]))
    return out + thefts(p, idle)


def _streaks(items: list[dict], gap: float = 45.0) -> list[list[dict]]:
    """Thefts (or invasions) one by one, merging those falling within `gap` seconds: they are cleared
    in a row, two or three camps of the same pass."""
    streaks: list[list[dict]] = []
    for r in sorted(items, key=lambda r: r["t"]):
        if streaks and r["t"] - streaks[-1][-1]["t"] <= gap:
            streaks[-1].append(r)
        else:
            streaks.append([r])
    return streaks


def thefts(p: Game, idle: dict) -> list[dict]:
    """Their camps that the enemy took (their gold is the other's, even if the camp wasn't stalled) and
    the enemy's that they took, in the laning phase."""
    side = "blue" if p.team == "100" else "red"
    spots = {(c["camp"], c["side"]): tuple(c["position"]) for c in p.events["camps"] if c["camp"] in CAMPS}
    out = []
    for streak in _streaks(idle.get("thefts", [])):
        a, b = streak[0]["t"], streak[-1]["t"]
        gold = sum(r["gold"] for r in streak)
        who = _list(sorted({r["who"] for r in streak}))
        names = [r["camp"] for r in streak]
        what = p.activity(a - 20, b + 5)
        text = (f"{who} took your {_list(names)} at {_clock(a)}: {gold:,.0f} gold that went to them instead of "
                 f"you, and a camp they take is one you can't clear for another two minutes.")
        if what:
            text += f" You were {what[0][0]} at the time."
        text += (" Ward your jungle entrances on the side you're not on, or clear the camps they're heading to "
                  "before they get there.")
        out.append(_moment(p, a, spots.get((names[0], side)), "camps", "bad", 1 + (gold >= 150) + (len(streak) >= 3),
                              f"{len(streak)} camp{'s' if len(streak) > 1 else ''} stolen", text, gold=-round(gold),
                              end=b if b > a else None, camps=names,
                              camp_spots=[list(spots[(c, side)]) for c in names if (c, side) in spots]))
    rival = "red" if side == "blue" else "blue"
    for streak in _streaks(idle.get("invasions", [])):
        a = streak[0]["t"]
        gold = sum(r["gold"] for r in streak)
        names = [r["camp"] for r in streak]
        text = (f"You took their {_list(names)} at {_clock(a)}: +{gold:,.0f} gold for you and gold their jungler "
                 "won't get. Invading when you know where they are is how junglers that win get ahead on farm.")
        out.append(_moment(p, a, spots.get((names[0], rival)), "camps", "good", 1 + (gold >= 150),
                              "Invaded their jungle", text, gold=round(gold), camps=names,
                              camp_spots=[list(spots[(c, rival)]) for c in names if (c, rival) in spots]))
    return out


SHOW_UP = 5  # seconds in view with an enemy laner in range for showing yourself without getting anything to be a moment


GAINS = (("kills", "killed"), ("burns", "burned"), ("their wave advances", "your wave pushed"),
        ("goes back to base", "went back to base"), ("retreats", "backed off"), ("falls", "took"),
        ("the wave of", "the wave in"), ("advances in their favour", "pushed your way"), ("ward at", "a ward"),
        ("from the river", "past the river"))


def _gains_txt(wins: list[str]) -> list[str]:
    """What a play gets (`moments.show_up` and `moments.departures`), in English."""
    out = []
    for g in wins:
        for raw, text in GAINS:
            g = g.replace(raw, text)
        out.append(g)
    return out


def fog(p: Game) -> list[dict]:
    """Each time they show themselves in a lane in the laning phase (`moments.show_up`, with an enemy laner in range): those
    that get nothing, which give away the pressure of being in the fog, and those that do (a gank with a kill, a summoner
    burned, the wave or the laner retreating). Times when a ward far from everyone sees them don't come out: they neither pressure
    anyone nor can be asked to get anything."""
    out = []
    plays_ = [x for x in _own(p) if x["camps"]]
    for j in p.raw["show_up"]:
        if j["jungler"] != p.champion:
            continue
        for v in j["windows"]:
            a, b = v["since"], v["until"]
            near = v.get("near") or []
            if not near and not v["wins"]:
                continue
            if any(x["since"] - 5 <= b and a <= x["until"] + 5 for x in plays_):
                continue  # already comes out as a play (`plays`), with what it cost and what it got
            spot = p.where(p.champion, a)
            lasts = b - a + 1
            if not v["wins"] and lasts < SHOW_UP:
                continue  # crossing into view for three seconds isn't showing yourself in a lane
            standing = v.get("standing") or []
            where = p.place(spot) + (f", close enough to threaten {_list(near)} in {v['lane']} lane" if near else "")
            if not v["wins"]:
                text = (f"The enemy saw you in {where} for {lasts} s at {_clock(a)} and nothing came of it: no kill, no "
                         f"summoner spell burned, the wave didn't move and nobody backed off.")
                if standing:
                    text += f" Your {_list(standing)} were up meanwhile."
                text += (" While you are in the fog every lane has to play as if you were next to them; showing up for "
                          "nothing hands that pressure back for free.")
                out.append(_moment(p, a, spot, "fog", "bad", 1 + (lasts >= 15) + bool(standing), "Showed up for nothing",
                                      text, end=float(b)))
            else:
                killed_by = any(g.startswith("kills") for g in v["wins"])
                text = f"Seen in {where} at {_clock(a)} and it paid: {_list(_gains_txt(v['wins']))}."
                if standing:
                    text += f" It cost you the {_list(standing)} meanwhile."
                out.append(_moment(p, a, spot, "gank", "good", 1 + killed_by, "Gank that paid off" if killed_by else "Pressure that worked",
                                      text, end=float(b)))
    return out


def fights(p: Game, own_deaths: list[dict]) -> list[dict]:
    """The fights they were in that changed the match: those their team lost (without theirs if it already comes out
    as a death) and the teamfights they won."""
    died = [m["t"] for m in own_deaths]
    out = []
    for f in p.raw["concepts"]["fights"]:
        if p.champion not in f["who"] or f.get("value_100") in (None, ""):
            continue
        s = 1.0 if p.team == "100" else -1.0
        value = s * f["value_100"]
        before = f["wp_before_100"] if p.team == "100" else 100 - f["wp_before_100"]
        after = f["wp_after_100"] if p.team == "100" else 100 - f["wp_after_100"]
        own_items, rivals = f[f"champions_{p.team}"], f[f"champions_{p.rival_team}"]
        fall, topple = f[f"deaths_{p.team}"], f[f"deaths_{p.rival_team}"]
        deficit = f[f"gold_{p.rival_team}"] - f[f"gold_{p.team}"]
        spot = (f["x"], f["z"])
        credit = dict((c, float(v)) for c, v in (x.split(":") for x in f.get("credit", "").split("|") if ":" in x))
        own_side = credit.get(p.champion)
        if min(before, 100 - before) < 10:  # with the game decided, fights no longer decide anything
            continue
        if (value <= -4 and (fall > topple or (f["teamfight"] and value <= -LOST_FIGHT))
                and not any(f["since"] - 1 <= t <= f["until"] + 3 for t in died) and not _fight_without_committing(p, f["since"])):
            text = f"A {own_items}v{rivals} in {p.place(spot)} at {_clock(f['since'])}: your side lost {fall}, they lost {topple}."
            if (own := _damage_in_fight(p, f["since"])) and p.position == "BOTTOM":
                text += " " + _damage_txt(own[0], own[1])
            back = deficit >= 1000 and own_items >= rivals
            if back:
                text += f" You took it {deficit:,.0f} gold behind in items, and fights that start that far behind are rarely won."
            elif own_items < rivals:
                text += " You were outnumbered from the start."
            text += " " + _wp_phrase(round(before), round(after))
            out.append(_moment(p, f["since"], spot, "fight", "bad", 1 + (value <= -6) + (value <= -10),
                                  "Lost a fight behind on items" if back else "Lost a fight", text,
                                  value=round(value, 1), wp_before=round(before), wp_after=round(after), end=f["until"],
                                  tags=["item deficit"] if back else ["outnumbered"] if own_items < rivals else None))
        elif value >= 6 and topple > fall and (f["teamfight"] or topple >= 2):
            text = (f"A {own_items}v{rivals} in {p.place(spot)} at {_clock(f['since'])}: they lost {topple}, you lost {fall}. "
                     + _wp_phrase(round(before), round(after)))
            if (own := _damage_in_fight(p, f["since"])) and p.position == "BOTTOM":
                text += " " + _damage_txt(own[0], own[1])
            if own_side is not None and own_side > 0:
                text += f" Your own share of that swing: {own_side:+.1f} points."
            out.append(_moment(p, f["since"], spot, "fight", "good", 1 + (value >= 10) + (value >= 15),
                                  "Won the teamfight" if f["teamfight"] else "Won the skirmish", text, value=round(value, 1),
                                  wp_before=round(before), wp_after=round(after), end=f["until"]))
    return out


def swings(p: Game, maximum: int = 3) -> list[dict]:
    """Where their team's WP collapsed (20 points or more in two minutes) coming from 55% or more: what
    "complicated a won game", with what happened in that time and what part was theirs."""
    c = p.curve
    if c is None or len(c["t"]) < 30:
        return []
    t = [float(x) for x in c["t"]]
    wp = [(float(w) if p.team == "100" else 1 - float(w)) for w in c["wp"]]
    candidates = []
    for i in range(0, len(t), 5):
        if wp[i] < 0.55 or sum(wp[max(0, i - 30):i + 1]) / len(wp[max(0, i - 30):i + 1]) < 0.50:
            continue  # a one-moment spike isn't a game that was being won: the lead has to be sustained
        j = max(range(i, min(len(t), i + 121)), key=lambda k: -wp[k])
        if wp[i] - wp[j] >= 0.20:
            candidates.append((wp[i] - wp[j], t[i], t[j], wp[i], wp[j]))
    out, used = [], []
    for _drop, a, b, high, under in sorted(candidates, reverse=True):
        if any(a < y and b > x for x, y in used) or len(used) >= maximum:
            continue
        used.append((a, b))
        own_deaths = [k for k in p.kills if a - 5 <= k["t"] <= b + 5 and p.team_of.get(k["victim"]) == p.team]
        rival_deaths = [k for k in p.kills if a - 5 <= k["t"] <= b + 5 and p.team_of.get(k["victim"]) == p.rival_team]
        fall = [o for o in p.objectives if a - 5 <= o["t"] <= b + 30 and o["team"] == p.rival_team]  # the model runs ahead of what comes
        fight = max((f for f in p.raw["fights"] if a - 5 <= f["since"] <= b), key=lambda f: f["take_part"], default=None)
        own_death = next((k for k in own_deaths if k["victim"] == p.champion), None)
        spot = ((fight["x"], fight["z"]) if fight else p.where(p.champion, own_death["t"]) if own_death else
                 fall[0]["spot"] if fall else p.where(p.champion, a))
        text = f"Your team was at {high:.0%} at {_clock(a)} and fell to {under:.0%} by {_clock(b)}."
        if own_deaths or rival_deaths:
            text += f" In that stretch your team lost {len(own_deaths)} champion{'s' if len(own_deaths) != 1 else ''} and killed {len(rival_deaths)}"
            text += f", and the enemy took {_list([o['name'] for o in fall])}." if fall else "."
        elif fall:
            text += f" The enemy took {_list([o['name'] for o in fall])} without a fight."
        if own_death:
            first = min(own_deaths, key=lambda k: k["t"]) is own_death
            text += f" You died at {_clock(own_death['t'])}" + (", the first to fall." if first else ".")
        elif fight and p.champion not in fight["who"]:
            text += f" You weren't in the main fight: you were in {p.place(p.where(p.champion, fight['since']))}."
        gold = [_team_gold(p, x) for x in (a, b)]
        if None not in gold:
            text += f" Team gold went from {gold[0]:+,.0f} to {gold[1]:+,.0f}."
        out.append(_moment(p, a, spot, "swing", "bad", 3, "Where the game turned" if high >= 0.6 else "Big swing",
                              text, end=b, wp_before=round(high * 100), wp_after=round(under * 100)))
    return out


def _team_gold(p: Game, t: float) -> float | None:
    """Their team's total gold minus the enemy's at that second."""
    total = {"100": 0.0, "200": 0.0}
    for champion, team in p.team_of.items():
        f = _row(p.table.get(champion, {}), t, margin=5)
        if not f:
            return None
        total[team] += _num(f, "total_gold")
    return total[p.team] - total[p.rival_team]


def flashes(p: Game) -> list[dict]:
    """Flashes spent outside teamfights with the next dragon before it comes back (`moments.flashes`)."""
    out = []
    for f in p.raw["concepts"]["flashes"]:
        if f["champion"] != p.champion or not f["suboptimal"]:
            continue
        text = (f"You flashed in a {'fight' if f['use'] == 'skirmish' else 'no-fight situation'} at {_clock(f['time'])} "
                 f"with the next {f['next_objective'].lower()} {_duration(f['seconds_to_objective'])} away: Flash takes "
                 f"{f['cooldown']} s to come back, so you'd reach it without one. Each extra player without Flash at a "
                 "dragon costs about 2 points of chance to take it.")
        out.append(_moment(p, f["time"], p.where(p.champion, f["time"]), "flash", "bad", 1, "Flash spent before a dragon",
                              text))
    return out


# What the wave was like on pressing recall (moments.wave_on_return) and why that makes it good or bad. The
# judgement is by where the wave is at that instant, not by the minions lost afterwards: going back late
# costs CS, but the recall itself is decided earlier.
BACK_WAVE = {
    "crash": "your wave crashing into their tower",
    "frozen": "the wave frozen in your lane",
    "neutral with cannon": "the wave in the middle of the lane and a cannon in it",
    "neutral without cannon": "the wave in the middle of the lane and no cannon in it",
    "pushed in their favour": "your wave pushing into their tower",
    "no resources": "very little mana or health left",
    "picked up under their tower": "the wave just collected under your tower",
    "picked up under their tower with cannon": "a cannon wave just collected under your tower",
}
BACK_WHY = {
    "crash": "That is the free one: their tower eats the wave and the next one takes its time to arrive.",
    "frozen": "A freeze is the one wave you don't leave: going back either breaks it or hands it to them.",
    "neutral with cannon": "The cannon holds the wave there, so it is still waiting for you when you walk back out.",
    "no resources": "Going back to refill is worth more than the wave you leave behind: with an empty bar you "
                    "can't trade or last-hit safely.",
    "pushed in their favour": "You had more minions, so the wave walks into their tower on its own and crashes there: "
                           "pushing before you leave is the right order.",
    "neutral without cannon": "With no cannon the wave rolls on its own into one of the towers and you lose all of it; "
                        "push it in or hold it first.",
    "picked up under their tower": "Collected under your tower the wave resets, so there is nothing to lose by going.",
    "picked up under their tower with cannon": "The bounce after a cannon wave is yours, and it is big: you want to be "
                                        "there to meet it, not walking back from base.",
}


def lane(p: Game) -> list[dict]:
    """Of the laners, the backs that let minions die and the lane departures that got nothing. The support's roams
    go in `roams_support`."""
    out = []
    price = MINION_PRICE
    c = p.raw["concepts"]
    laner = p.position in ("TOP", "MIDDLE", "BOTTOM")  # the lane's CS is not the support's: their departure is the roam
    for b in c["backs"] if laner else []:
        if b["champion"] != p.champion or not b["verdict"]:
            continue
        well = b["verdict"] == "good"
        text = (f"You recalled at {_clock(b['time'])} with {BACK_WAVE[b['wave']]}. " + BACK_WHY[b["wave"]])
        died = any(k["victim"] == p.champion and b["time"] < k["t"] <= b["time"] + 60 for k in p.kills)
        own_ones = [x["time"] for x in c["backs"] if x["champion"] == p.champion]
        cheater = (well and b["time"] == min(own_ones) and b["wave_number"] >= 3 and b["time"] <= 240
                   and b["wave"] in ("crash", "pushed in their favour"))  # only after the 3rd wave
        if cheater:
            text += (" This is the cheater recall: the first recall, right after crashing the third wave. It buys your first "
                      "item (the Cull, for most ADCs) and makes the economy for the second one.")
        released = any(m["tone"] == "good" and m["kind"] == "dive" and b["time"] - 40 <= m["t"] <= b["time"] for m in dive(p))
        if b["cs_lost"] >= 4 and not died and not released:  # dying on the way back, or deliberately letting the wave go, isn't what the recall costs
            text += (f" {b['cs_lost']} minions died in your lane in the next minute (~{b['cs_lost'] * price} "
                      "gold), which is what being late back costs on top.")
        out.append(_moment(p, b["time"], p.where(p.champion, b["time"]), "back", "good" if well else "bad",
                              1 + (not well and b["cs_lost"] >= 8), "Cheater recall" if cheater else "Recalled on the wave" if well else "Recalled on a wave you were leaving behind",
                              text, gold=-b["cs_lost"] * price if not well and b["cs_lost"] else None))
    new_ones = [x["since"] for x in _departures_without_crash(p)] if laner else []
    for s in c["departures"] if laner else []:
        if any(abs(s["since"] - d) < 15 for d in new_ones):
            continue  # already comes out as «Moved with the wave not crashed»
        if s["champion"] == p.champion and not s["wins"] and s["cs_lost"] >= 3:
            text = (f"You left {s['lane']} lane at {_clock(s['since'])} for {_duration(s['until'] - s['since'])} "
                     f"{'without pushing the wave first ' if not s['won'] else ''}and got nothing for it, while "
                     f"{s['cs_lost']} minions (~{s['cs_lost'] * price} gold) died in your lane.")
            out.append(_moment(p, s["since"], p.where(p.champion, s["since"] + 5), "roam", "bad", 1 + (s["cs_lost"] >= 8),
                                  "Left lane for nothing", text, gold=-s["cs_lost"] * price, end=s["until"]))
    return out


# ── The jungle: plays with live camps and camps that go in pairs ──────────────────────────────────────────

def _own(p: Game) -> list[dict]:
    """The plays from `moments.plays` in which they are the jungler and which they choose (not those that enter their jungle)."""
    return [x for x in p.raw.get("plays") or [] if x["jungler"] == p.champion and not x.get("invaded")]


def _cost(x: dict) -> float:
    """What the camps a play leaves alive cost it, in gold (XP, at what it weighs in the model)."""
    return x["gold_cost"] + M.GOLD_PER_XP * x["xp_cost"]


def plays(p: Game) -> list[dict]:
    """Each play they make with their own camps alive (`moments.plays`): what they stopped farming by making it
    against what everyone who took part got out of it, from both teams, and whether it paid for the camps."""
    out = []
    for x in _own(p) if p.position == "JUNGLE" else []:
        # with nothing to farm the play costs them no camps (what happens already comes out in other moments), and passing
        # in view of a lane with a freshly spawned camp isn't leaving it for a play either
        if not x["camps"] or (_cost(x) < 20 and abs(x["value"]) < 300):
            continue
        a = x["since"]
        spot = p.where(p.champion, a)
        base = p.bases.get(p.team)
        if spot and base and math.dist(spot, base) < BASE:  # leaves base: the play is where it happens, not where it leaves from
            k = next((k for k in sorted(p.kills, key=lambda k: k["t"]) if a <= k["t"] <= x["until"] and p.champion in (k["killer"], *k["assists"])), None)
            if k:
                a, spot = k["t"], p.where(p.champion, k["t"]) or spot
        what = ("took " + _list([_objective(o) for o in dict.fromkeys(x["objectives"])]) if x["objectives"] else
               "went for a fight" if "fight" in x["kinds"] else "went for a gank")
        own_items = [(c, v) for c, v in x["involved"].items() if v["team"] == p.team]
        rivals = [(c, v) for c, v in x["involved"].items() if v["team"] != p.team]

        def parts(items) -> str:
            chunks = []
            for c, v in sorted(items, key=lambda cv: -abs(cv[1]["gold"])):
                who = "you" if c == p.champion else c
                if v["gold"]:
                    chunks.append(f"{who} {v['gold']:+,d} g" + (" (died)" if v["died"] else ""))
                elif v["died"]:
                    chunks.append(f"{who} died")
            return _list(chunks[:4]) or "nothing either way"

        text = (f"At {_clock(a)} you {what} in {p.place(spot)} with your {_list(x['camps'])} up "
                 f"({x['gold_camps']:,d} g on the map). Doing the play first pushed those clears back: about "
                 f"{x['gold_cost']:,d} g and {x['xp_cost']:,d} XP you don't get back. What the players involved made of "
                 f"it, against what each would normally farm in that time: {parts(own_items)}"
                 + (f"; on their side, {parts(rivals)}." if rivals else "; nobody on their side was involved."))
        for items, who in ((x["objectives"], "Your team"), (x["objectives_rival"], "They")):
            if items:
                worth = sum(M.OBJECTIVE_GOLD[o] for o in items)
                text += (f" {who} took {_list([_objective(o) for o in dict.fromkeys(items)])} out of it, worth about "
                          f"{worth:,.0f} g in win chance.")
        text += f" Net for your side: {x['net_gold']:+,d} g and {x['net_xp']:+,d} XP"
        text += (f", {x['value']:+,d} g all in with the objective." if x["objectives"] or x["objectives_rival"] else ".")
        # what isn't gold: the summoners they burned and the laners they pushed back by showing themselves (`show_up`)
        also = [g for j in p.raw["show_up"] if j["jungler"] == p.champion for v in j["windows"]
                  if v["since"] <= x["until"] + 5 and v["until"] >= x["since"] - 5 for g in v["wins"]
                  if not g.startswith(("kills", "their wave"))]
        if also:
            text += f" It also got {_list(_gains_txt(list(dict.fromkeys(also))))}, which the gold doesn't price."
        if x["verdict"] == "good":
            text += " The play paid for the camps: worth leaving them."
        elif x["verdict"] == "bad" and x["objectives_rival"]:
            text += " It handed them the objective on top of the farm you skipped."
        elif x["verdict"] == "bad":
            text += (" It cost more than the farm you skipped: with camps up, a play has to give back more than the "
                      "clears it delays.")
        else:
            text += " About even: it neither paid for the camps nor cost much more."
        tone = {"good": "good", "bad": "bad", "even": "neutral"}[x["verdict"]]
        title = {"good": "Play that paid for the camps", "bad": "Play that cost more than the camps",
                  "even": "Play that broke even"}[x["verdict"]]
        ledger = [{"champion": c, "side": "ally" if v["team"] == p.team else "enemy", "gold": v["gold"], "xp": v["xp"],
                  "died": v["died"]} for c, v in x["involved"].items()]
        out.append(_moment(p, a, spot, "play", tone, 1 + (abs(x["value"]) >= 300) + (abs(x["value"]) >= 700),
                              title, text, gold=x["net_gold"], end=x["until"],
                              play={"camps": x["camps"], "camp_gold": x["gold_camps"],
                                    "cost_gold": x["gold_cost"], "cost_xp": x["xp_cost"], "ledger": ledger,
                                    "net_gold": x["net_gold"], "net_xp": x["net_xp"], "value": x["value"],
                                    "kills": x["kills"], "deaths": x["deaths"], "objectives": x["objectives"]}))
    return out


DID = {"died": "you died right after", "goes back to base": "you recalled", "fight": "you went into a fight",
        "objective": "you went to an objective", "other camp": "you moved on to other camps",
        "nothing": "you walked away from them"}


def camp_pairs(p: Game) -> list[dict]:
    """Each time they clear a small camp and leave the one beside it alive (`moments.camp_pairs`): Raptors with Krugs and
    Wolves with Gromp are cleared in the same pass, or from there on they spawn out of sync."""
    own = (p.raw.get("camp_pairs") or {}).get(p.champion)
    if not own or p.position != "JUNGLE":
        return []
    side = "blue" if p.team == "100" else "red"
    spots = {c["camp"]: tuple(c["position"]) for c in p.events["camps"]
              if c["camp"] in CAMPS and c["side"] == side and any(c["position"])}
    out = []
    for r in own["detail"]:
        t, camp, other = r["t"], r["camp"], r["duo"]
        play = next((x for x in _own(p) if x["start"] - 5 <= t + 20 <= x["end"] + 5 or t <= x["since"] <= t + 45), None)
        text = (f"You cleared your {camp} at {_clock(t)} and left the {other} next to them up: {DID[r['did']]}. "
                 f"{camp} and {other} are a pair: cleared in the same pass they respawn together and the next pass finds "
                 "both; split, every later visit to that side of your jungle finds half of it.")
        if r["wait"] is None:
            text += f" The {other} were still standing at 14:00."
        else:
            text += f" You came back for the {other} {_duration(r['wait'])} later."
        paid_off = r["did"] in ("fight", "objective") and play and play["verdict"] == "good"
        if paid_off:
            text += f" The play you left them for paid (about {play['value']:+,d} g for your side), so it was a fair trade."
        elif r["did"] == "goes back to base":
            text += " Clear the pair before you recall: the shop doesn't go anywhere."
        out.append(_moment(p, t, spots.get(other) or p.where(p.champion, t), "pair", "neutral" if paid_off else "bad",
                              1 + (r["wait"] is None or r["wait"] >= 100), f"Left the {other} after {camp}", text,
                              camps=[camp, other], camp_spots=[list(spots[c]) for c in (camp, other) if c in spots]))
    return out


# ── The support: where they open, the roams, and the vision ───────────────────────────────────────────────

BOTLANE = {"crash": "your wave had just crashed into their tower, the safest moment to leave your ADC",
         "pushed": "the bot wave was pushed to their side",
         "neutral": "the bot wave was in the middle of the lane",
         "at their tower": "the bot wave was at your own tower",
         "slowpush rival": "their wave was stacking up and coming at your ADC",
         "freeze rival": "they were holding the wave on their side, so your ADC had to walk past the middle to farm",
         "without marksman": "your ADC wasn't in lane"}
BAD_FOR_MARKSMAN = ("slowpush rival", "freeze rival")  # the two waves with which the marksman isn't left alone


def _death_txt(marksman: str, m: dict) -> tuple[str, bool]:
    """(how the marksman died, whether they exposed themselves): past the middle of their lane is on them; against their turret, not."""
    if m.get("adc_dies") in (None, ""):
        return "", False
    if m["adc_dies_exposed"] and not m["adc_dies_under_tower"]:
        return (f"{marksman} died past the middle of the lane with {m['adc_dies_rivals']} "
                f"enem{'y' if m['adc_dies_rivals'] == 1 else 'ies'} on them. That one is on your ADC: while you are "
                "away the lane has to be played from their own half, even if it costs a few minions."), True
    if m["adc_dies_under_tower"]:
        return (f"{marksman} died at their own tower, with {m['adc_dies_rivals']} "
                f"enem{'y' if m['adc_dies_rivals'] == 1 else 'ies'} on them."), False
    return f"{marksman} died in lane" + (" before you got there." if m["adc_dies_alone"] else " with you there."), False


def support_openings(p: Game, map_, model: dict | None) -> list[dict]:
    """Each time the support leaves base in the laning phase (`openings.departures_of`): how the lane was left for their
    marksman, whether they opened through the middle or went straight down, what Challenger and Grandmaster supports do on a map
    like that and what came out. If the marksman dies, how is looked at: past the middle of their lane means they exposed themselves in
    a window they had to respect, and it doesn't make the opening bad."""
    import openings as A

    if p.position != "UTILITY":
        return []
    sup = (model or {}).get("support")
    marksman = next((j["champion"] for j in p.events["players"] if j["team"] == p.team and j["position"] == "BOTTOM"), "Your ADC")
    out = []
    for s in A.departures_of(map_, "UTILITY", until=A.UNTIL_SUPPORT):
        if s["champion"] != p.champion:
            continue
        t0 = s["leaves"]
        e = A.support_state(map_, p.team, t0) | {"team": p.team, "trigger": s["trigger"]}
        d = A.decision_support(map_, p.champion, t0)
        if d["opens"] not in ("mid", "bot"):
            continue
        r = A.support_result(map_, p.champion, t0)
        prob = A.scores_support(e, sup) if sup else None
        clear = prob is not None and abs(prob - 0.5) >= sup["clear"]
        through_mid = d["opens"] == "mid"
        bad_ = e["botlane_state"] in BAD_FOR_MARKSMAN
        how, exposed = _death_txt(marksman, r)
        died = r["dies_adc_90"] == 1
        text = (f"You left base at {_clock(t0)} ({'after a back' if s['trigger'] == 'back' else 'after respawning'}) and "
                 + ("opened through mid" if through_mid else "walked straight down to bot")
                 + f". When you left, {BOTLANE[e['botlane_state']]}"
                 + (f" ({e['botlane_minions']:+d} minions)" if e["botlane_state"] in ("slowpush rival", "freeze rival") else "") + ". ")
        # the tempo: with which wave they started going back to base (after dying they didn't choose it)
        went_back = A.botlane(map_, p.team, s["arrives"] - 8)["botlane_state"] if s["trigger"] == "back" else None
        if went_back in ("crash", "pushed"):
            text += "You had recalled on a wave pushed into them, which is the tempo for it. "
        elif went_back == "slowpush rival":
            text += "You had recalled while their wave was already stacking up against your ADC. "
        elif went_back == "freeze rival":
            text += "You had recalled with the wave already held on their side. "
        if prob is not None:
            text += (f"Challenger and Grandmaster supports open through mid in {prob:.0%} of maps like this. ")
        taken = []
        if d["wards_60"]:
            taken.append(f"placed {d['wards_60']} ward{'s' if d['wards_60'] > 1 else ''}"
                          + (" (one past the river)" if d["ward_deep_60"] > 0.02 else ""))
        if r["mid_retreats"]:
            taken.append("made their mid back off")
        if r["takes_part_90"]:
            taken.append(f"took part in {r['takes_part_90']} kill{'s' if r['takes_part_90'] > 1 else ''}")
        if taken:
            text += f"In the next minute and a half you {_list(taken)}. "
        if how:
            text += how + " "
        if through_mid:
            if bad_ and died and not exposed:
                tone, severity, title = "bad", 2, "Opened mid on a wave against your ADC"
                text += "With that wave you go to your ADC first: the dive was already coming when you left."
            elif bad_:
                tone, severity, title = "neutral", 1, "Opened mid on a risky wave"
                text += "That wave is the one reason not to open mid; it went unpunished this time."
            elif died and not exposed:
                tone, severity, title = "neutral", 1, "Opened mid, ADC died"
            elif clear and prob < 0.5:
                tone, severity, title = "neutral", 1, "Opened mid where high elo goes to bot"
            else:
                tone, severity, title = "good", 1, "Opened through mid"
                if not how:
                    text += ("That is the opening: renew vision on the way, show yourself in mid, and reach bot when "
                              "the wave comes back.")
        elif bad_ or e["botlane_state"] == "without marksman" or not clear or prob < 0.5:
            tone, severity, title = ("good" if bad_ else "neutral"), 1, "Went straight to your ADC"
            if bad_:
                text += "Right call: with that wave your ADC can't be left alone."
        elif r["takes_part_90"] and not died:
            tone, severity, title = "neutral", 1, "Went straight to bot and it paid"
            text += "The map was open through mid, but going down got you a kill this time."
        else:
            tone, severity, title = "bad", 1, "Walked to bot with the map open through mid"
            text += ("The wave gave you the time: going through mid renews vision, puts pressure on their mid laner "
                      "and still gets you to bot when the wave bounces back.")
        state = {"role": "support", "opens": d["opens"], "prob_mid": None if prob is None else round(prob, 3),
                  "clear": bool(clear), "recalled_on": went_back,
                  "lane": {"state": e["botlane_state"], "wave": e["botlane_wave"], "minions": e["botlane_minions"],
                           "adc_alive": bool(e["adc_alive"]), "adc_in_base": bool(e["adc_in_base"]),
                           "adc_hp": e["adc_health"], "adc_at": e["adc_advance"], "enemies": e["botlane_rivals"]},
                  "mid": {"wave": e["mid_wave"], "enemy_hp": e["mid_health_rival"], "ally_hp": e["mid_health_ally"]},
                  "after": {"adc_died": bool(died), "adc_exposed": bool(exposed), "wards": d["wards_60"],
                            "mid_backed": bool(r["mid_retreats"]), "kills": r["takes_part_90"],
                            "reaches_bot": d["arrives_bot"] if d["arrives_bot"] != "" else None}}
        out.append(_moment(p, t0, p.where(p.champion, t0 + 15), "opening", tone, severity, title, text.strip(),
                              opening=state, tags=["adc exposed"] if exposed else None))
    return out


def roams_support(p: Game, map_) -> list[dict]:
    """Each support roam from the lane (`moments.roams`), judged by the wave it leaves and not only by whether the
    marksman dies: with the wave against (an enemy slow push or a freeze) it is a bad roam; with the wave
    fine, if the marksman dies past the middle of their lane they exposed themselves. With what the roam got
    (`moments.departures`: a kill, a burned summoner, the enemy mid retreating, a deep ward)."""
    import openings as A

    if p.position != "UTILITY":
        return []
    out = []
    departures = [s for s in p.raw["concepts"]["departures"] if s["champion"] == p.champion]
    owner_of = {j["net_id"]: j["team"] for j in p.events["players"]}
    for r in p.raw["concepts"]["roams"]:
        if r["support"] != p.champion:
            continue
        t0, end = r["time"], r["time"] + r["lasts"]
        # a roam is leaving the marksman in the lane to go elsewhere: if they weren't with them there, it is leaving base
        # (that is the opening) and if what they do is go back to base, it isn't either
        base = p.bases[p.team]
        if not any((a := p.where(p.champion, s)) and (b := p.where(r["marksman"], s)) and math.dist(a, b) <= 1500
                   and math.dist(b, base) > A.OUTSIDE for s in range(int(t0) - 20, int(t0))):
            continue
        if any((a := p.where(p.champion, s)) and math.dist(a, base) < A.OUTSIDE for s in range(int(t0), int(t0) + A.A_BASE + 1)):
            continue
        botlane = A.botlane(map_, p.team, t0)
        fall, lost = M._cs_lost(map_.waves, "bot", p.team, t0, end, owner_of) if map_.waves else (0, 0)
        m = A.marksman_death(map_, p.team, p.champion, t0, end + 5)
        how, exposed = _death_txt(r["marksman"], m)
        # what counts as getting something: not a ward at the river's edge nor a nearby crab that falls
        gets = [g for s in departures if s["since"] <= end and s["until"] >= t0 for g in s["wins"]
                if not (g.startswith("ward at") and float(g.split("+")[-1].split("%")[0] if "+" in g else 0) < 10)
                and not (g.startswith("falls") and not any(o in g for o in ("Dragon", "Voidgrub", "Herald")))]
        bad_ = botlane["botlane_state"] in BAD_FOR_MARKSMAN
        where_to = {"mid": "mid", "top": "the top side", "bot": "the bot-side river"}.get(r["to_where"], "the map")
        text = (f"You left {r['marksman']} at {_clock(t0)} to roam to {where_to} for {_duration(r['lasts'])}. When you left, "
                 f"{BOTLANE[botlane['botlane_state']]}. ")
        if gets:
            text += f"The roam got: {_list(_gains_txt(list(dict.fromkeys(gets))))}. "
        if lost >= 3:
            text += f"{r['marksman']} missed {lost} of the {fall} minions that died in bot meanwhile. "
        if how:
            text += how + " "
            if exposed and not bad_:
                tone, severity, title = "neutral", 1, "Good window, your ADC overextended"
            elif bad_:
                tone, severity, title = "bad", 2, "Roamed with the wave against your ADC"
                text += "That wave was the reason to stay: the roam is for when the wave has crashed or is pushing out."
            else:
                tone, severity, title = "bad", 1, "Roam that cost your ADC"
        elif gets and bad_:
            tone, severity, title = "neutral", 1, "Roam that paid on a risky wave"
            text += "It worked, but that wave is the one reason to stay with your ADC: it went unpunished this time."
        elif gets:
            killed_by = any(g.startswith("kills") for g in gets)
            tone, severity, title = "good", 1 + killed_by, "Roam that paid"
        elif bad_:
            tone, severity, title = "bad", 1, "Roamed on a bad wave for nothing"
            text += "Nothing came of it, and that wave is the one reason to stay with your ADC."
        else:
            continue
        out.append(_moment(p, t0, p.where(p.champion, t0 + 10), "roam", tone, severity, title, text.strip(), end=end,
                              tags=["adc exposed"] if exposed else None))
    return out


WARD_WINDOW = {"objective": "objective", "prio": "priority", "reset": "reset", "loose": "none"}
WARD_RISK = {"low": "low", "mid": "medium", "high": "high"}


def wards(p: Game) -> list[dict]:
    """Each ward the support places in the match, to draw them on the map: when and where, of what type, in which
    window (`moments.vision`: setting up an objective, with the wave pushed, on leaving base or none), with what
    risk, how many seconds it showed someone their team wasn't seeing, whether it found the enemy jungler, whether it was swept
    and whether it cost their life."""
    own_entry = next((v for v in p.raw.get("watchers") or [] if v["champion"] == p.champion), None)
    if p.position != "UTILITY" or not own_entry:
        return []
    return [{"t": round(w["when"]), "clock": _clock(w["when"]), "x": w["x"], "z": w["z"], "type": w["kind"],
             "when": WARD_WINDOW[w["moment"]], "risk": WARD_RISK[w["risk"]], "seconds": w["seconds"],
             "jungler": bool(w["to_jungler"]), "swept": bool(w["sweep"]), "lived": round(w["lives"]),
             "died": bool(w["costs_it"] and not w["in_fight"])} for w in own_entry["wards"]]


# Crashing the wave (reference review): the ideal is to crash as many waves together as possible, which buys tempo; but with
# the enemy laner dead (their respawn timers running) it is best to crash right away, so they lose as much as possible.
BEFORE_CLASH = 30  # seconds before the turret starts eating the wave in which it is looked at whether the enemy was dead


def crashes(p: Game) -> list[dict]:
    """A single wave pushed into their turret while the enemy laner is dead (`moments.stacks`): with their respawn timers
    running they can't save it, and crashing right away makes them lose the most. Stacks of several waves are counted by `slowpush`."""
    if p.position not in ("TOP", "MIDDLE", "BOTTOM"):
        return []
    lane, side = M.LANES[p.position], ("blue" if p.team == "100" else "red")
    rivals = [j["champion"] for j in p.events["players"] if j["team"] != p.team and M.LANES.get(j["position"]) == lane]
    out = []
    for c in p.raw["concepts"]["clashes"]:
        if c["lane"] != lane or c["side"] != side or c["ends"] > 840 or c["stack"]:
            continue
        if not any((q := p.where(p.champion, t)) and M._lane(*q) == lane for t in range(int(c["time"]) - 30, int(c["time"]) + 1, 5)):
            continue  # the wave was pushed by someone else (a teammate covering the lane): it isn't theirs
        dead = [r for r in rivals if any(not p.is_alive(r, t) for t in range(int(c["time"]) - BEFORE_CLASH, int(c["time"]) + 1, 5))]
        if not dead:
            continue
        text = (f"You crashed the wave at {_clock(c['time'])} while {_list(dead)} {'was' if len(dead) == 1 else 'were'} dead. "
                 "With their respawn timers running they can't save it: every minion the tower eats is gold and experience they lose, "
                 "so pushing now beats waiting for another wave.")
        out.append(_moment(p, c["time"], p.where(p.champion, c["time"]), "back", "good", 2, "Hard push while they respawn", text))
    return out


# The slow push (reference review): what matters is that the waves join up (3 or 4 minions from one plus the 6 of the next, and if
# a third is added, perfect), not how many minions there are nor what happens around. It gives safe time while it is built, fight potential
# (minions block abilities and a stack hits hard) and, since it takes a while to die under their turret, a window to play the map.
PERFECT_WAVES = 3
MINIONS_PER_WAVE = 3  # live minions for a wave to count in the stack (3 or 4 from the previous one plus the 6 of the next)
STACK_LASTS = 20  # consecutive seconds with 2+ waves together for it to be a stack and not a passing overlap


def slowpush(p: Game) -> list[dict]:
    """Each stretch in which they join several of their own waves in their lane: 2+ waves with `MINIONS_PER_WAVE` or more live minions at once
    for `STACK_LASTS` seconds or more, while someone touches it (minions die in the lane: a stopped wave nobody touches
    isn't being built). It doesn't look at how many minions the enemy has: what matters is the stack."""
    waves = p.raw.get("waves")
    if p.position not in ("TOP", "MIDDLE", "BOTTOM") or not waves:
        return []
    lane, side = M.LANES[p.position], ("blue" if p.team == "100" else "red")
    mine_total = [x for x in waves["minions"].values() if x["lane"] == lane and x["side"] == side]

    def joined(t: float) -> int:
        alive = collections.Counter(x["wave"] for x in mine_total if x["spawned_at"] <= t < x["died"])
        return sum(n >= MINIONS_PER_WAVE for n in alive.values())

    periods, opened = [], None
    for t in range(120, int(LANING_PHASE) + 1, 5):
        n = joined(t) if M._advance(waves, lane, t) is not None else 0  # without deaths around, nobody touches the wave: nothing is built
        if n >= 2:
            opened = opened or {"since": t, "until": t, "max": n, "peak": t}
            opened["until"] = t
            if n > opened["max"]:
                opened["max"], opened["peak"] = n, t
        elif opened and t - opened["until"] > 10:  # a 10 s gap doesn't cut the stack
            periods.append(opened)
            opened = None
    if opened:
        periods.append(opened)
    clashes = [c for c in p.raw["concepts"]["clashes"] if c["lane"] == lane and c["side"] == side]
    out = []
    for a in periods:
        if a["until"] - a["since"] < STACK_LASTS:
            continue
        if not any((q := p.where(p.champion, t)) and M._lane(*q) == lane for t in range(a["peak"] - 15, a["peak"] + 16, 5)):
            continue  # the stack was being built by another (a teammate covering the lane)
        clash = next((c["time"] for c in clashes if a["since"] - 10 <= c["time"] <= a["until"] + 30), None)
        ends = f" It crashed into their tower at {_clock(clash)}." if clash else ""
        text = (f"You built a slow push of {a['max']} waves between {_clock(a['since'])} and {_clock(a['until'])}.{ends} A slow "
                 "push gives you safe time while you build it, fight potential (the minions block skills and a stack hits hard) and, "
                 "because that many minions take longer to die under their tower, a window to make a play: dive, roam, recall, drake "
                 "or invade." + (" Three waves is the best you can build." if a["max"] >= PERFECT_WAVES else
                                 " Adding the next wave to it would make it perfect."))
        out.append(_moment(p, a["peak"], p.where(p.champion, a["peak"]), "back", "good", 3 if a["max"] >= PERFECT_WAVES else 2,
                              f"Slow push of {a['max']} waves", text, end=a["until"]))
    return out


# Taking the first turret (reference review): the marksman moves to mid, whatever the minute; staying to push the second
# alone, with no information, costs more than it gives.
AFTER_TOWER = 120  # seconds after the first turret falls in which it is looked at where they play


def first_tower(p: Game) -> list[dict]:
    """For the marksman: where they play in the two minutes after their team takes the first enemy outer bot turret."""
    if p.position != "BOTTOM":
        return []
    fall = min((a for a in p.raw.get("sieges") or []
                 if a["team"] == p.rival_team and a["lane"] == "bot" and a["rank"] == "OUTER_TURRET" and a["falls"]),
                key=lambda a: a["until"], default=None)
    if fall is None:
        return []
    t0 = fall["until"]
    zones = [M._lane(*q) for t in range(int(t0), int(t0) + AFTER_TOWER, 2)
             if (q := p.where(p.champion, t)) and math.dist(q, p.bases[p.team]) > 2000]
    if len(zones) < 15:
        return []
    mid, bot = zones.count("mid") / len(zones), zones.count("bot") / len(zones)
    spot = (fall["x"], fall["z"])
    if mid >= 0.4:
        return [_moment(p, t0, spot, "play", "good", 2, "Swapped to mid after the first tower",
                         f"Their bot outer turret fell at {_clock(t0)} and you moved to mid. With the first tower down the side "
                         "lane is done: the game is played in the middle.")]
    if bot >= 0.5:
        return [_moment(p, t0, spot, "play", "bad", 2, "Stayed in bot after the first tower",
                         f"Their bot outer turret fell at {_clock(t0)} and you stayed in the lane for the next two minutes. Once "
                         "the first tower is down, swap to mid whatever the minute: pushing the second tower alone, without "
                         "information, costs more than it gives.")]
    return []


# Freezing the wave (reference review): it is held near your turret with about 4 minions fewer than the enemy (sometimes 3) so that
# they have to go out to farm away from theirs and farm less; there is no need to deny a whole wave. If it can't be held (the
# champion pushes alone, the minions don't arrive) it is released and it becomes a slow push of yours. With the support and the jungler away and without seeing the enemy jungler
# or mid it isn't held blind: like the give up of a stack, it is left.
MIN_FREEZE = 3  # minions fewer than the enemy (normally 4)


def freeze(p: Game) -> list[dict]:
    """Each freeze they hold (`moments.freezes`): what it costs the enemy, and whether they did it without cover."""
    if p.position not in ("TOP", "MIDDLE", "BOTTOM"):
        return []
    lane = M.LANES[p.position]
    jungler, mid = _of(p, p.rival_team, "JUNGLE"), _of(p, p.rival_team, "MIDDLE")
    my_jg, my_sup = _of(p, p.team, "JUNGLE"), _of(p, p.team, "UTILITY")
    out = []
    for c in p.raw["concepts"]["freezes"]:
        if c["lane"] != lane or c["team"] != p.team or p.champion not in c["who"] or c["difference"] < MIN_FREEZE:
            continue
        t0, t1 = c["since"], c["until"]
        where = p.where(p.champion, t0)
        only = where and sum(_far(p, x, t0, where) and not _arrives(p, x, t0) for x in (my_jg, my_sup) if x) == 2
        blind = [x for x in (jungler, mid) if x and _blindly(p, x, t0)]
        died = next((m for m in p.kills if m["victim"] == p.champion and t0 <= m["t"] <= t1 + 10), None)
        lost, source = c["rival_cs_lost"], c["rival_cs"]
        text = (f"You held the wave frozen near your tower from {_clock(t0)} for {_duration(t1 - t0)}, with {c['difference']:.0f} "
                 "fewer minions than them. They had to walk out to farm it, away from their tower"
                 + (f": {lost} of the {source} minions died without them (~{lost * MINION_PRICE} gold)." if lost else "."))
        if only and blind:
            text += (f" Nobody from your side was near and you had no sight of {_list(blind)} for over {NO_INFO:.0f} s: holding "
                      "a freeze blind is how you end up taking the dive. With no cover, give it up.")
        if only and blind and died:  # the death is the freeze's only if they held it without cover and blind; otherwise, it has its own cause
            out.append(_moment(p, t0, where, "dive", "bad", 2, "Died holding a freeze",
                                  text + f" You died at {_clock(died['t'])}.", end=t1))
        elif only and blind:
            out.append(_moment(p, t0, where, "dive", "neutral", 1, "Held a freeze with no cover", text, end=t1))
        else:
            out.append(_moment(p, t0, where, "back", "good", 2, "Held the freeze", text, end=t1))
    return out


# Last hit under tower (reference review): every gold counts (30 g can be the difference between reaching the first item or not), so an enemy wave
# that crashes into your tower is farmed whole: the last hit is optimised and it is predicted when the turret hits. Low importance.
# The map's outer turrets (x, z) and their range: the minions a turret kills die ~600 from it in the measured matches (the range
# is 775; with the margin of the minion's radius, 875). A minion is "under tower" only if it dies inside that circle.
OUTER_TOWER = {("bot", "blue"): (10504, 1029), ("bot", "red"): (13866, 4505), ("mid", "blue"): (5846, 6396),
                  ("mid", "red"): (8955, 8510), ("top", "blue"): (981, 10441), ("top", "red"): (4318, 13875)}
TOWER_RANGE = 875.0
LOST_UNDER_TOWER = 2  # uncollected minions of a crash for it to come out (two are ~30 g)
NEAR_WAVE = 1800.0  # within this of the wave, you are in it and can farm


def crashes_under_tower(p: Game) -> list[dict]:
    """Each enemy wave that falls under their turret in the laning phase (4+ minions): how many enter the turret's range, how many
    they take, how many their teammates take and how many nobody takes. `count` says whether it was theirs to pick up: they were next to it and didn't leave (recall) or
    die; otherwise, `reason` says why it doesn't count (the give up, the recall and the death have their own moment)."""
    waves = p.raw.get("waves")
    if p.position not in ("TOP", "MIDDLE", "BOTTOM") or not waves:
        return []
    lane, blue = M.LANES[p.position], p.team == "100"
    tower = OUTER_TOWER[(lane, "blue" if blue else "red")]
    turrets = {e["net_id"] for e in p.events["events"] if e["type"] == "SetSpell" and "Turret" in (e.get("name") or "")}
    owner_of = {j["net_id"]: j["team"] for j in p.events["players"]}
    per_wave, no_spot = collections.defaultdict(list), collections.defaultdict(list)
    for sub in waves["minions"].values():
        if sub["lane"] != lane or sub["side"] != ("red" if blue else "blue") or sub["died"] > LANING_PHASE:
            continue
        if sub["killed_by"] in turrets or (sub.get("where") and math.dist(tuple(sub["where"]), tower) <= TOWER_RANGE):
            per_wave[sub["wave"]].append(sub)  # finished by the turret, or dies inside its range
        elif not sub.get("where"):
            no_spot[sub["wave"]].append(sub)  # died leaving no position: it belongs to the wave if it dies among those that are under the turret
    out = []
    for n, ms in sorted(per_wave.items()):
        if len(ms) >= 3:
            start_, end = min(x["died"] for x in ms), max(x["died"] for x in ms)
            ms = ms + [x for x in no_spot[n] if start_ - 4 <= x["died"] <= end + 4]
        if len(ms) < 4:
            continue
        t = statistics.median(sub["died"] for sub in ms)
        spots = [tuple(sub["where"]) for sub in ms if sub.get("where")]
        center = (statistics.median(x for x, _z in spots), statistics.median(z for _x, z in spots)) if spots else None
        near = sum(bool(center and p.is_alive(p.champion, s_) and (q := p.where(p.champion, s_)) and math.dist(q, center) <= NEAR_WAVE)
                    for s_ in range(int(t) - 15, int(t) + 6, 5))
        was_going_back = any(e["type"] == "AddBuff" and e["buff"].lower() == "recall" and e["net_id"] == p.me["net_id"]
                     and t - 20 <= e["time"] <= t + 20 for e in p.events["events"])
        died = any(k["victim"] == p.champion and t - 10 <= k["t"] <= t + 10 for k in p.kills)
        reason = "recalled" if was_going_back else "died" if died else "away" if near < 3 else None
        mine_total = sum(sub["farm"] == p.me["net_id"] for sub in ms)
        team = sum(owner_of.get(sub["farm"]) == p.team for sub in ms) - mine_total
        out.append({"t": round(t, 1), "clock": _clock(t), "wave": n, "cannon": bool(waves["waves"].get(
                          (lane, "red" if blue else "blue", n), {}).get("cannon")),
                      "minions": len(ms), "yours": mine_total, "team": team, "lost": len(ms) - mine_total - team,
                      "counts": reason is None, "reason": reason})
    return out


def under_tower(p: Game) -> list[dict]:
    """One moment for each crash under their turret that was theirs to pick up and in which `LOST_UNDER_TOWER` minions or more escaped, with THEIR
    minions and their gold (reference review: that gold decides whether they reach the first item on a recall, and sometimes a fight). The game's
    totals go in `numbers.tower_*`, not in each moment's text."""
    out = []
    for c in crashes_under_tower(p):
        if not c["counts"] or c["lost"] < LOST_UNDER_TOWER:
            continue
        text = (f"A {'cannon ' if c['cannon'] else ''}wave of theirs crashed under your tower at {c['clock']}: {c['minions']} minions entered "
                 f"its range, you took {c['yours']} and {c['lost']} died without anyone on your side collecting them "
                 f"(~{c['lost'] * MINION_PRICE} gold). That gold can be the difference between reaching your first item on a recall or "
                 "not, and between winning a fight or not.")
        out.append(_moment(p, c["t"], p.where(p.champion, c["t"]), "back", "bad", 1, "Minions lost under your tower", text,
                              gold=-c["lost"] * MINION_PRICE))
    return out


# Moving with the wave uncrashed (reference review): any play in which they have to move and their wave isn't crashed under
# their turret is moving with the wave in a bad state, and is always suboptimal. These don't count: the wave a teammate covers, the give up, going back to
# base (the recall has its own rules) nor leaving base after dying or recalling (an opening, not a departure).
MOVE = 2000.0  # units from their own turret beyond which going to a fight is already moving (also inside the lane)
CRASH_RANGE = 1000.0  # one of their minions that dies within this of the enemy turret is in its range (775 plus the minion's margin)
AT_CRASH = 40.0  # seconds before (the wave is going toward their turret) and after (the recall comes free) it crashes
SHORT_DEPARTURE = 5.0  # seconds out of the lane for it to count as a departure


def _departures_without_crash(p: Game) -> list[dict]:
    """The departures from their lane (`moments.departures`) made without having the wave crashed under the enemy turret."""
    if p.position not in ("TOP", "MIDDLE", "BOTTOM"):
        return []
    if hasattr(p, "_without_crash"):
        return p._without_crash
    side = "blue" if p.team == "100" else "red"
    clashes = p.raw["concepts"]["clashes"]
    loose = [m["t"] for m in dive(p) if m["tone"] == "good"]
    recalls = [e["time"] for e in p.events["events"] if e["type"] == "AddBuff" and e["buff"].lower() == "recall" and e["net_id"] == p.me["net_id"]]
    out = []
    for s in M.departures(p.events, p.raw["waves"], p.rows, minimum=SHORT_DEPARTURE):
        a, b = s["since"], s["until"]
        if s["champion"] != p.champion or s["covered"]:
            continue
        if _own_crash(p, s["lane"], a) or any(c["lane"] == s["lane"] and c["side"] == side and c["time"] - 5 <= a <= c["ends"] + M.CRASH_RETURN
                                                   for c in clashes):
            continue
        if any(a - 30 <= t <= a + 10 for t in loose) or any(a - 5 <= t <= b + 15 for t in recalls):
            continue
        if any((q := p.where(p.champion, a - k)) and math.dist(q, p.bases[p.team]) < 2000 for k in (3, 8, 15)):
            continue  # comes from base: it is an opening
        out.append(s)
    p._without_crash = out
    return out


def without_crash(p: Game) -> list[dict]:
    """Each departure to a play with the wave uncrashed at their turret: always suboptimal."""
    out = []
    for s in _departures_without_crash(p):
        a, b = s["since"], s["until"]
        died = next((m for m in p.kills if m["victim"] == p.champion and a <= m["t"] <= b + 10), None)
        text = (f"You left {s['lane']} lane at {_clock(a)} for {_duration(b - a)} ({s['where_to']}) without having your wave crashed "
                 "under their tower. Whenever you have to move and your wave isn't crashed there, you move with the wave in a bad "
                 "state, and that is always suboptimal"
                 + (f": {s['cs_lost']} minions (~{s['cs_lost'] * MINION_PRICE} gold) died in your lane meanwhile." if s["cs_lost"] else ".")
                 + (f" It cost you more: you died at {_clock(died['t'])}." if died else
                    f" What it got you: {_list(s['wins'])}." if s["wins"] else ""))
        out.append(_moment(p, a, p.where(p.champion, (a + b) / 2) or p.where(p.champion, a), "roam", "bad", 2 + bool(died),
                              "Moved with the wave not crashed", text, gold=-s["cs_lost"] * MINION_PRICE or None, end=b))
    return out


# Free damage in lane (reference review, Kaisa 1:29): each ability you don't dodge while farming is health the enemy
# doesn't pay for, and a potion heals 150: a potion advantage is very noticeable in lane. They are many small hits, so it goes as a statistic.
ABILITY = re.compile(r"^[A-Z][A-Za-z]+[QWER](Missile\d*)?$")  # XayahQMissile1, LockeQMissile, QiyanaW...: the passive and the auto don't count
ANSWER = 4.0  # seconds around an ability hit in which, if they hit whoever throws it, it is an exchange and not free damage
POTION = 150  # health a potion heals


def free_damage(p: Game) -> list[dict]:
    """The damage from enemy abilities they take in the laning phase without answering whoever throws them (`Damage` with the ability's name):
    hits (grouping the missiles of one ability), total health and potions that is."""
    if p.position not in ("TOP", "MIDDLE", "BOTTOM"):
        return []
    me = p.me["net_id"]
    rivals = {j["net_id"]: j["champion"] for j in p.events["players"] if j["team"] == p.rival_team}
    dealt_by = collections.defaultdict(list)  # what they hit each enemy with
    received = []
    for e in p.events["events"]:
        if e["type"] != "Damage" or e["time"] > LANING_PHASE:
            continue
        if e["source"] == me and e["net_id"] in rivals:
            dealt_by[e["net_id"]].append(e["time"])
        elif e["net_id"] == me and e["source"] in rivals and ABILITY.match(e.get("spell") or ""):
            received.append(e)
    hits = []  # missiles of the same ability from the same enemy within 1.5 s: a single hit
    for e in sorted(received, key=lambda x: x["time"]):
        if hits and hits[-1]["source"] == e["source"] and e["time"] - hits[-1]["end"] <= 1.5:
            hits[-1]["health"] += e["amount"]
            hits[-1]["end"] = e["time"]
        else:
            hits.append({"t": e["time"], "end": e["time"], "source": e["source"], "health": e["amount"]})
    fights = [f for f in p.raw.get("fights") or [] if p.champion in f["who"] and f["take_part"] >= 5]  # the 2-person pokes are what is measured
    free = [g for g in hits if not any(g["t"] - ANSWER <= t <= g["end"] + ANSWER for t in dealt_by[g["source"]])
              and not any(f["since"] - 2 <= g["t"] <= f["until"] + 2 for f in fights)  # a hit in a fight isn't farming damage
              and not any(k["victim"] == p.champion and g["t"] - 3 <= k["t"] <= g["t"] + 10 for k in p.kills)]
    if not free:
        return []
    health = sum(g["health"] for g in free)
    items = ", ".join(f"{_clock(g['t'])} {g['health']:.0f}" for g in free)
    text = (f"You took {len(free)} hit{'s' if len(free) != 1 else ''} from enemy abilities in lane without answering: {health:.0f} health in total "
             f"(about {health / POTION:.1f} potions). Every hit counts in lane, and a potion heals {POTION}: a potion lead is felt a lot. "
             f"Be more reactive with your movement commands and punish when they go for the last hit: {items}.")
    return [_moment(p, free[0]["t"], p.where(p.champion, free[0]["t"]), "trade", "bad", 1, "Free damage taken in lane", text,
                     hits=[{"t": round(g["t"], 1), "hp": round(g["health"])} for g in free], hp=round(health))]


PROACTIVE_BEFORE = 10.0  # the wave has to be about to crash (not just «heading to it») for it to be a play with its timer
# Proactive play with the wave in a good state (reference review, Kaisa 8:10): with the wave crashed under their turret nothing is lost by leaving,
# and using that time to catch, rotate or force a play is what is looked for.
def proactive_play(p: Game) -> list[dict]:
    """The laner's kills and assists in the laning phase away from their turret with the wave crashed or about to crash."""
    if p.position not in ("TOP", "MIDDLE", "BOTTOM"):
        return []
    lane, side = M.LANES[p.position], ("blue" if p.team == "100" else "red")
    tower = OUTER_TOWER[(lane, side)]
    waves = p.raw.get("waves") or {"minions": {}}
    earliest = min((x["died"] for x in waves["minions"].values() if x["lane"] == lane), default=0.0)  # when the first wave arrives
    out = []
    for k in p.kills:
        if k["t"] > LANING_PHASE or p.team_of.get(k["victim"]) != p.rival_team or p.champion not in {k["killer"], *k["assists"]}:
            continue
        spot = p.where(p.champion, k["t"])
        what = "killed" if k["killer"] == p.champion else "took part in killing"
        if k["t"] < earliest:  # the wave hasn't even arrived: it is the level 1 all-in, not a play with the crash timer
            text = (f"You {what} {k['victim']} at {_clock(k['t'])}, in an all-in as soon as you reached lane, before the first wave "
                     "had arrived. Going in at level 1 is a call on who wins the fight, not on the wave: you took it.")
            out.append(_moment(p, k["t"], spot, "trade", "good", 2, "Level-1 all-in won", text))
            continue
        if not spot or math.dist(spot, tower) < MOVE or not _own_crash(p, lane, k["t"], before=PROACTIVE_BEFORE):
            continue
        text = (f"You used your crash timer to move and {what} {k['victim']} at {_clock(k['t'])}, {p.place(spot)}. With your wave already "
                 "crashing into their tower you lose nothing by leaving, which is what makes it a proactive play with the wave in a "
                 "good state.")
        out.append(_moment(p, k["t"], spot, "play", "good", 2, "Proactive play with the wave in a good state", text))
    return out


# Opening the map (reference review): the ADC wants to open to mid. It is good: it syncs with the team's movements, adapts to the
# enemy and to teammates, and the sooner they are in mid, the better. Opening to a sidelane isn't a rule: it is neutral, with its reasons.
OPENING_OUTSIDE = 2000.0  # units from their base beyond which they have left it
FAR_FROM_BASE = 6000.0  # the lane they reach beyond this from their base is their destination


def adc_opening(p: Game) -> list[dict]:
    """For the marksman: where they open the map each time they leave their base (after dying or recalling): mid, or a sidelane."""
    if p.position != "BOTTOM":
        return []
    base = p.bases[p.team]
    out, inside = [], None  # inside: they were in base the previous second (None until they are seen)
    for t in range(60, int(p.events["game_length"]) - 40):
        q = p.where(p.champion, t)
        if q is None:
            continue
        far = math.dist(q, base) > OPENING_OUTSIDE
        if inside is True and far:
            # the first lane they reach already far from their base: the path from the base passes through other corridors first
            zone = next((z for s_ in range(t + 5, t + 71, 2)
                         if (d := p.where(p.champion, s_)) and p.is_alive(p.champion, s_) and math.dist(d, base) > FAR_FROM_BASE
                         and (z := M._corridor(p.raw["waves"], *d))), None)
            if zone:
                covers = [j["champion"] for j in p.events["players"] if t <= LANING_PHASE and j["team"] == p.team
                         and j["position"] in ("TOP", "MIDDLE") and sum(bool((d := p.where(j["champion"], s_)) and M._lane(*d) == "bot") for s_ in range(t, t + 31, 5)) >= 3]
                if zone == "mid":
                    text = (f"You opened to mid from your base at {_clock(t)}. As an ADC you want to be in mid: you sync with your "
                             "team's moves, adapt to the rival and to your teammates, and the sooner you are in mid the better."
                             + (f" {_list(covers)} covered bot, which left you the mid wave: opening to bot as well would have made "
                                "you both lose a wave instead of one." if covers else ""))
                    out.append(_moment(p, t, p.where(p.champion, t + 20), "play", "good", 2, "Opened to mid", text))
                elif t > LANING_PHASE:
                    flash = next((f for f in p.raw["concepts"]["flashes"] if f["champion"] == p.champion and t <= f["time"] <= t + 60), None)
                    text = (f"You opened to {zone} from your base at {_clock(t)}. It isn't a norm: as an ADC you almost always want to be in "
                             "mid. In a sidelane you are more exposed to a catch, though it frees pressure from that lane to impact mid "
                             "later, which your teammates weren't doing. Collect one wave and go to mid; don't overstay several."
                             + (f" It cost you your Flash at {_clock(flash['time'])}, with the next {flash['next_objective'].lower()} "
                                f"{_duration(flash['seconds_to_objective'])} away." if flash else ""))
                    out.append(_moment(p, t, p.where(p.champion, t + 20), "play", "neutral", 2 if flash else 1,
                                          f"Opened to a sidelane ({zone})", text))
        inside = not far
    return out


# The level 1 ward (reference review): essential. In bot, the lane bush is placed by the marksman or the support;
# the mid looks at where the enemy jungler starts (their half of the river); the jungler covers an entrance or reads the enemy.
INITIAL_WARD = 120.0  # seconds: what is placed right on reaching the lane, before the first wave clash
BOT_BUSH = (12950.0, 2000.0)  # the bottom lane's bush: in 2 matches of 16.20 the level 1 wards land there
BUSH_RADIUS = 800.0


def initial_ward(p: Game) -> list[dict]:
    """The level 1 ward of whoever plays bot, mid or jungle: placed on time and where it should be, or not placed."""
    if p.position not in ("BOTTOM", "UTILITY", "MIDDLE", "JUNGLE"):
        return []
    side = "blue" if p.team == "100" else "red"
    places = {}  # net_id → (second, place) of their first ward
    for e in p.events["events"]:
        if e["type"] == "CastSpell" and e["spell"] in M.WARDS and e["time"] <= INITIAL_WARD:
            places.setdefault(e["net_id"], (e["time"], tuple(e["target"][:2])))
    mine = places.get(p.me["net_id"])
    if p.position == "JUNGLE":
        import jungle as J

        return J.level_1_ward(p, mine)
    if p.position in ("BOTTOM", "UTILITY"):
        duo = [j["net_id"] for j in p.events["players"] if j["team"] == p.team and j["position"] in ("BOTTOM", "UTILITY")]
        in_bush = {n: w for n, w in places.items() if n in duo and math.dist(w[1], BOT_BUSH) <= BUSH_RADIUS}
        if p.me["net_id"] in in_bush:
            t, spot = in_bush[p.me["net_id"]]
            name = bush_at(*spot)
            return [_moment(p, t, spot, "ward", "good", 1, "Level-1 ward in the lane bush",
                             f"You put the level-1 ward in the lane bush{f' ({name})' if name else ''} at {_clock(t)}. It decides whether the lane can be "
                             "contested: the bush is where you drop the aggro of the minions and of the enemy.")]
        if not in_bush:
            return [_moment(p, 60, BOT_BUSH, "ward", "bad", 2, "No ward in the lane bush",
                             "Neither of you put a ward in the lane bush in the first two minutes. It is the one that decides "
                             "whether you can contest the lane: put it as soon as you arrive, and if it isn't you, your "
                             "partner does.")]
        return []
    if mine is None:
        who = ("where their jungler starts" if p.position == "MIDDLE" else
                 "an entrance to your jungle or where their jungler is")
        return [_moment(p, 60, None, "ward", "bad", 2, "No level-1 ward",
                         f"You didn't put a ward in the first two minutes. The level-1 ward is free and shows you {who}.")]
    t, spot = mine
    enemy = M._depth(*spot, side) > 0
    if p.position == "MIDDLE" and not enemy:
        return []  # in their own half it doesn't say where the enemy jungler starts: neither good nor bad
    text = (f"You put the level-1 ward at {_clock(t)} on their side of the river, which shows where their jungler starts."
             if p.position == "MIDDLE" else
             f"You put the level-1 ward at {_clock(t)}: it covers an entrance to your jungle or reads their jungler.")
    return [_moment(p, t, spot, "ward", "good", 1, "Level-1 ward", text)]


def vision(p: Game) -> list[dict]:
    """For the support, what a coach would teach them about their vision (`moments.vision` of the whole match and
    `moments.support_item`): the wards that cost them their life, those that show the enemy jungler, the stretches they walk the
    map with the support item empty and the times they go back to base with wards unplaced."""
    if p.position != "UTILITY":
        return []
    own_entry = next((v for v in p.raw.get("watchers") or [] if v["champion"] == p.champion), None)
    support_item = next((x for x in p.raw.get("support_item") or [] if x["champion"] == p.champion), None)
    out = []
    falls = [e["time"] for e in p.events["events"] if e["type"] == "Death" and e["net_id"] == p.me["net_id"]]
    for w in (own_entry or {}).get("wards", []):
        spot = (w["x"], w["z"])
        # going to ward far from their own (outside a lane, or past the turret line) and dying without coming from a fight
        if (w["costs_it"] and not w["in_fight"] and (w["lane"] is None or w["past_the_lane"])
                and (w["passed"] or w["alone"])):
            count = [f"{w['in_sight']} enem{'y' if w['in_sight'] == 1 else 'ies'} already in sight" if w["in_sight"] else "",
                      "nobody with you" if w["alone"] else "",
                      f"{w['uncounted']} of their players unaccounted for" if w["uncounted"] >= 3 else ""]
            takes = min((m - w["when"] for m in falls if m > w["when"]), default=0)
            text = (f"You went to ward {p.place(spot)} at {_clock(w['when'])}"
                     + (f", with {_list(count)}," if any(count) else "") + f" and died {takes:.0f} s later. No ward is "
                     "worth a death: the deep ones are for when the wave is pushed, a teammate is with you or you know "
                     "where they are.")
            out.append(_moment(p, w["when"], spot, "ward", "bad", 2, "Died placing a ward", text,
                                  ward={"type": w["kind"], "risk": w["risk"], "when": w["moment"]}))
    best_ones: list[dict] = []
    for w in sorted((w for w in (own_entry or {}).get("wards", []) if w["to_jungler"] and w["seconds"] >= 5),
                    key=lambda w: -w["seconds"]):
        if len(best_ones) < 3 and all(abs(w["when"] - o["when"]) > 60 for o in best_ones):
            best_ones.append(w)  # two consecutive wards that see the same thing are the same hit
    for w in best_ones:
        spot = (w["x"], w["z"])
        others = [c for c in w["reveals"] if w["reveals"][c] >= 2]
        text = (f"The ward you placed in {p.place(spot)} at {_clock(w['when'])} showed {_list(others)} for "
                 f"{w['seconds']} s that nobody on your team would have seen. That is what a ward is for: it told your "
                 "lanes where their jungler was.")
        out.append(_moment(p, w["when"], spot, "ward", "good", 1, "Ward that found their jungler", text,
                              ward={"type": w["kind"], "risk": w["risk"], "when": w["moment"], "seconds": w["seconds"]}))
    for a, b in sorted((support_item or {}).get("spans_empty", []), key=lambda ab: ab[0] - ab[1])[:2]:
        if b - a < 75:
            continue
        text = (f"From {_clock(a)} to {_clock(b)} your support item had no wards left and you stayed on the map "
                 f"({_duration(b - a)}). Its charges only come back in the shop, so the next quiet moment is the reset: "
                 "you walk back out with vision for the next play. Higher tiers actually spend more of their time with "
                 "it empty than lower ones, because they spend the charges faster; what they don't do is go back with "
                 "them unspent.")
        out.append(_moment(p, a, p.where(p.champion, a), "ward", "neutral", 1, "On the map with no wards",
                              text, end=float(b)))
    for t, charges in sorted((support_item or {}).get("returns", []), key=lambda tc: -tc[1])[:2]:
        if charges < 2:
            continue
        text = (f"You got back to base at {_clock(t)} with {charges} wards still on your support item. The shop refills "
                 "them anyway: place them before you recall and that vision is on the map while you are away.")
        out.append(_moment(p, t, p.where(p.champion, t - 12), "ward", "bad", 1, "Recalled with wards unused", text))
    return out


# ── From 14 onward: the opening is to the objective ───────────────────────────────────────────────────────

def preparations(p: Game, rows: list[dict]) -> list[dict]:
    """For the jungler and the support, each objective that spawns after 14 (`rows`, theirs from
    `openings.preparations`): whether in the 45 s before they were setting up their zone or elsewhere, and whether they got
    anything there."""
    import openings as A

    out = []
    for f in rows:
        if f["does"] == "reset":
            continue
        t, name = f["leaves"], _objective(f["objective"])
        capitalised = name[0].upper() + name[1:]
        pit = (f["pit_x"], f["pit_z"])
        spot = (f["x"], f["z"]) if f["x"] != "" else pit
        final = ""
        if f["takes_it"] != "" and f["falls_in"] != "" and f["falls_in"] <= 240:
            final = (f" Your team took it {_duration(f['falls_in'])} after it spawned." if f["takes_it"] else
                     f" The enemy took it {_duration(f['falls_in'])} after it spawned.")
        if f["does"] == "prepares":
            if not f["takes_it"]:
                continue
            text = (f"{capitalised} spawned at {_clock(t)} and you were already there: {min(f['in_zone'], A.BEFORE)} of the {A.BEFORE} s before "
                     f"in its area, which is when vision and position around it get decided.{final}")
            out.append(_moment(p, t - A.BEFORE, spot, "setup", "good", 1, f"Set up {name}", text, objective=name,
                                  end=float(t), objective_spot=list(pit)))
            continue
        what = p.activity(t - A.BEFORE, t)
        doing = _list([f"{_duration(s)} {where}" for where, s in what[:2]])
        arrives = ("you never got to the pit area" if f["arrives"] == "" else
                 f"you reached the pit area {-f['arrives']} s after it spawned" if f["arrives"] < 0 else
                 f"you were near the pit for only {f['in_zone']} s of them")
        text = (f"{capitalised} spawned at {_clock(t)}. In the {A.BEFORE} s before you spent {doing}, and {arrives}.")
        if f["gets"]:
            achievement = _list([f"{f['kills']} kill{'s' if f['kills'] > 1 else ''} you took part in" if f["kills"] else "",
                            "a summoner spell burned next to you" if f["burns"] else "", "a turret" if f["tower"] else ""])
            text += f" You got {achievement} there, so being away had a reason.{final}"
            out.append(_moment(p, t - A.BEFORE, spot, "setup", "neutral", 1, f"Away from {name}, for something", text,
                                  objective=name, end=float(t), objective_spot=list(pit)))
        else:
            text += (f" Nothing came of being there.{final} From the minute {A.FROM_OBJECTIVES / 60:.0f} the opening that "
                      f"matters is the objective: {A.BEFORE} s before it spawns you want to be around it, placing vision "
                      "and looking for a pick nearby.")
            loses = f["takes_it"] == 0 and f["falls_in"] != "" and f["falls_in"] <= 120
            out.append(_moment(p, t - A.BEFORE, spot, "setup", "bad", 1 + loses + (loses and f["objective"] == "Baron"),
                                  f"Not at {name}", text, objective=name, end=float(t), objective_spot=list(pit)))
    return out


def series(p: Game, step: int = 30) -> dict:
    """Every `step` seconds: the gold, CS and XP they get over their position's opponent and their team's gold against
    the other's, to draw the match."""
    end = int(p.events["game_length"])
    out: dict[str, list] = {"t": [], "gold": [], "cs": [], "xp": [], "team_gold": []}
    for t in range(0, end + 1, step):
        me = _row(p.table[p.champion], t, margin=5)
        opp = _row(p.table.get(p.rival, {}), t, margin=5) if p.rival else None
        team = _team_gold(p, t)
        out["t"].append(t)
        out["team_gold"].append(None if team is None else round(team))
        for key, columns in (("gold", ("total_gold",)), ("cs", ("cs", "jungle_minions")), ("xp", ("xp",))):
            out[key].append(round(sum(_num(me, k) - _num(opp, k) for k in columns)) if me and opp else None)
    return out


def numbers(p: Game, moment_list: list[dict], series_: dict, before: list[dict] | None = None) -> dict:
    """The match numbers that follow from one to the next: the lead at 10 and 14, the WP at 15, the deaths
    before and after 14; for the jungler, stalled camps, how much they let themselves be seen, the camp pairs
    they break and the plays they make with live camps; for the support, their vision, their roams and where they open; and
    for both, where they are before each objective after 14 (`before`)."""
    def at(key, t):
        i = min(range(len(series_["t"])), key=lambda k: abs(series_["t"][k] - t))
        return series_[key][i] if series_["t"] and abs(series_["t"][i] - t) <= 30 else None

    mine_list = [m for m in moment_list if m["kind"] == "death"]
    out = {"gold_diff_10": at("gold", 600), "gold_diff_14": at("gold", 840), "cs_diff_14": at("cs", 840),
             "xp_diff_14": at("xp", 840), "team_gold_20": at("team_gold", 1200),
             "wp_15": None if (w := _wp(p.curve, p.team, 900)) is None else round(w * 100),
             "deaths_early": sum(m["t"] < LANING_PHASE for m in mine_list), "deaths_late": sum(m["t"] >= LANING_PHASE for m in mine_list),
             "deaths_no_vision": sum(bool({"no vision", "unseen enemy"} & set(m.get("tags", []))) for m in mine_list),
             "fights_lost": sum(m["kind"] == "fight" and m["tone"] == "bad" for m in moment_list) + sum(
                 bool({"outnumbered", "item deficit"} & set(m.get("tags", []))) for m in mine_list)}
    if p.curve is not None and len(p.curve["t"]):
        own_ = [(float(w) if p.team == "100" else 1 - float(w)) for w in p.curve["wp"]]
        out |= {"wp_max": round(max(own_) * 100), "wp_min": round(min(own_) * 100)}
    opens = [m["opening"] for m in moment_list if m["kind"] == "opening"]
    if opens:
        def matches(o: dict) -> bool:
            """Opens where those above would: through the middle or bottom for the support, top or bottom for the jungler."""
            if o.get("role") == "support":
                return (o["prob_mid"] >= 0.5) == (o["opens"] == "mid")
            return (o["prob_top"] >= 0.5) == (o["opens"] == "top")

        clear_ones = [o for o in opens if o.get("clear")]
        out |= {"openings": len(opens), "openings_clear": len(clear_ones), "openings_matched": sum(matches(o) for o in clear_ones)}
        if p.position == "UTILITY":
            out["openings_mid"] = sum(o["opens"] == "mid" for o in opens)
    if before:  # the objectives that spawn after 14 with them on the map (neither dead nor in base)
        decide = [f for f in before if f["does"] != "reset"]
        out |= {"setups": len(decide), "setups_prepared": sum(f["does"] == "prepares" for f in decide),
                  "setups_away": sum(f["does"] == "other spot" and not f["gets"] for f in decide)}
    if p.position == "UTILITY":
        own_entry = next((v for v in p.raw.get("watchers") or [] if v["champion"] == p.champion), None)
        support_item = next((x for x in p.raw.get("support_item") or [] if x["champion"] == p.champion), None)
        roams = [m for m in moment_list if m["kind"] == "roam"]
        if own_entry:
            w = own_entry["wards"]
            out |= {"wards": len(w), "wards_useful": sum(bool(x["reveals"]) for x in w),
                      "ward_info_seconds": sum(x["seconds"] for x in w), "wards_on_jungler": sum(x["to_jungler"] for x in w),
                      "wards_risky": sum(x["risk"] == "high" and not x["in_fight"] for x in w),
                      "wards_swept": sum(x["sweep"] for x in w),
                      "deaths_warding": sum(m["kind"] == "ward" and m["title"] == "Died placing a ward" for m in moment_list)}
        if support_item:
            out |= {"control_wards": support_item["control_placed"], "item_empty_seconds": support_item["empty"],
                      "item_empty_share": None if support_item["empty_share"] is None else round(100 * support_item["empty_share"]),
                      "wards_unused_on_recall": support_item["charges_wasted"], "sweeps": support_item["sweeps"]}
        out |= {"roams": len(roams), "roams_good": sum(m["tone"] == "good" for m in roams),
                  "roams_bad": sum(m["tone"] == "bad" for m in roams),
                  "roams_adc_exposed": sum("adc exposed" in m.get("tags", []) for m in roams)}
    if p.position in ("TOP", "MIDDLE", "BOTTOM"):
        goes_back = [m for m in moment_list if m["kind"] == "back"]
        out |= {"recalls_judged": len(goes_back), "recalls_good": sum(m["tone"] == "good" for m in goes_back)}
        # the laning phase at the two turrets of their lane: the health taken from each (that of the plates and
        # that of the siege go together; the loose plates, with their gold, are in `stats`)
        lane = M.LANES[p.position]
        own_items = [a for a in p.raw.get("sieges") or []
                 if a["lane"] == lane and a["rank"] == "OUTER_TURRET" and a["since"] < LANING_PHASE]
        if own_items:
            out |= {"tower_damage_taken": sum(a["health_lost"] for a in own_items if a["team"] == p.team),
                      "tower_damage_dealt": sum(a["health_lost"] for a in own_items if a["team"] != p.team)}
    if p.position in M.LANES and (cb := [c for c in crashes_under_tower(p) if c["counts"]]):
        out |= {"tower_crashes": len(cb), "tower_minions": sum(c["minions"] for c in cb),
                  "tower_taken": sum(c["yours"] for c in cb), "tower_lost": sum(c["lost"] for c in cb)}
    if p.position in M.LANES:
        # the plates of their lane before 14: the gold that comes in and that which goes out (`moments.plates`)
        mine = M.LANES[p.position]
        own_rows = [x for x in p.raw.get("plates") or [] if x["lane"] == mine]
        if own_rows:
            mine_list = sum(x["team"] == p.rival_team for x in own_rows)
            out |= {"plates_lane": mine_list, "plates_against": len(own_rows) - mine_list,
                      "plate_gold": mine_list * PLATE_GOLD, "plate_gold_against": (len(own_rows) - mine_list) * PLATE_GOLD,
                      "plates_yours": sum(x["champion"] == p.champion for x in own_rows),
                      "plates_given": sum(m["tone"] == "bad" for m in moment_list if m["kind"] == "plate")}
    if p.position == "BOTTOM":
        tower = [m for m in moment_list if m["kind"] == "tower"]
        if tower:
            out |= {"mid_turret_sieges": len(tower),
                      "mid_turret_away": sum(m["tone"] == "bad" for m in tower),
                      "mid_turret_held": sum(m["tone"] == "good" for m in tower)}
    if p.position == "BOTTOM":
        tr = [m for m in moment_list if m["kind"] == "trade"]

        all_ = [v for f in (p.raw.get("fights") or [])
                 if (v := _damage_in_fight(p, f["since"])) and f["take_part"] >= REAL_FIGHT[0]]
        out |= {"trades_won": sum(m["tone"] == "good" for m in tr), "trades_lost": sum(m["tone"] == "bad" for m in tr),
                  "fights_measured": len(all_),
                  "fight_damage": round(statistics.median(v[1] for v in all_), 2) if all_ else None,
                  "fights_carried": sum(v[1] >= MARKSMAN_DAMAGE[1] for v in all_),
                  "fights_silent": sum(v[1] <= MARKSMAN_DAMAGE[0] for v in all_),
                  "dives_taken": sum(m["kind"] == "dive" and m["tone"] == "bad" for m in moment_list),
                  "waves_given_up": sum(m["kind"] == "dive" and m["tone"] == "good" for m in moment_list)}
    if p.position == "JUNGLE":
        idle = p.raw["idle"].get(p.champion) or {}
        j = next((j for j in p.raw["show_up"] if j["jungler"] == p.champion), None)
        out |= {"camp_gold_lost": round(idle.get("gold", 0)), "camp_clears_lost": round(idle.get("clears_lost", 0), 1),
                  "camps_stolen": idle.get("stolen", 0), "camp_gold_stolen": round(idle.get("stolen_gold", 0)),
                  "camps_invaded": idle.get("invade", 0), "camp_gold_invaded": round(idle.get("invade_gold", 0)),
                  "camps_lost": round(idle.get("lost_and_stolen", 0), 1)}
        if j:
            in_lane = [v for v in j["windows"] if v.get("near")]  # with an enemy laner in range (`show_up`)
            out |= {"unseen_share": round(100 * j["invisible"] / max(1, j["invisible"] + j["visible"])),
                      "showups": len(in_lane), "showups_nothing": sum(not v["wins"] for v in in_lane),
                      "ganks_kill": sum(any(g.startswith("kills") for g in v["wins"]) for v in j["windows"])}
        pairs = (p.raw.get("camp_pairs") or {}).get(p.champion)
        if pairs:
            out |= {"pair_clears": pairs["clears"], "pairs_broken": pairs["broken"]}
        own_rows = [x for x in _own(p) if x["camps"]]
        out |= {"plays": len(own_rows), "plays_good": sum(x["verdict"] == "good" for x in own_rows),
                  "plays_bad": sum(x["verdict"] == "bad" for x in own_rows),
                  "plays_value": sum(x["value"] for x in own_rows), "plays_camp_cost": round(sum(_cost(x) for x in own_rows))}
    return out



SIDES = {"top": "top side", "bot": "bot side", "mid": "mid"}


def _half_txt(e: dict, h: str) -> str:
    """One half of the map in a sentence: its camps, its objective and its lane."""
    parts = []
    if e[f"{h}_gold_now"]:
        parts.append(f"{e[f'{h}_gold_now']:.0f} g of your camps up")
    elif e[f"{h}_gold_30"]:
        parts.append(f"{e[f'{h}_gold_30']:.0f} g of camps back within 30 s")
    else:
        parts.append("no camps of yours up")
    objective = _objective(e.get(f"{h}_objective_which") or ("Dragon" if h == "bot" else "Voidgrub"))
    sec = float(e[f"{h}_objective"])
    if sec <= 0:
        parts.append(f"{objective} up")
    elif sec <= 90:
        parts.append(f"{objective} in {sec:.0f} s")
    lane = "top" if h == "top" else "bot"
    alive, health = int(e[f"{lane}_rivals_alive"]), float(e[f"{lane}_health_rival"])
    no_flash = int(e[f"{lane}_no_flash_rival"])
    if alive == 0:
        parts.append(f"their {lane} laners dead")
    elif health < 0.5:
        parts.append(f"their {lane} lane at {health:.0%} HP" + (" and without Flash" if no_flash else ""))
    elif no_flash:
        parts.append(f"{no_flash} of their {lane} laners without Flash")
    return ", ".join(parts)


def _why(e: dict, model: dict, above: bool) -> list[str]:
    """The two features that push most toward the side those above would choose, in words."""
    import openings as A

    w = model["weights"][0][1:]
    z = [(v - m) / sd for v, m, sd in zip(A.vector(e), model["mean"], model["scale"], strict=True)]
    contrib = sorted(((wi * zi if above else -wi * zi), name) for wi, zi, name in zip(w, z, model["features"], strict=True))
    side, other = ("top", "bot") if above else ("bot", "top")
    sec = float(e[f"{side}_objective"])
    wave = float(e[f"{side}_wave"])
    phrases = {
        "gold_30": f"{e[f'{side}_gold_30']:.0f} g of your camps up or back within 30 s on {side} side against "
                  f"{e[f'{other}_gold_30']:.0f} g on {other}",
        "gold_now": f"{e[f'{side}_gold_now']:.0f} g of your camps up on {side} side against {e[f'{other}_gold_now']:.0f} g",
        "gold_rival": f"{e[f'{side}_gold_rival']:.0f} g of their camps up on {side} side to take",
        "crab": f"the {side} scuttle up",
        "objective": _objective(e.get(f"{side}_objective_which") or ("Dragon" if side == "bot" else "Voidgrub"))
                    + (" up" if sec <= 0 else f" spawning in {sec:.0f} s"),
        "rival_touched": f"their {side} laners low ({float(e[f'{side}_health_rival']):.0%} HP)",
        "rival_no_flash": f"{int(e[f'{side}_no_flash_rival'])} of their {side} laners without Flash",
        "priority": (f"your {side} lane under pressure, the wave at your tower" if wave < 0.45 else
                      f"your {side} wave pushed into them, free to move" if wave > 0.55 else ""),
        "rival_seen": (f"their jungler last seen {SIDES.get(e['rival_seen_half'], 'somewhere')} "
                        f"{float(e['rival_seen_ago']):.0f} s before"),
        "rival_clean": f"their jungler clearing {SIDES.get(e['rival_clean'], 'somewhere')}",
        "allies_alive": f"your {side} lane short-handed",
    }
    chosen = [n for c, n in reversed(contrib[-3:]) if c > 0.15 and phrases.get(n)]
    if "gold_30" in chosen and "gold_now" in chosen:  # they say the same thing: the 30 s one stays
        chosen.remove("gold_now")
    return [phrases[n] for n in chosen[:2]]


def openings(p: Game, map_, model: dict | None) -> list[dict]:
    """Each time they leave their base in the laning phase (the jungler): the map at that instant, where they opened and what
    the Challengers and Grandmasters would have done on a map like that (`openings.model`), with what came out in the following
    90 s. After 14 the opening that is looked at is the objective's (`preparations`)."""
    import openings as A

    if p.position != "JUNGLE":
        return []
    out = []
    for s in A.departures(map_):
        if s["jungler"] != p.champion or s["leaves"] >= A.UNTIL_JUNGLE * 60:
            continue
        t0 = s["leaves"]
        e = A.state(map_, p.team, t0) | {"team": p.team}
        d = A.decision(map_, p.champion, t0)
        r = A.result(map_, p.champion, t0)
        if d["opens"] not in ("top", "bot"):
            continue
        prob = A.scores(e, model) if model else None
        own_entry = None if prob is None else (prob if d["opens"] == "top" else 1 - prob)
        clear = prob is not None and abs(prob - 0.5) >= model["clear"]
        well = clear and own_entry >= 0.5
        bad_ = clear and own_entry < 0.5
        first = {"camp": f"your {d['first_which']}", "invasion": f"their {d['first_which']}",
                   "crab": "the scuttle", "objective": d["first_which"], "fight": "a fight"}.get(d["first"], "")
        text = (f"You left base at {_clock(t0)} ({'after a back' if s['trigger'] == 'back' else 'after respawning'})"
                 f" and opened {SIDES[d['opens']]}" + (f", going to {first} first" if first else "") + ". "
                 f"Top side: {_half_txt(e, 'top')}. Bot side: {_half_txt(e, 'bot')}. ")
        if float(e["rival_seen_ago"]) < 2:
            text += f"Their jungler was in sight, {SIDES.get(e['rival_seen_half'], 'somewhere')}, as you left. "
        elif float(e["rival_seen_ago"]) < 60:
            text += f"Their jungler was last seen {SIDES.get(e['rival_seen_half'], 'somewhere')} {float(e['rival_seen_ago']):.0f} s before. "
        else:
            text += "Nobody had seen their jungler for over a minute. "
        if prob is not None:
            above = prob >= 0.5
            best = max(prob, 1 - prob)
            text += (f"Challenger and Grandmaster junglers open {'top' if above else 'bot'} side in {best:.0%} of maps "
                      "like this")
            reasons = _why(e, model, above)
            text += f" ({_list(reasons)})." if reasons else "."
        after = []
        if r["gold_90"] != "":
            after.append(f"you made {r['gold_90']:.0f} gold")
        if r["dies_jungler_90"]:
            after.append("you died")
        if r["objectives_120"]:
            after.append(("your team took " if r["objectives_120"] > 0 else "the enemy took ") +
                           f"{abs(r['objectives_120'])} objective{'s' if abs(r['objectives_120']) > 1 else ''}")
        if after:
            text += f" In the next 90 s {_list(after)}."
        title = (f"Opened {d['opens']} against the map" if bad_ else f"Read the map: opened {d['opens']}" if well
                  else f"Opened {d['opens']} side")
        spot = p.where(p.champion, t0 + 20)
        state = {"top": {k[4:]: e[k] for k in e if k.startswith("top_")},
                  "bot": {k[4:]: e[k] for k in e if k.startswith("bot_")},
                  "mid": {k[4:]: e[k] for k in e if k.startswith("mid_")},
                  "rival": {"seen": e["rival_seen_half"], "ago": e["rival_seen_ago"],
                            "cleared": e.get("rival_clean", "nothing")},
                  "opens": d["opens"], "prob_top": None if prob is None else round(prob, 3), "clear": bool(clear)}
        out.append(_moment(p, t0, spot, "opening", "bad" if bad_ else "good" if well else "neutral",
                              (2 + bool(r["dies_jungler_90"])) if bad_ else 1, title, text,
                              opening=state, first=d["first"],
                              tags=["died after"] if bad_ and r["dies_jungler_90"] else None))
    return out


# ── The marksman ──────────────────────────────────────────────────────────────────────────────────────────
#
# What a marksman hits in a fight, against what one of their teammates hits on average in that same fight (so it doesn't
# matter whether it is a 2v2 or a 5v5). Measured in 12 matches of 16.19: median 1.33 times, quartiles 0.77 and 1.70.
# The other positions, for reference: jungle 1.19, mid 1.15, top 1.02 and support 0.45.
MARKSMAN_DAMAGE = (0.77, 1.70)
NOT_THERE = 250.0  # damage below which, without having taken any, it doesn't count as having been in the fight
LOST_FIGHT = 10.0  # WP points a fight costs for it to be counted as lost even if the same number die on each side (reference review, 14:00)
REAL_FIGHT = (4, 3000.0)  # participants and damage on their side for a fight to count as one
HOW_MANY_DAMAGE, HOW_MANY_TRADES = 4, 6  # the ones that stand out most in each thing; the rest is noise in the list
MIN_TRADE = 0.25  # health bars a trade has to move to be shown
KNOW = 40  # seconds backwards in which it is looked at whether the enemy saw their support leave
NO_INFO = 30.0  # seconds without seeing an enemy: from there on it isn't known where they are
NEAR_DIVE = 2500.0  # within this, their support or jungler can respond to a dive
MID_TOWER = 2800.0  # within this of the mid turret, they are defending it


def _damage_in_fight(p: Game, since: float) -> tuple[float, float, int] | None:
    """(what they hit, how many times that is the average of their teammates in that fight, how many of their teammates were there).

    Each one's damage goes in the unflattened fights (`raw["fights"]`), which is the same list as that of the
    concepts but with `damage` and `taken`; they are matched by the second the fight starts."""
    f = next((x for x in p.raw.get("fights") or [] if x["since"] == since), None)
    if f is None:
        return None
    own_items = [c for c in f["who"] if p.team_of.get(c) == p.team]
    total = sum(f["damage"].get(c, 0) for c in own_items)
    if not own_items or total <= 0:
        return None
    return f["damage"].get(p.champion, 0), f["damage"].get(p.champion, 0) / (total / len(own_items)), len(own_items)


def _damage_txt(own: float, times: float) -> str:
    """Their damage in a fight, with the scale of MARKSMAN_DAMAGE."""
    return (f"You dealt {own:,.0f} damage to champions there, {times:.1f}x what the average player on your side "
            "dealt in that fight (an ADC usually does 1.3x).")


def _seen_ago(p: Game, champion: str, t: float, cap: float = 120.0) -> float | None:
    """Seconds since their team last saw that enemy; None if they haven't been seen in `cap`."""
    table = p.table.get(champion, {})
    for s in range(int(t), max(0, int(t - cap)), -1):
        f = table.get(s)
        if f and f.get("seen") == "True" and f.get("alive") == "True":
            return t - s
    return None


def _blindly(p: Game, champion: str, t: float) -> bool:
    """Whether they haven't been seen for NO_INFO seconds or more. Seeing them right now is `_seen_ago` == 0: that 0 is NOT «not seen»."""
    does = _seen_ago(p, champion, t)
    return does is None or does >= NO_INFO


def _far(p: Game, champion: str | None, t: float, source: tuple[float, float] | None) -> bool:
    """Whether that teammate isn't at hand (dead, elsewhere or unknown)."""
    spot = p.where(champion, t) if champion else None
    return not (spot and source and p.is_alive(champion, t) and math.dist(spot, source) <= NEAR_DIVE)


def _arrives(p: Game, champion: str, t: float, window: int = 30) -> bool:
    """Whether that teammate is at hand at some point in the next `window` seconds: returning to the lane (a recall made
    together), not gone elsewhere."""
    return any(not _far(p, champion, s_, p.where(p.champion, s_)) for s_ in range(int(t), int(t) + window + 1, 5))


def _of(p: Game, team: str, position: str) -> str | None:
    return next((j["champion"] for j in p.events["players"] if j["team"] == team and j["position"] == position), None)


def _without_committing(p: Game, t: dict) -> tuple[int, int] | None:
    """(theirs, the enemies') if, in that trade in their lane, they didn't die, spent no summoner spell and in the fight they were outnumbered by
    them (the trade only counts for those in the lane; the fight, for everyone: the enemy jungler, for example). Not committing to a fight at a
    disadvantage is the right play even if another of their teammates falls; whoever enters without counting on the enemy jungler is the one who pays for it."""
    mine = t["sides"][p.team]
    me = mine["champions"].get(p.champion)
    f = next((x for x in p.raw["concepts"]["fights"] if abs(x["since"] - t["since"]) <= 5 and p.champion in x["who"]), None)
    if not me or not f or p.champion in mine["died"] or me["summoners"]:
        return None
    we, they = f[f"champions_{p.team}"], f[f"champions_{p.rival_team}"]
    return (we, they) if we < they else None


def _fight_without_committing(p: Game, since: float) -> bool:
    """Whether that fight is the trade in their lane in which they didn't commit (`_without_committing`)."""
    lane = M.LANES.get(p.position)
    return any(t["lane"] == lane and abs(t["since"] - since) <= 5 and _without_committing(p, t) for t in p.raw.get("trades") or [])


def trades(p: Game) -> list[dict]:
    """Each exchange of blows in their lane (`moments.trades`), with the verdict the concept asks for: not
    who hit more, but **how each ends up on health, what they spent, how the wave is left and who can go back to
    base**. A trade lost on health that leaves the wave heading toward them is a trade won: they crash it, go to
    base and come back full, and the enemy can't.

    Only for those who farm a lane, and only those that really move health."""
    if p.position not in ("TOP", "MIDDLE", "BOTTOM"):
        return []
    lane = M.LANES[p.position]
    jungler = _of(p, p.rival_team, "JUNGLE")
    accumulations = p.raw["concepts"].get("accumulations") or []
    out = []
    for t in p.raw.get("trades") or []:
        if t["lane"] != lane or t["since"] >= p.laning_end:
            continue  # past the start of the midgame it is a team fight, not a lane trade
        mine, own = t["sides"][p.team], t["sides"][p.rival_team]
        if p.champion not in mine["champions"]:
            continue

        def spending(side: dict) -> tuple[float, list[str]]:
            """(health lost adding up their side, summoner spells they spend)."""
            health = sum(max(0.0, (d["health_before"] or 0) - (d["health_after"] or 0))
                       for d in side["champions"].values() if d["health_before"] is not None)
            return health, [f"{c}'s {i}" for c, d in side["champions"].items() for i in d["summoners"]]

        lose_, mine_total = spending(mine)
        losers, own_items = spending(own)
        if max(lose_, losers) < MIN_TRADE and not mine["died"] and not own["died"]:
            continue  # a poke of autos isn't a trade worth teaching
        # the wave afterwards, in their frame: positive if it goes toward the enemy turret
        wave = t["wave"] if t["wave"] is None else (t["wave"] if p.team == "100" else -t["wave"])
        balance = ((losers - lose_) - 0.3 * (len(mine_total) - len(own_items))
                 - 1.0 * (len(mine["died"]) - len(own["died"])))
        # going back to base comes free if the wave goes toward them and they are the one who ends with less health
        can_ = wave is not None and wave > 0.05 and lose_ > losers
        verdict = "good" if balance >= 0.25 else "bad" if balance <= -0.25 else "even"
        if verdict == "bad" and can_:
            verdict = "even"
        healths = ", ".join(f"{c} {100 * (d['health_after'] or 0):.0f}%"
                          for side in (mine, own) for c, d in side["champions"].items()
                          if d["health_after"] is not None)
        text = (f"A trade in {lane} lane at {_clock(t['since'])}: you took {losers:.1f} health bars off their "
                 f"side and gave up {lose_:.1f} of yours. After it: {healths}.")
        if mine_total or own_items:
            text += f" Summoners spent: {_list(mine_total + own_items)}."
        for side, who in ((mine, "Your side"), (own, "They")):
            if side["died"]:
                text += f" {who} lost {_list(side['died'])}."
        if wave is not None:
            text += (" The wave rolled towards them afterwards." if wave > 0.05 else
                      " The wave rolled back into you afterwards." if wave < -0.05 else " The wave barely moved.")
        if jungler and (does := _seen_ago(p, jungler, t["until"])) is not None:
            text += (" Their jungler was in sight." if does < 2 else
                      f" Nobody had seen their jungler for {_duration(does)}.")
        sides = {p.team: "blue" if p.team == "100" else "red", p.rival_team: "blue" if p.rival_team == "100" else "red"}
        set_up = lambda team: any(a["lane"] == lane and a["side"] == sides[team]  # noqa: E731
                                    and a["since"] - 10 <= t["since"] <= a["until"] + 10 for a in accumulations)
        if verdict == "bad" and set_up(p.rival_team):
            text += (" They were building a slow push toward your tower: you don't trade into it, you last-hit and let it "
                      "stack.")
        elif verdict == "good" and set_up(p.team):
            text += (" You had the slow push: trading now is the right moment, because they can't use their crash to recall "
                      "or roam.")
        numbers = None
        if can_:
            text += (" You came out lower but with the wave going into them: that one pays for itself if you crash "
                      "it and recall, because you come back full and they can't.")
        elif verdict == "bad" and (numbers := _without_committing(p, t)):
            verdict = "without committing"
            fell = f", even though your {_list(mine['died'])} died" if _list(mine["died"]) else ""
            text = (f"A {numbers[0]}v{numbers[1]} in {lane} lane at {_clock(t['since'])}: you never exposed yourself or spent your "
                     f"summoner spells{fell}. Not committing to a fight where you are outnumbered "
                     "is the right play, and the one who goes in without counting their jungler pays for it.")
        elif verdict == "bad":
            text += " Trading into a wave that then comes back at you is how you end up having to take the dive."
        tone = {"good": "good", "bad": "bad", "even": "neutral", "without committing": "good"}[verdict]
        title = {"good": "Trade you won", "bad": "Trade you lost", "even": "Even trade",
                  "without committing": f"Didn't commit to the {numbers[0]}v{numbers[1]}" if numbers else ""}[verdict]
        if verdict == "even":
            continue  # a trade that decides nothing isn't a moment
        out.append((abs(balance), _moment(p, t["since"], p.where(p.champion, t["since"]), "trade", tone,
                                          1 + (abs(balance) >= 0.5) + bool(mine["died"] or own["died"]), title,
                                          text, end=t["until"])))
    return [m for _key, m in sorted(out, key=lambda x: -x[0])[:HOW_MANY_TRADES]]


def damage_in_fights(p: Game, already: list[dict]) -> list[dict]:
    """For the marksman: what they hit in each fight and skirmish, when it stands out from normal.

    The damage is measured against what one of their teammates hits on average in that same fight, not raw: that way a
    2v2 skirmish and a teamfight can be compared. Fights that already come out for another reason (a lost one, a won
    teamfight) aren't repeated: the damage is added to their own text."""
    if p.position != "BOTTOM":
        return []
    done = {m["t"] for m in already}
    under, high = MARKSMAN_DAMAGE
    out = []
    for f in p.raw.get("fights") or []:
        if p.champion not in f["who"] or f["since"] in done:
            continue
        measured = _damage_in_fight(p, f["since"])
        if measured is None or under < measured[1] < high:
            continue
        if not f.get("taken", {}).get(p.champion) and measured[0] < NOT_THERE:
            continue  # they neither hit nor were hit: they just passed by. Hitting little in a fight they weren't in isn't a mistake
        own, times, _how_many = measured
        people, minimum = REAL_FIGHT
        if f["take_part"] < people or own + sum(v for c, v in f["damage"].items()
                                                 if p.team_of.get(c) == p.team and c != p.champion) < minimum:
            continue  # a two-person poke in the lane isn't a fight
        spot = (f["x"], f["z"])
        well = times >= high
        how_many = f"{f[f'champions_{p.team}']}v{f[f'champions_{p.rival_team}']}"
        text = f"A {how_many} in {p.place(spot)} at {_clock(f['since'])}. " + _damage_txt(own, times)
        text += (" That is the ADC doing its job: the fight was yours to carry and you carried it." if well else
                  " Low for an ADC: either you never got to a safe angle, you were kited off the fight, or you went "
                  "down early. Your team fights a player short when your damage doesn't land.")
        if not well and (bad_ := _bad_wave(p, f["since"], spot)):
            text += " " + bad_
        out.append((abs(times - 1.33), _moment(p, f["since"], spot, "damage", "good" if well else "bad",
                              1 + bool(f["teamfight"]) + (times >= 2.0 or times <= 0.4),
                              "Carried the damage in a fight" if well else "Barely did damage in a fight",
                              text, end=f["until"])))
    # the ones that stand out most: with all of them, the match's list would be half a screen of fights
    return [m for _key, m in sorted(out, key=lambda x: -x[0])[:HOW_MANY_DAMAGE]]

TOWER_HIT = 600.0  # health they must take off for it to be a siege and not a minion hitting


def mid_tower(p: Game) -> list[dict]:
    """For the marksman: the outer mid turret that reaches 14 alive is theirs to look after from then on.

    When the mid game starts the marksman plays around that turret: while it stands, the mid waves
    keep arriving where they should and the map defends itself. With the turrets' health
    (`moments.sieges`, from the harvest) there is no need to wait for it to fall: each stretch in which it is being eaten
    comes out with how much health is taken from it, who was hitting it and who was defending it.

    The two endings that cost games are the ones seen here: being caught in mid and the turret then being
    eaten, and them being off rotating while the enemy marksman hits the turret. With the enemy collapsing with extra
    people there was nothing to do and the play is to let it go."""
    if p.position != "BOTTOM":
        return []
    own_items = [a for a in p.raw.get("sieges") or []
             if a["team"] == p.team and a["lane"] == "mid" and a["rank"] == "OUTER_TURRET"]
    if not own_items or any(a["falls"] and a["until"] < LANING_PHASE for a in own_items):
        return []  # no turret health in that harvest, or the turret fell in the laning phase
    rival_marksman = next((j["champion"] for j in p.events["players"]
                          if j["team"] == p.rival_team and j["position"] == "BOTTOM"), None)
    out = []
    for a in own_items:
        if a["since"] < LANING_PHASE or not a["attack"] or a["health_lost"] < TOWER_HIT:
            continue
        spot = (a["x"], a["z"])
        opp = p.champion in a["defend"]
        numbers = len(a["attack"]) - len(a["defend"]) >= 2
        share = a["health_lost"] / max(1.0, a["health_before"])
        died = next((m for m in p.kills if m["victim"] == p.champion and a["since"] - 35 <= m["t"] <= a["since"] + 5), None)
        where = _list([f"{_duration(s)} {spot_}" for spot_, s in p.activity(a["since"] - 45, a["since"])[:2]])
        text = (f"From {_clock(a['since'])} they took {a['health_lost']:,} health off your mid outer turret"
                 f"{' and killed it' if a['falls'] else f', {share:.0%} of what it had left'}. "
                 f"{_list(a['attack'])} {'was' if len(a['attack']) == 1 else 'were'} on it"
                 + (f", with {_list(a['defend'])} defending" if a["defend"] else ", with nobody defending")
                 + ".")
        if died:
            text += (f" You died at {_clock(died['t'])}, right before. That is the sequence that costs games: they "
                      "catch the ADC in mid and the turret goes with you.")
            tone, title, severity = "bad", "Caught in mid, then the turret", 2 + bool(a["falls"])
        elif numbers:
            text += (" They came with numbers, so there was nothing to hold: give it up and take something on the "
                      "other side of the map instead of dying for it.")
            tone, title, severity = "neutral", "Mid turret under a collapse", 1
        elif opp:
            text += " You were there holding it, which is where an ADC belongs once the laning phase ends."
            tone, title, severity = "good", "Held the mid turret", 1
        else:
            text += (f" You spent the 45 s before {where}."
                      + (" Their ADC was one of the ones hitting it." if rival_marksman in a["attack"] else "")
                      + " From 14:00 that turret is the ADC's job: while it stands every mid wave arrives where it "
                      "should, and once it falls you are the one living with it for the rest of the game.")
            tone, title, severity = "bad", "Mid turret hit while you were elsewhere", 1 + bool(a["falls"]) + (share >= 0.5)
        out.append(_moment(p, a["since"], spot, "tower", tone, severity, title, text, end=float(a["until"])))
    return out


# What a plate of difference in a lane before 14 is worth, in team winrate points: measured in
# 10,276 matches of the harvest (from -5 to +5 plates, mid goes from 17.5% to 82.5%; top only from 27.1% to 72.9%).
WINRATE_PER_PLATE = {"mid": 6.5, "bot": 6.0, "top": 4.6}
PLATE_GOLD = 160  # what a plate shares among those beside it
PLATE_STREAK = 60.0  # seconds without any falling that split a run of plates in two
MIN_PLATES = 2  # plates of difference in a run to show it: a single one is the lane's normal rhythm
HOW_MANY_PLATES = 3  # the runs that moved most; the rest is noise in the list
AT_THE_PLATE = 1300.0  # within this of the turret, they are at it (the same as `moments.NEAR_TOWER`)


def plates(p: Game) -> list[dict]:
    """For laners and the support: the runs of plates in their lane before 14, the cheapest gold there is.

    A plate is 160 gold shared among those beside it, and a lane's plate difference
    predicts the game better than almost anything that happens there: each plate is worth 6.5 winrate points in mid,
    6.0 in bot and 4.6 in top. What is judged is the run (`PLATE_STREAK` without any falling cuts it) and only
    if it moved `MIN_PLATES` of difference: a loose plate traded for another is the lane's normal rhythm, and
    with a moment per plate the list filled up with four identical sentences.

    If the match carries the turrets' health (`raw["sieges"]`), it also comes out with how much was left: a turret
    that has already lost half its health in the laning phase is a turret that falls at the first grouping."""
    if p.position not in M.LANES:
        return []
    mine = M.LANES[p.position]
    own_rows = [x for x in p.raw.get("plates") or [] if x["lane"] == mine]
    if not own_rows:
        return []  # without a timeline there are no plates: they come from the API's TURRET_PLATE_DESTROYED
    runs = []
    for run in _streaks([dict(x, t=x["time"]) for x in own_rows], PLATE_STREAK):  # `_streaks` goes by `t`
        ours = [x for x in run if x["team"] == p.rival_team]  # those of their turret are collected by their team
        against = [x for x in run if x["team"] == p.team]
        if abs(len(ours) - len(against)) >= MIN_PLATES:
            runs.append((run, ours, against))
    out = []
    for run, ours, against in sorted(runs, key=lambda x: -abs(len(x[1]) - len(x[2])))[:HOW_MANY_PLATES]:
        diff, t = len(ours) - len(against), run[0]["time"]
        won_ = diff > 0
        which_ones = ours if won_ else against
        spot = (which_ones[0]["x"], which_ones[0]["z"])
        ahead = _who_near(p, which_ones[0]["time"] - 5, which_ones[-1]["time"] + 5, spot)
        opp = p.champion in ahead[p.team]
        gold = abs(diff) * PLATE_GOLD
        text = (f"{_plates_txt(len(ours), len(against))} in {mine} lane in the {_duration(max(5.0, run[-1]['time'] - t))} "
                 f"from {_clock(t)}: {diff:+d} plates, about {gold:,} gold and {abs(diff) * WINRATE_PER_PLATE[mine]:.0f} "
                 f"points of win rate (each plate of difference in {mine} is worth {WINRATE_PER_PLATE[mine]:.1f}).")
        if health := _tower_health(p, which_ones[-1]):
            text += f" The turret was left on {health}."
        where = _list([f"{_duration(x)} {spot_}" for spot_, x in p.activity(t - 30, run[-1]["time"])[:2]])
        if won_ and opp:
            text += " You were on the turret for them, which is what prio in lane is for."
            tone, title, severity = "good", "Cashed your lane into plates", 1 + (diff >= 3)
        elif won_:
            text += f" You were not there for them: you spent that minute {where}."
            tone, title, severity = "neutral", "Plates taken without you", 1
        elif len(ahead[p.rival_team]) - len(ahead[p.team]) >= 2:
            text += (f" {_list(sorted(ahead[p.rival_team]))} came for them with numbers, so those were not "
                      "yours to hold.")
            tone, title, severity = "neutral", "Plates lost to a collapse", 1
        elif opp:
            text += " You were there and they took them anyway, which is the lane being lost rather than thrown."
            tone, title, severity = "neutral" if diff > -3 else "bad", "Plates lost in a lane you were holding", 1
        else:
            text += (f" You spent that minute {where} and nobody was on the turret. This is the cheapest gold in "
                      "the game to give away and it compounds: fewer plates, a weaker turret, and every wave "
                      "after that arrives on their terms.")
            tone, title, severity = "bad", "Plates given away", 1 + (diff <= -3)
        out.append(_moment(p, t, spot, "plate", tone, severity, title, text,
                              end=run[-1]["time"] if run[-1]["time"] > t else None,
                              gold=diff * PLATE_GOLD))
    return sorted(out, key=lambda m: m["t"])


def _plates_txt(ours: int, against: int) -> str:
    """"Your lane took 3 plates", "They took 2 plates off you", "You traded 2 plates for 1"."""
    if ours and against:
        return f"You traded {ours} plate{'s' * (ours > 1)} for {against}"
    if ours:
        return f"Your lane took {ours} plate{'s' * (ours > 1)}"
    return f"They took {against} plate{'s' * (against > 1)} off you"


def _who_near(p: Game, since: float, until: float, spot: tuple[float, float]) -> dict[str, set[str]]:
    """{team: those who passed by} in those seconds, within `AT_THE_PLATE` of the place and alive."""
    out: dict[str, set[str]] = {"100": set(), "200": set()}
    for j in p.events["players"]:
        for t in range(int(since), int(until) + 1, 2):
            q = p.where(j["champion"], t)
            if q and p.is_alive(j["champion"], t) and math.dist(q, spot) <= AT_THE_PLATE:
                out[j["team"]].add(j["champion"])
                break
    return out


def _tower_health(p: Game, plate: dict) -> str | None:
    """How much health that turret was left with after the plate, if the match carries the turrets' health."""
    near = [a for a in p.raw.get("sieges") or []
             if a["lane"] == plate["lane"] and a["rank"] == "OUTER_TURRET"
             and a["team"] == plate["team"] and a["since"] - 10 <= plate["time"] <= a["until"] + 10]
    if not near:
        return None
    return f"{max(near, key=lambda a: a['until'])['health_after']:,} health"


def dive(p: Game) -> list[dict]:
    """For the marksman: the slow push that comes at them with their support and jungler away.

    If the enemy is joining waves toward them and has nobody nearby, the wave stops being theirs: with the enemy
    jungler or mid unseen for NO_INFO seconds, staying to pick it up under the turret is
    putting yourself in range of a dive. Losing the entire wave is the play, even if the mistake comes from someone else.

    If they are killed there it comes out as a mistake; if they let it go and leave, as a success."""
    if p.position not in ("TOP", "MIDDLE", "BOTTOM"):
        return []
    lane = M.LANES[p.position]
    rival_side = "red" if p.team == "100" else "blue"
    jungler, mid = _of(p, p.rival_team, "JUNGLE"), _of(p, p.rival_team, "MIDDLE")
    my_jg, my_sup = _of(p, p.team, "JUNGLE"), _of(p, p.team, "UTILITY")
    out = []
    for a in p.raw["concepts"]["accumulations"]:
        if a["lane"] != lane or a["side"] != rival_side or a["peak"] < 4:
            continue
        t = a["clash"] - 10 if a["clash"] else a["since"]  # when the wave reaches their turret: that is where it is decided whether they stay
        where = p.where(p.champion, t)
        if not where or not p.is_alive(p.champion, t):
            continue
        if sum(_far(p, c, t, where) and not _arrives(p, c, t) for c in (my_jg, my_sup) if c) < 2:
            continue  # with someone beside them, or about to arrive, the wave is theirs
        risk = [c for c in (jungler, mid) if c and _blindly(p, c, t)]
        # what weighs most (reference review): the enemy knowing where their support is, that they left in view
        knows = bool(my_sup) and any((f := p.table.get(my_sup, {}).get(s_)) and f.get("seen") == "True"
                                     for s_ in range(int(t) - KNOW, int(t) + 1))
        if not risk and not knows:
            continue
        died = next((m for m in p.kills if m["victim"] == p.champion and t - 10 <= m["t"] <= t + 25), None)
        goes_back = any(e["type"] == "AddBuff" and e["buff"].lower() == "recall" and e["net_id"] == p.me["net_id"]
                     and t <= e["time"] <= t + 25 for e in p.events["events"])
        leaves = not died and (goes_back or all(not (q := p.where(p.champion, s)) or math.dist(q, where) > 1800
                                             for s in range(int(t) + 10, int(t) + 26, 5)))
        health = M._health(p.table.get(p.champion, {}).get(int(t)))
        text = (f"At {_clock(t)} they had {a['peak']} extra minions stacking into your lane, with "
                 f"{_list([c for c in (my_sup, my_jg) if c])} nowhere near you")
        if knows:
            text += f". They had seen {my_sup} leave, so they know you are alone"
        if risk:
            text += f"{', and' if knows else ' and'} no sight of {_list(risk)} for over {NO_INFO:.0f} s"
        text += "."
        if health is not None and health < 0.5:
            text += (f" You were on {100 * health:.0f}% health when it built up, which is the other half of how dives "
                      "happen: the trade you took before decides whether they can even go for it.")
        if died:
            text += (f" You stayed for it and died at {_clock(died['t'])}. That wave was not yours: with nobody to "
                      "answer a collapse and no idea where they were, the play is to give it up whole and take the "
                      "reset, even when the reason you are alone is someone else's.")
            out.append(_moment(p, t, where, "dive", "bad", 2, "Dived on a wave that wasn't yours", text,
                                  end=died["t"]))
        elif leaves:
            text += " You gave the wave up and left, which is the play: a lost wave costs less than a death under tower."
            out.append(_moment(p, t, where, "dive", "good", 1, "Gave up a wave you couldn't hold", text))
        else:
            text += (" You held it and got away with it this time; the same spot with their jungler walking in is a "
                      "free kill for them.")
            out.append(_moment(p, t, where, "dive", "neutral", 1, "Held a wave you couldn't see coming", text))
    return out

# ── The match scoreboard and the player's grade ───────────────────────────────────────────────────────────

ORDER = {"TOP": 0, "JUNGLE": 1, "MIDDLE": 2, "BOTTOM": 3, "UTILITY": 4}
EPIC_MARKER = (("Dragon", "dragons"), ("Baron", "barons"), ("Herald", "heralds"), ("Voidgrub", "grubs"))


def _int(s: dict, key: str) -> int:
    try:
        return int(float(s.get(key) or 0))
    except (TypeError, ValueError):
        return 0


def scoreboard(p: Game) -> dict:
    """The post-game scoreboard, from the replay: the ten players with their KDA, gold, CS and damage, and
    for each team the kills, gold, turrets and objectives it took."""
    players = []
    stats = p.events.get("stats") or []
    for i, j in enumerate(p.events["players"]):
        s = stats[i] if i < len(stats) else {}  # a replay without a statsJson leaves the scoreboard at zero, it doesn't break the analysis
        players.append({
            "champion": j["champion"], "role": j["position"], "you": j["champion"] == p.champion,
            "side": "ally" if j["team"] == p.team else "enemy",
            "kills": _int(s, "CHAMPIONS_KILLED"), "deaths": _int(s, "NUM_DEATHS"),
            "assists": _int(s, "ASSISTS"), "level": _int(s, "LEVEL"),
            "cs": _int(s, "MINIONS_KILLED") + _int(s, "NEUTRAL_MINIONS_KILLED"),
            "gold": _int(s, "GOLD_EARNED"), "damage": _int(s, "TOTAL_DAMAGE_DEALT_TO_CHAMPIONS"),
            "taken": _int(s, "TOTAL_DAMAGE_TAKEN"), "vision": _int(s, "VISION_SCORE"),
            "wards": _int(s, "WARD_PLACED"), "plates": _int(s, "Missions_TurretPlatesDestroyed"),
        })
    players.sort(key=lambda x: (x["side"] != "ally", ORDER.get(x["role"], 9)))
    teams = {}
    for side in ("ally", "enemy"):
        own_items = [x for x in players if x["side"] == side]
        team = p.team if side == "ally" else p.rival_team
        of_that = [o for o in p.objectives if o["team"] == team]
        teams[side] = {"kills": sum(x["kills"] for x in own_items), "deaths": sum(x["deaths"] for x in own_items),
                         "gold": sum(x["gold"] for x in own_items),
                         "towers": sum(1 for o in of_that if o["epic"] is None),
                         **{key: sum(1 for o in of_that if (o["epic"] or "").startswith(pre))
                            for pre, key in EPIC_MARKER}}
    return {"players": players, "teams": teams}


# How much each moment adds or subtracts in the grade, per severity level (1-3). It is the football-grades scale:
# what each thing weighs is set by the concept and how big it was, not the loose gold of that play. With each moment's
# measured gold the grade became a death counter (40% of what moved it) and a jungler-fight counter
# (56%), because a fight moves thousands of gold and an opening moves none.
#
# The match's fights, objectives and swings are not included: the team decides them and the grade is for what they
# do. That is why the grade depends little on winning (correlation +0.30 across 400 test players) and little on how long the
# match lasts (-0.18, with the points already brought to 30 minutes). With these weights deaths are four tenths of what
# moves it, the jungler's plays three and the other decisions the rest.
WEIGHT = {"death": 0.8, "gank": 1.4, "play": 1.2, "fog": 1.2, "camps": 1.0, "pair": 1.0, "opening": 1.2,
        "roam": 1.2, "ward": 1.0, "back": 0.8, "flash": 0.7, "setup": 1.0,
        # for the marksman: the damage they put into each fight, the lane trades and the dive
        "damage": 1.2, "trade": 1.0, "dive": 1.4,
        # the lane's plates: the cheapest gold of the laning phase and the one that predicts most (6.5 winrate
        # points per plate in mid). It comes from the timeline, which all the harvest's matches have
        "plate": 1.2}
# The mid turret (`tower`) is left out of the grade on purpose: it needs the turrets' health, which only
# the matches harvested since the decoder stores it carry, and the 5,143 against which the scale was measured don't have
# it (their .rofl no longer exist and Riot only serves those of the current patch). With a new harvest that carries it,
# it is added here and grades.py is run again.
GRADE_MINUTES = 30.0  # the grade is brought to a 30-minute match: in a 45-minute one there is more of everything, for better and for worse


def _ungraded(moment_list: list[dict]) -> list[dict]:
    """Marks moments that come out in the match but don't score: the reference review's concepts are not yet calibrated against
    the 5,143 matches with which `WEIGHT` and the league grades were set (adding them moved the grade without anyone having recalibrated it)."""
    for m in moment_list:
        m["no_score"] = True
    return moment_list


def _points(m: dict) -> float:
    """What a moment adds (or subtracts) to the grade."""
    if m.get("no_score"):
        return 0.0
    weight = WEIGHT.get(m["kind"])
    return 0.0 if weight is None else {"good": 1.0, "bad": -1.0}.get(m["tone"], 0.0) * weight * m["severity"]


def grade(moment_list: list[dict], duration: float) -> dict:
    """What their moments add and subtract in the match, brought to one of GRADE_MINUTES minutes: `total` and where it
    comes from. The 1-to-100 grade is set by `grades`, which needs how this is distributed in their league and position."""
    scale = GRADE_MINUTES / max(10.0, duration / 60)
    parts: dict[str, dict] = {}
    for m in moment_list:
        pts = _points(m)
        if not pts:
            continue
        d = parts.setdefault(m["kind"], {"kind": m["kind"], "points": 0.0, "good": 0, "bad": 0})
        d["points"] += pts * scale
        d["good" if pts > 0 else "bad"] += 1
    for d in parts.values():
        d["points"] = round(d["points"], 1)
    return {"total": round(sum(_points(m) for m in moment_list) * scale, 1),
            "parts": sorted(parts.values(), key=lambda d: d["points"])}


def grades(games: list[dict], reference: dict | None) -> None:
    """Sets the 1-to-100 grade of each match, comparing what their moments added up to with what those of their
    league and position add up to (`reference`: the 10th, 35th, 50th, 65th and 90th percentiles of `total`). It is the same scale as the app's
    match grade (`ygg_core.metrics.match_score`): the 50th percentile of their league scores 62.5 and the 90th, 85."""
    from ygg_core.metrics.match_score import metric_score

    for j in games:
        r = (j.get("rating") or {})
        cuts = (reference or {}).get(j.get("role"))
        if not r or not cuts:
            continue
        r["score"] = max(1, min(100, round(metric_score("wpa", r["total"], tuple(cuts)))))
        r["median"] = cuts[2]  # what an ordinary match of their league and position adds up to, to read the total


def analyse(raw: dict, record: dict | None, champion: str, openings_model: dict | None = None) -> dict:
    """The moments of `champion` in a match (in order), the series to draw it and its numbers. With the `openings.py`
    model, also each jungler opening judged against what the Challengers would do."""
    import openings as A
    import jungle as J

    p = Game(raw, record, champion)
    own_deaths = deaths(p)
    map_ = A.GameMap(p.events, p.rows, p.raw.get("waves"), p.curve) if p.position in ("JUNGLE", "UTILITY") else None
    # where they were before each objective after 14 (jungle and support)
    before = [f for f in A.preparations(map_, positions=(p.position,)) if f["champion"] == p.champion] if map_ else []
    own_fights = fights(p, own_deaths)
    moment_list = sorted(own_deaths + camps(p) + fog(p) + own_fights + swings(p)
                      + flashes(p) + lane(p) + plays(p) + camp_pairs(p) + vision(p) + preparations(p, before)
                      + _ungraded(initial_ward(p) + adc_opening(p) + proactive_play(p) + free_damage(p) + without_crash(p) + crashes(p) + slowpush(p)
                          + first_tower(p) + freeze(p) + under_tower(p) + J.everything(p)) + trades(p) + mid_tower(p) + dive(p) + damage_in_fights(p, own_fights) + plates(p)
                      + (openings(p, map_, openings_model) + support_openings(p, map_, openings_model)
                         + roams_support(p, map_) if map_ else []), key=lambda m: m["t"])
    J.net_of_plays(p, moment_list)
    J.adjust_openings(p, moment_list)
    J.far_from_herald(p, moment_list)
    for i, m in enumerate(moment_list):
        m["id"] = i
    series_ = series(p)
    return {"moments": moment_list, "series": series_, "numbers": numbers(p, moment_list, series_, before), "opponent": p.rival,
            "wards": wards(p), "scoreboard": scoreboard(p),
            "rating": grade(moment_list, p.events["game_length"])}


# ── The patterns across several matches ───────────────────────────────────────────────────────────────────

ROLES = {"JUNGLE": "junglers", "TOP": "top laners", "MIDDLE": "mid laners", "BOTTOM": "ADCs", "UTILITY": "supports"}


def _mean(values: list) -> float | None:
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def _ref(reference: dict, *columns: str) -> dict | None:
    """The median, the mean of those who win and that of those who lose in their league and role; with several columns, the
    sum (the means are added)."""
    rows = [reference.get(c) for c in columns]
    if not all(rows) or any(f[6] is None or f[7] is None for f in rows):
        return None
    return {"median": sum(f[2] for f in rows), "winners": sum(f[6] for f in rows), "losers": sum(f[7] for f in rows)}


SEPARATES = 0.08  # the least those who win must differ from those who lose, over the median, to score


def _towards(you: float | None, r: dict | None) -> float | None:
    """Where the player stands between those who win (0) and those who lose (1) in their league and role: more than 1, worse than those who
    lose; less than 0, better than those who win. It is equally valid for what is better high and for what is better low.

    None if that concept doesn't separate one from the other (they differ by less than SEPARATES of the median): dividing by a difference
    of nothing gave weights of 7 and even changed direction (in Master, winning junglers leave 6.3 clears and losing
    ones 5.9). Bounded between -1 and 2 so that one concept doesn't cover the others."""
    if you is None or not r:
        return None
    gap = r["losers"] - r["winners"]
    if abs(gap) < SEPARATES * max(abs(r["median"]), abs(r["winners"]), abs(r["losers"]), 1e-9):
        return None
    return max(-1.0, min(2.0, (you - r["winners"]) / gap))


def _weight(you: float | None, r: dict | None, uncompared: float) -> float:
    """`_towards`, or `uncompared` if there is nothing to compare against or the concept doesn't separate winners from losers."""
    h = _towards(you, r)
    return uncompared if h is None else h


def _ids(games: list[dict], filter_, how_many: int = 6) -> list[str]:
    """The moments that meet `filter_`, from most to least serious: "match:moment"."""
    everyone = [(m["severity"], -abs(m.get("value") or 0), j["match_id"], m["id"])
             for j in games for m in j.get("moments") or [] if filter_(m)]
    return [f"{mid}:{i}" for _s, _v, mid, i in sorted(everyone, key=lambda x: (-x[0], x[1]))[:how_many]]


def _pattern(kind: str, title: str, text: str, weight: float, moment_list: list[str], **extra) -> dict:
    """A pattern. `weight` on the scale of `_towards` (0 like those who win, 1 like those who lose): from 0.5 up
    it is something that costs them games, from 0 down something they do well."""
    tone = "bad" if weight >= 0.5 else "good" if weight <= 0 else "neutral"
    return {"kind": kind, "title": title, "text": text, "tone": tone, "weight": round(weight, 2), "moments": moment_list} | {
        k: v for k, v in extra.items() if v is not None}


def _against(you: float, r: dict | None, role: str, league: str, unit: str, decimals: int = 1) -> str:
    if not r:
        return ""
    f = f"{{:.{decimals}f}}"
    return (f" Winning {role} in {league} average {f.format(r['winners'])}{unit}, losing ones {f.format(r['losers'])}{unit}"
            f" (you: {f.format(you)}{unit}).")


# What goes into the support's vision score: the column of the features table (whole match), what it is
# called and whether more is better (+1) or worse (-1). The direction of each is set by the league ladder measured in the 5,143
# matches of 16.19 (research/replays/reports/vision.md), not by anyone's criterion, and only those that have one are included (from Gold to
# Challenger, in standard deviations): wards per 10 min +1.34; control wards +0.99; sweeps +0.79; wards that
# find the enemy jungler +0.79; charges thrown away per back to base -0.91; wards with no window -0.35.
#
# Left out on purpose, though they are measured and shown: the share of wards that show someone (+0.00) and the
# seconds of information per ward (-0.38, because the more you place the less each one adds and the more of them get swept), the
# share of high-risk wards (+0.20: the risk rises with the league) and deaths while placing a ward (+0.10). Comparing
# with winners and losers doesn't work here either: in a lost game the enemy is all over the place
# and the wards show more, so almost all these columns come out "better" in defeats.
VISION = (
    ("guard_wards_10", "Wards placed per 10 min", 1),
    ("guard_to_jungler_10", "Wards that found their jungler", 1),
    ("control_placed_10", "Control wards placed", 1),
    ("sweeps_10", "Sweeps", 1),
    ("support_item_wasted_per_trip", "Wards left unused on each recall", -1),
    ("guard_loose_share", "Wards placed with no window", -1),
)


def vision_score(est: list[dict], reference: dict) -> dict | None:
    """A support's vision score: for each VISION item, the percentile of their mean among the supports of
    their league (inverted for what is better the less), and the mean of all. 50 is the median of their league."""
    from premium_references import percentile

    parts = []
    for column, name, direction in VISION:
        values = [e[column] for e in est if isinstance(e.get(column), (int, float)) and not isinstance(e.get(column), bool)]
        row = reference.get(column)
        if not values or not row:
            continue
        mean = sum(values) / len(values)
        p = percentile(mean, row[:5])
        parts.append({"key": column, "label": name, "value": round(mean, 2), "median": row[2],
                       "score": round(p if direction > 0 else 100 - p), "better": "higher" if direction > 0 else "lower"})
    if len(parts) < 3:
        return None
    return {"score": round(sum(x["score"] for x in parts) / len(parts)), "parts": parts}


def patterns(games: list[dict], reference: dict, league: str, position: str, openings_: dict | None = None,
             top: dict | None = None) -> list[dict]:
    """What repeats in their matches: how many times, in how many matches, how much it costs them, how those who
    win and those who lose in their league and role do it (`reference`: the columns of premium_reference.json for that league and role)
    and the moments that show it. From what separates them most from those who win to what they do best."""
    n = len(games)
    if not n:
        return []
    league, role = league.title(), ROLES.get(position, "players")
    mom = [j.get("moments") or [] for j in games]
    num = [j.get("numbers") or {} for j in games]
    est = [j.get("stats") or {} for j in games]
    out = []

    # ── deaths
    all_ = [m for ms in mom for m in ms if m["kind"] == "death"]
    deaths = _mean([e.get("deaths") for e in est]) or len(all_) / n
    r = _ref(reference, "deaths")
    if all_ or r:
        blind_count = sum("no vision" in m.get("tags", []) for m in all_)
        objective = sum("objective lost" in m.get("tags", []) for m in all_)
        given_away = sum(-(m.get("gold") or 0) for m in all_)
        early = sum(m["t"] < LANING_PHASE for m in all_) / n
        text = f"You die {deaths:.1f} times per game, {early:.1f} of them before 14:00." + _against(deaths, r, role, league, "")
        if all_:
            text += (f" {blind_count} of your {len(all_)} deaths came from someone you never saw coming, {objective} were "
                      f"followed by an objective or turret lost while you were dead, and together they paid the enemy "
                      f"{given_away:,.0f} gold. Each death is worth about {WORTH['kill']} points of win chance to the enemy.")
        out.append(_pattern("death", "Deaths", text, _weight(deaths, r, 0.5), _ids(games, lambda m: m["kind"] == "death"),
                             per_game=round(deaths, 1), count=len(all_), gold=-given_away or None, reference=r))

    # ── jungle: camps and fog
    if position == "JUNGLE":
        standing = _mean([x.get("camp_clears_lost") for x in num])
        if standing is not None:
            stolen = _mean([x.get("camps_stolen") for x in num]) or 0.0
            invade = _mean([x.get("camps_invaded") for x in num]) or 0.0
            lost_ = standing + stolen
            gold = sum((x.get("camp_gold_lost") or 0) + (x.get("camp_gold_stolen") or 0) for x in num)
            r_rob, r_inv, r_per = (_ref(reference, c) for c in ("idle_stolen", "idle_invade",
                                                                   "idle_lost_and_stolen"))
            text = (f"Before 14:00 you lost {lost_:.1f} camp clears per game: {standing:.1f} left standing and "
                     f"{stolen:.1f} stolen by the enemy jungler, about {gold / n:,.0f} gold per game "
                     f"({gold:,.0f} over {n} game{'s' if n != 1 else ''}) plus the XP. You took {invade:.1f} of theirs "
                     "per game.")
            # what separates those who win from those who lose isn't how many camps they leave (almost the same) but who
            # takes the other's (see moments.idle_jungle): the weight comes from thefts and invasions
            if r_rob and r_inv:
                text += (f" What separates winning {role} in {league} from losing ones isn't how many camps they leave "
                          f"but who takes whose: winners get {r_rob['winners']:.1f} stolen and take {r_inv['winners']:.1f} "
                          f"per game, losers get {r_rob['losers']:.1f} stolen and take {r_inv['losers']:.1f}.")
            if top and (c := _ref(top, "idle_lost_and_stolen")) and r_per:
                text += (f" Across tiers the ladder is clear: Challenger junglers lose {c['median']:.1f} clears per game, "
                          f"the {league} median is {r_per['median']:.1f}.")
            text += (" Each clear is worth 109 gold (Krugs), 85 (Wolves), 80 (Gromp) or 75 (Raptors), and a camp you don't "
                      "take respawns later, so the delay piles up.")
            weights = [h for h in (_towards(stolen, r_rob), _towards(invade, r_inv)) if h is not None]
            out.append(_pattern("camps", "Jungle control", text,
                                 sum(weights) / len(weights) if weights else _weight(lost_, r_per, 0.3),
                                 _ids(games, lambda m: m["kind"] == "camps" and m["tone"] == "bad"),
                                 per_game=round(lost_, 1), gold=-round(gold), reference=r_per))
        nothing = _mean([x.get("showups_nothing") for x in num])
        if nothing is not None:
            hidden = _mean([x.get("unseen_share") for x in num]) or 0
            ganks = _mean([x.get("ganks_kill") for x in num]) or 0
            r = _ref(reference, "jungler_taking_nothing")
            inv, vis = _ref(reference, "jungler_invisible"), _ref(reference, "jungler_visible")
            text = (f"Between 2:00 and 14:00 the enemy couldn't see you {hidden:.0f}% of the time. You showed yourself "
                     f"{nothing:.1f} times per game without getting anything back, and {ganks:.1f} times per game an "
                     "appearance ended in a kill.")
            if inv and vis:
                text += (f" Winning {role} in {league} stay unseen {100 * inv['winners'] / (inv['winners'] + vis['winners']):.0f}% "
                          f"of that time")
                text += f" and show up for nothing {r['winners']:.1f} times per game (losing ones {r['losers']:.1f})." if r else "."
            text += (" The fog is worth something even when nothing happens: while nobody knows where you are, all three "
                      "lanes have to play as if you were next to them, so they can't push, trade or ward deep freely. Every "
                      "time you appear without a kill, a summoner spell burned or a laner sent back, you give that pressure "
                      "away and tell them where you are not.")
            out.append(_pattern("fog", "Fog of war", text, _weight(nothing, r, 0.3), _ids(games, lambda m: m["kind"] == "fog"),
                                 per_game=round(nothing, 1), unseen_share=round(hidden), reference=r))

    # ── jungle: the openings, against what Challengers and Grandmasters would do (openings.model)
    clear_ones = sum(x.get("openings_clear") or 0 for x in num)
    if position == "JUNGLE" and clear_ones:
        rate = sum(x.get("openings_matched") or 0 for x in num) / clear_ones
        agreement = (openings_ or {}).get("agreement", {})
        own_entry, top_a, base_a = agreement.get(league.upper()), agreement.get("CHALLENGER"), agreement.get("GOLD")
        r = {"median": own_entry["all"], "winners": own_entry["winners"], "losers": own_entry["losers"]} if own_entry else None
        text = (f"Every time you leave base you choose which half of the map to open. In {clear_ones} of your openings the map "
                 f"had a clear best side, and you took the one Challenger and Grandmaster junglers take {rate:.0%} of the "
                 "time.")
        if top_a and base_a:
            text += (f" Challenger junglers do it {top_a['all']:.0%} of the time and Gold ones {base_a['all']:.0%}: "
                      "reading the map is one of the things that climbs with rank.")
        died = (openings_ or {}).get("follow", {}).get("dies_pp")
        if died and died["no"] > died["matches"]:
            text += (f" Opening against a clear read is where junglers die: {died['no']:.0f}% of the time in the next "
                      f"90 seconds, against {died['matches']:.0f}% when they follow it.")
        text += (" The read is mostly your camps up or respawning within 30 s on each side (high-elo junglers count "
                  "respawn timers, lower tiers look at what is up right now), then the objective about to spawn; each "
                  "opening on the map shows the whole picture.")
        # the league ladder separates more than winning or losing within one (Master: 87% against 85%): 0 is Challenger's level and
        # 1 is Gold's
        weight = (max(-1.0, min(2.0, (top_a["all"] - rate) / (top_a["all"] - base_a["all"])))
                if top_a and base_a and top_a["all"] > base_a["all"] else _weight(rate, r, 0.3))
        # without `reference`: `r` is a hit percentage and `per_game`, clear openings per match
        out.append(_pattern("opening", "Map openings", text, weight,
                             _ids(games, lambda m: m["kind"] == "opening" and m["tone"] == "bad"),
                             per_game=round(clear_ones / n, 1), count=clear_ones))

    # ── jungle: camp pairs and plays with live camps
    if position == "JUNGLE":
        broken = _mean([x.get("pairs_broken") for x in num])
        if broken is not None:
            r = _ref(reference, "pairs_broken")
            cleared_at = _mean([x.get("pair_clears") for x in num]) or 0
            text = ("Raptors go with Krugs and Wolves with Gromp: cleared in the same pass they come back together, and "
                     "split they respawn out of step, so every later visit to that side finds half of it. Before 14:00 you "
                     f"cleared one and left its pair up {broken:.1f} times per game (of {cleared_at:.0f} small-camp clears)."
                     + _against(broken, r, role, league, ""))
            if top and (c := _ref(top, "pairs_broken")):
                text += f" Challenger junglers split {c['winners'] / 2 + c['losers'] / 2:.1f} per game."
            text += (" Most splits come from leaving for a fight or dying; when it is a recall or just moving on, "
                      "finish the pair first.")
            out.append(_pattern("pair", "Camp pairs", text, _weight(broken, r, 0.3),
                                 _ids(games, lambda m: m["kind"] == "pair" and m["tone"] == "bad"),
                                 per_game=round(broken, 1), reference=r))
        done = sum(x.get("plays") or 0 for x in num)
        if done:
            good_ones, bad_ones = (sum(x.get(k) or 0 for x in num) for k in ("plays_good", "plays_bad"))
            value = sum(x.get("plays_value") or 0 for x in num) / n
            cost = sum(x.get("plays_camp_cost") or 0 for x in num) / n
            r = _ref(reference, "plays_bad_ones")
            text = (f"You left camps up to make a play {done / n:.1f} times per game before 14:00. Of those {done} plays, "
                     f"{good_ones} paid for the camps, {bad_ones} cost more than they gave back and the rest broke even: "
                     f"{value:+,.0f} g per game for your side all in, against about {cost:,.0f} g of clears pushed back. "
                     "The count is for everyone involved, on both teams: kills, plates, waves lost by whoever came to "
                     "help or died, camps taken from their jungle. With camps up a play has to return more than the farm "
                     "it delays; with none up it is free." + _against(bad_ones / n, r, role, league, " plays that didn't pay"))
            out.append(_pattern("play", "Plays with camps up", text, _weight(bad_ones / n, r, min(1.0, 1.6 * bad_ones / done)),
                                 _ids(games, lambda m: m["kind"] == "play" and m["tone"] == "bad"),
                                 per_game=round(bad_ones / n, 1), count=done, gold=round(value * n) or None, reference=r))

    # ── support: where they open on leaving base, the roams and the vision
    leaving = sum(x.get("openings") or 0 for x in num)
    if position == "UTILITY" and leaving:
        through_mid = sum(x.get("openings_mid") or 0 for x in num) / leaving
        sup = (openings_ or {}).get("support") or {}
        by_league = sup.get("opens_mid", {})
        own_entry, top_s, base_s = by_league.get(league.upper()), by_league.get("CHALLENGER"), by_league.get("GOLD")
        text = ("Every time you leave base in lane phase you choose: straight down to your ADC, or through mid (vision "
                 "on the way, pressure on their mid laner) and bot after. You opened through mid in "
                 f"{through_mid:.0%} of your {leaving} exits.")
        if top_s and base_s and own_entry:
            text += (f" Challenger supports do it {top_s:.0%} of the time, {league} ones {own_entry:.0%} and Gold ones "
                      f"{base_s:.0%}: it is one of the clearest differences between tiers.")
        text += " What decides it is the wave you leave your ADC with, and the measured payoff follows exactly that."
        botlanes = sup.get("by_botlane", {})
        pushed_, slow = (botlanes.get(k, {}).get("value") for k in ("pushed", "slowpush rival"))
        if pushed_ and slow:
            text += (f" With the bot wave pushed into their tower, opening through mid is worth {pushed_[0]:+.2f} points of "
                      f"win chance over walking down [{pushed_[1]:+.2f}, {pushed_[2]:+.2f}]; with their wave stacking against "
                      f"your ADC it is {slow[0]:+.2f} [{slow[1]:+.2f}, {slow[2]:+.2f}]. That slow push and a freeze on "
                      "their side are the reasons to go straight down; nothing else is.")
        died = sup.get("follow", {}).get("dies_adc_pp")
        if died:
            text += (f" And going through mid is not what gets your ADC killed: where high-elo supports open mid, the ADC "
                      f"dies in the next 90 s {died['matches']:.0f}% of the time when the support goes through mid and "
                      f"{died['no']:.0f}% when it walks straight down.")
        weight = (max(-1.0, min(2.0, (top_s - through_mid) / (top_s - base_s)))
                if top_s and base_s and top_s > base_s else 0.3)
        out.append(_pattern("opening", "Map openings", text, weight,
                             _ids(games, lambda m: m["kind"] == "opening" and m["tone"] == "bad"),
                             per_game=round(leaving / n, 1), count=leaving))
    judged = sum(x.get("roams") or 0 for x in num)
    if position == "UTILITY" and judged:
        good_ones_, bad, exposed = (sum(x.get(k) or 0 for x in num) for k in ("roams_good", "roams_bad", "roams_adc_exposed"))
        text = (f"Of your roams from lane, {good_ones_} paid (a kill, a summoner spell burned, their laner sent back) and "
                 f"{bad} went wrong. A roam is judged by the wave you leave behind, not only by what happens to your ADC: "
                 "with the wave crashed or pushing out the window is yours; with their wave stacking or frozen on their "
                 "side, it isn't.")
        if exposed:
            text += (f" {exposed} time{'s' if exposed > 1 else ''} your ADC died past the middle of the lane while you "
                      "were away on a good wave: that window is theirs to respect, and it doesn't make the roam a bad one.")
        roam = (openings_ or {}).get("roams") or {}
        if (bad_ := roam.get("slowpush rival")) and (good_one := roam.get("pushed")):
            text += (f" Across the 5,143 games, leaving your ADC with the wave pushed out makes them die "
                      f"{good_one['dies_60'][0]:+.0f} pp more in the next minute than staying would; leaving with their wave "
                      f"stacking, {bad_['dies_60'][0]:+.0f} pp, and with a freeze on their side, "
                      f"{roam['freeze rival']['dies_60'][0]:+.0f} pp. And it is a different death: on a good wave "
                      f"{good_one['exposed']:.0f}% of those ADCs die past the middle of the lane, which is on them; on a "
                      f"slow push {bad_['tower']:.0f}% die at their own tower, dived, which is on the wave you left.")
        out.append(_pattern("roam", "Roams", text, min(1.5, 1.5 * bad / judged) if bad else -0.2,
                             _ids(games, lambda m: m["kind"] == "roam" and m["tone"] == "bad"),
                             count=judged, per_game=round(bad / n, 1)))
    if position == "UTILITY" and (grade := vision_score(est, reference)):
        worst_ones = sorted(grade["parts"], key=lambda x: x["score"])
        text = (f"Vision score {grade['score']}/100 against {league} supports (50 is the tier's median). It is built only "
                 "from the things that actually climb with rank across the 5,143 games: how much vision you put out, "
                 f"how much of it finds their jungler, control wards, sweeps, and wards you don't waste. Best: "
                 f"{worst_ones[-1]['label'].lower()} ({worst_ones[-1]['score']}). Worst: {worst_ones[0]['label'].lower()} "
                 f"({worst_ones[0]['score']}).")
        util = _mean([x.get("wards_useful") for x in num])
        wards_ = _mean([x.get("wards") for x in num])
        seconds = _mean([x.get("ward_info_seconds") for x in num])
        empty = _mean([x.get("item_empty_share") for x in num])
        thrown = _mean([x.get("wards_unused_on_recall") for x in num])
        if wards_:
            text += (f" Of your {wards_:.0f} wards per game, {util or 0:.0f} showed an enemy nobody on your team was "
                      f"seeing: {seconds or 0:.0f} seconds of information a game.")
        if empty is not None:
            text += (f" You spend {empty:.0f}% of your time on the map with the item empty and go back to base with "
                      f"{thrown or 0:.1f} of its wards unused per game. Empty isn't the problem — Challenger supports "
                      "run empty more than Gold ones because they spend the charges faster. Going back with them "
                      "unspent is: that one falls from 1.9 wards per recall in Gold to 1.2 in Challenger.")
        out.append(_pattern("vision", "Vision", text, max(-1.0, min(2.0, (60 - grade["score"]) / 40)),
                             _ids(games, lambda m: m["kind"] == "ward" and m["tone"] == "bad"),
                             score=grade["score"], parts=grade["parts"]))

    # ── marksman: the damage in fights, the lane trades and the dive
    measured_ones = [x.get("fight_damage") for x in num if x.get("fight_damage") is not None]
    if position == "BOTTOM" and measured_ones:
        fights_ = sum(x.get("fights_measured") or 0 for x in num)
        carries = sum(x.get("fights_carried") or 0 for x in num)
        stays_silent = sum(x.get("fights_silent") or 0 for x in num)
        mean = sum(measured_ones) / len(measured_ones)
        text = (f"In the {fights_} real fights of these games you dealt {mean:.2f}x what the average player on your "
                 f"side dealt in the same fight. An ADC usually does 1.33x; the top quarter of ADC fights is 1.70x "
                 f"and the bottom quarter 0.77x. You carried {carries} of them and were under the bar in {stays_silent}. "
                 "Damage you don't land is your team fighting a player short, and it is the one thing nobody else "
                 "on the team can do for you.")
        out.append(_pattern("damage", "Damage in fights", text,
                             max(-1.0, min(2.0, (1.33 - mean) / 0.5)),
                             _ids(games, lambda m: m["kind"] == "damage" and m["tone"] == "bad"),
                             per_game=round(mean, 2), count=fights_))
    judged_ = sum((x.get("trades_won") or 0) + (x.get("trades_lost") or 0) for x in num)
    if position == "BOTTOM" and judged_:
        won_ones = sum(x.get("trades_won") or 0 for x in num)
        text = (f"Of the trades that decided something in your lane, you came out ahead in {won_ones} and behind in "
                 f"{judged_ - won_ones}. A trade is not the damage bar: it is how both sides end up in health, what "
                 "you each spent to get there, where the wave goes next and who can afford to walk back to base. "
                 "Losing one on health but crashing the wave and resetting is winning it — you come back full and "
                 "they don't.")
        out.append(_pattern("trade", "Trades in lane", text, min(1.5, 1.5 * (judged_ - won_ones) / judged_),
                             _ids(games, lambda m: m["kind"] == "trade" and m["tone"] == "bad"),
                             count=judged_, per_game=round((judged_ - won_ones) / n, 1)))
    plates_ = sum((x.get("plates_lane") or 0) + (x.get("plates_against") or 0) for x in num)
    if position in M.LANES and plates_:
        mine_list = sum(x.get("plates_lane") or 0 for x in num)
        against = plates_ - mine_list
        lane_ = M.LANES[position]
        worth = WINRATE_PER_PLATE[lane_]
        text = (f"Before 14:00 your lane took {mine_list} plates and gave up {against}, "
                 f"{(mine_list - against) / n:+.1f} per game ({abs(mine_list - against) * PLATE_GOLD:,} gold over {n} games). "
                 f"Plates are the cheapest gold in the game and the one thing in a lane that predicts the result: "
                 f"across 10,276 games, every plate of difference in {lane_} is worth {worth:.1f} points of win rate "
                 f"for the whole team, and a lane that ends 5 plates up wins "
                 f"{50 + 5 * worth:.0f}% of the time against {50 - 5 * worth:.0f}% when it ends 5 down. They also "
                 "compound: a turret you plated is a turret that falls to the first group, and from then on every "
                 "wave in that lane arrives on your terms.")
        out.append(_pattern("plate", "Plates in your lane", text,
                             max(-1.5, min(1.5, 0.3 * (against - mine_list) / n)),
                             _ids(games, lambda m: m["kind"] == "plate" and m["tone"] == "bad"),
                             count=plates_, per_game=round((mine_list - against) / n, 1)))
    dives = sum(x.get("dives_taken") or 0 for x in num)
    if position == "BOTTOM" and (dives or sum(x.get("waves_given_up") or 0 for x in num)):
        loose = sum(x.get("waves_given_up") or 0 for x in num)
        text = (f"{dives} time{'s' if dives != 1 else ''} you died holding a wave that was stacking into you with "
                 f"nobody of yours nearby and no sight of their jungler, and {loose} time"
                 f"{'s' if loose != 1 else ''} you gave that wave up and walked away. When they stack minions at "
                 "you and you are alone, the wave stops being yours: losing it whole costs far less than the dive, "
                 "even when the reason you are alone is your support's or your jungler's.")
        out.append(_pattern("dive", "Waves you can't hold", text, min(1.5, 0.75 * dives) if dives else -0.2,
                             _ids(games, lambda m: m["kind"] == "dive" and m["tone"] == "bad"),
                             count=dives + loose, per_game=round(dives / n, 1)))

    # ── jungle and support: where they are before each objective after 14
    decide = sum(x.get("setups") or 0 for x in num)
    if position in ("JUNGLE", "UTILITY") and decide:
        prepares = sum(x.get("setups_prepared") or 0 for x in num) / decide
        nothing = sum(x.get("setups_away") or 0 for x in num) / decide
        obj = (openings_ or {}).get("objectives") or {}
        own_entry = obj.get("leagues", {}).get(league.upper(), {}).get(position)
        top_o = obj.get("leagues", {}).get("CHALLENGER", {}).get(position)
        base_o = obj.get("leagues", {}).get("GOLD", {}).get(position)
        text = ("From 14:00 on the opening that matters is the objective: 45 seconds before it spawns you want to be "
                 f"around it, placing vision and looking for a pick. Of the {decide} dragons, Barons and Heralds that "
                 f"spawned with you on the map, you were already in the area {prepares:.0%} of the time, and {nothing:.0%} you "
                 "were somewhere else with nothing to show for it.")
        if top_o and base_o:
            text += (f" Where you are before an objective barely changes with rank (Challenger {role} are around the pit "
                      f"{top_o['prepares']:.0%} of the time, Gold ones {base_o['prepares']:.0%}); what it changes is who "
                      "ends up with the objective.")
        carries = obj.get("takes_it", {}).get(position, {})
        if carries.get("prepares") and carries.get("other spot and nothing"):
            text += (f" Teams take the objective {carries['prepares']:.0f}% of the time when their {role[:-1]} sets it up and "
                      f"{carries['other spot and nothing']:.0f}% when they are elsewhere for nothing.")
        # the direction is fixed (going elsewhere and getting nothing is the bad thing) and the scale is their own league: neither the
        # league ladder nor winning or losing separates here (Challenger sets up 53% and Gold 46-52%; within a
        # league, winners and losers differ by a point), and with gaps like that the comparison flipped the pattern.
        # 0.5 is what their league does, 0 is never going elsewhere for nothing
        weight = (max(-1.0, min(2.0, 0.5 + (nothing - own_entry["nothing"]) / max(0.15, own_entry["nothing"]))) if own_entry
                else 0.6 if nothing >= 0.3 else 0.3)
        out.append(_pattern("setup", "Objective setups", text, weight,
                             _ids(games, lambda m: m["kind"] == "setup" and m["tone"] == "bad"),
                             count=decide, reference=None))

    # ── laners: playing without knowing where the enemy jungler is
    if position in ("TOP", "MIDDLE", "BOTTOM"):
        blind = _mean([(e.get("blind_half_rival_blind") or 0) + (e.get("blind_overextend_blind") or 0)
                        for e in est if "blind_half_rival_blind" in e])
        r = _ref(reference, "blind_half_rival_blind", "blind_overextend_blind")
        if blind is not None:
            blind_deaths = _mean([(e.get("blind_half_rival_dies") or 0) + (e.get("blind_overextend_dies") or 0) for e in est])
            text = (f"Until 14:00 you spent {blind:.0f} seconds per game past the middle of your lane while the enemy "
                     f"jungler could have reached you unseen, and died {blind_deaths or 0:.1f} times per game in that "
                     "state. Without information you have to assume the jungler is in the closest bush: push when you know "
                     "where they are, or when your river is warded." + _against(blind, r, role, league, " s", 0))
            out.append(_pattern("exposure", "Playing without information", text, _weight(blind, r, 0.3),
                                 _ids(games, lambda m: m["kind"] == "death" and "no vision" in m.get("tags", [])),
                                 per_game=round(blind), reference=r))

    # ── fights
    lower = _mean([e.get("outnumbered_fights") for e in est])
    lost_ = [m for ms in mom for m in ms if (m["kind"] == "fight" and m["tone"] == "bad")
                or (m["kind"] == "death" and {"outnumbered", "item deficit"} & set(m.get("tags", [])))]
    r = _ref(reference, "outnumbered_fights")
    if lower is not None or lost_:
        value = sum(m.get("value") or 0 for m in lost_ if m["kind"] == "fight")
        text = (f"You took {lower or 0:.1f} fights per game with your side 1,000+ gold behind in items, and you were "
                 f"part of {len(lost_)} lost fights across {n} games." + _against(lower or 0, r, role, league, ""))
        text += (f" A won teamfight is worth about {WORTH['teamfight']:.0f} points of win chance (four kills) and a skirmish "
                  f"{WORTH['skirmish']:.1f}: the same swing goes the other way when you take the fight behind.")
        out.append(_pattern("fight", "Fights you shouldn't take", text, _weight(lower, r, 0.4),
                             _ids(games, lambda m: m in lost_), per_game=round(lower or 0, 1), count=len(lost_),
                             value=round(value, 1) or None, reference=r))

    # ── advantages that slip away
    defeats = [x for j, x in zip(games, num, strict=True) if not j.get("win")]
    from_ahead = [x for x in defeats if (x.get("wp_max") or 0) >= 60]
    if from_ahead:
        counts = ("In your only loss" if len(defeats) == 1 else
                   f"In {len(from_ahead)} of your {len(defeats)} losses")
        text = (f"{counts} your team was ahead at some point (60% or more to win). Those are the games to rewatch "
                 "first: each moment below is where the win chance collapsed, with what happened and where you were.")
        out.append(_pattern("swing", "Leads that slipped", text, 1.5 * len(from_ahead) / len(defeats),
                             _ids(games, lambda m: m["kind"] == "swing"), count=len(from_ahead)))

    # ── flash, backs, departures and the support's roams
    flash = _mean([e.get("flash_suboptimal") for e in est])
    bad = sum(1 for ms in mom for m in ms if m["kind"] == "flash")
    r = _ref(reference, "flash_suboptimal")
    if bad:
        text = ("After 14:00, a Flash spent in a skirmish or outside any fight with the next dragon due before it comes "
                 f"back: {flash or bad / n:.1f} per game." + _against(flash or bad / n, r, role, league, "") +
                 " It's a small cost each time, about 2 points of chance to take that dragon per player without Flash.")
        out.append(_pattern("flash", "Flash timing", text, min(_weight(flash, r, 0.2), 0.8),
                             _ids(games, lambda m: m["kind"] == "flash"), count=bad, reference=r))
    judged_ = sum(x.get("recalls_judged") or 0 for x in num)
    if position in ("TOP", "MIDDLE", "BOTTOM") and judged_:
        good_ones_ = sum(x.get("recalls_good") or 0 for x in num)
        text = (f"Of the {judged_} recalls where the wave said something, {good_ones_} were on a wave that let you go "
                 f"and {judged_ - good_ones_} were not. A recall is decided by where the wave is when you press it, not "
                 "by what you lose walking back: crashed into their tower or collected under yours you lose nothing, "
                 "a cannon in the middle holds the wave until you return, and a freeze or a wave rolling with no "
                 "cannon in it is a wave you are giving away whole. Nobody has this one solved: across the 5,143 "
                 "games of the reference, Gold and Challenger laners both get it right about 56% of the time, so "
                 "it is free gold for whoever makes a habit of it.")
        out.append(_pattern("back", "Recall timing", text,
                             min(1.5, 1.5 * (judged_ - good_ones_) / judged_),
                             _ids(games, lambda m: m["kind"] == "back" and m["tone"] == "bad"),
                             count=judged_, per_game=round((judged_ - good_ones_) / n, 1)))
    for kind, title, column, explains in (
            ("roam", "Leaving your lane", "departures_cs_lost", "minions lost while you were away from lane"),):
        own_items = [m for ms in mom for m in ms if m["kind"] == kind]
        cs = _mean([e.get(column) for e in est])
        r = _ref(reference, column)
        if position in ("TOP", "MIDDLE", "BOTTOM") and cs is not None:
            text = (f"{cs:.1f} {explains} per game, about {cs * MINION_PRICE:,.0f} gold per game."
                     + _against(cs, r, role, league, " CS"))
            out.append(_pattern(kind, title, text, _weight(cs, r, 0.3), _ids(games, lambda m, t=kind: m["kind"] == t),
                                 count=len(own_items), per_game=round(cs, 1), gold=-round(cs * MINION_PRICE * n) or None,
                                 reference=r))
    return sorted(out, key=lambda x: -x["weight"])


if __name__ == "__main__":  # the minimal check: the map's places and the patterns of two invented matches
    assert place(600, 600, "100") == "your base" and place(14000, 14000, "100") == "the enemy base"
    assert place(1200, 9000, "100") == "top lane" and place(9000, 1200, "200") == "bot lane"
    assert place(7700, 7900, "100") == "mid lane" and "pit" in place(9800, 5000, "100").lower()  # the names are from zones.json
    names = [b["name"] for b in _bushes()]
    assert len(set(names)) == len(names), "two bushes with the same name"
    for b in _bushes():  # a point inside each bush belongs to that bush and `place` says so, with its zone after
        x, z = next((x, z) for x in range(int(min(q[0] for q in b["polygon"])), int(max(q[0] for q in b["polygon"])), 10)
                    for z in range(int(min(q[1] for q in b["polygon"])), int(max(q[1] for q in b["polygon"])), 10) if _inside(x, z, b["polygon"]))
        assert bush_at(x, z) == b["name"] and f" in {place(x, z, '100', bush=False)}" in place(x, z, "100"), b["name"]
    assert bush_at(7700, 7900) is None and place(7700, 7900, "100") == "mid lane"  # the middle of the map isn't a bush
    assert place(3800, 7800, "100") == "your jungle (top side)" and place(3800, 7800, "200") == "the enemy jungle (top side)"
    death = {"kind": "death", "tone": "bad", "severity": 3, "id": 0, "t": 300.0, "tags": ["no vision"], "gold": -300,
              "text": "…"}
    games = [{"match_id": "A", "win": False, "moments": [death], "numbers": {"wp_max": 70}},
              {"match_id": "B", "win": True, "moments": [], "numbers": {"wp_max": 90}}]
    ref = {"deaths": [2, 3, 5, 7, 9, 5.5, 4.2, 6.9, 1000]}
    p = patterns(games, ref, "MASTER", "TOP")
    deaths_ = next(x for x in p if x["kind"] == "death")
    assert deaths_["per_game"] == 0.5 and deaths_["moments"] == ["A:0"] and "4.2" in deaths_["text"], deaths_
    assert next(x for x in p if x["kind"] == "swing")["count"] == 1
    assert _towards(4.2, {"median": 5, "winners": 4.2, "losers": 6.9}) == 0
    assert _towards(80, {"median": 75, "winners": 80, "losers": 70}) == 0
    assert _towards(3.5, {"median": 6.1, "winners": 6.3, "losers": 5.9}) is None  # it doesn't separate: it doesn't score
    assert _towards(99, {"median": 5, "winners": 4.2, "losers": 6.9}) == 2  # acotado
    # a support who opens through the middle like Challengers do (from what they do well) and with the median vision (50)
    own = [{"match_id": "C", "win": True, "moments": [],
             "numbers": {"openings": 10, "openings_mid": 6, "openings_clear": 4, "openings_matched": 3},
             "stats": {"guard_wards_10": 10.0, "control_placed_10": 1.5, "sweeps_10": 3.0}}]
    ref = {"guard_wards_10": [6, 8, 10, 12, 14, 10, 10.5, 9.5, 100], "control_placed_10": [.5, 1, 1.5, 2, 2.5, 1.5, 1.5, 1.5, 100],
           "sweeps_10": [1, 2, 3, 4, 5, 3, 3, 3, 100]}
    p = patterns(own, ref, "MASTER", "UTILITY", {"support": {"opens_mid": {"CHALLENGER": 0.6, "MASTER": 0.4, "GOLD": 0.1}}})
    opens = next(x for x in p if x["kind"] == "opening")
    assert opens["weight"] == 0 and opens["tone"] == "good" and "60%" in opens["text"], opens
    grade_ = next(x for x in p if x["kind"] == "vision")
    assert grade_["score"] == 50 and [x["score"] for x in grade_["parts"]] == [50, 50, 50], grade_
    # plates: only runs that move MIN_PLATES of difference come out, and the text carries what they are worth
    assert _plates_txt(3, 0) == "Your lane took 3 plates" and _plates_txt(0, 1) == "They took 1 plate off you"
    assert _plates_txt(2, 1) == "You traded 2 plates for 1"
    plates_ = [{"plates_lane": 1, "plates_against": 5}, {"plates_lane": 0, "plates_against": 2}]
    p = patterns([{"match_id": "D", "win": False, "moments": [], "numbers": plates_[0], "stats": {}},
                  {"match_id": "E", "win": False, "moments": [], "numbers": plates_[1], "stats": {}}], {}, "GOLD", "MIDDLE")
    pl = next(x for x in p if x["kind"] == "plate")
    assert pl["per_game"] == -3.0 and pl["tone"] == "bad" and "6.5 points" in pl["text"], pl

    # a match's grade: each moment adds or subtracts by its kind and severity, and is brought to 30 minutes
    moment_list = [{"kind": "death", "tone": "bad", "severity": 2}, {"kind": "death", "tone": "bad", "severity": 1},
                {"kind": "play", "tone": "good", "severity": 3}, {"kind": "fight", "tone": "bad", "severity": 3},
                {"kind": "opening", "tone": "neutral", "severity": 1}]
    n = grade(moment_list, 60 * 60)  # a one-hour match: the points are worth half
    assert n["total"] == round((-0.8 * 3 + 1.2 * 3) / 2, 1) == 0.6, n
    assert [d["kind"] for d in n["parts"]] == ["death", "play"] and n["parts"][0]["bad"] == 2, n
    games_ = [{"role": "JUNGLE", "rating": n}]
    grades(games_, {"JUNGLE": [-20.0, -10.0, -5.0, 0.6, 10.0]})
    assert games_[0]["rating"]["score"] == 70, games_  # the 65th percentile of their league scores 70
    print("ok")
