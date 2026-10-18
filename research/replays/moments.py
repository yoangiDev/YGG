"""Moments that cost the match, with the context only the replay gives.

    python research/replays/moments.py <game.state.csv> <match.json> <timeline.json> [<events.json>]
    python research/replays/moments.py <game.state.csv> - - <events.json>   # without the WP model

It joins the two halves of the system: `lol-replay-decoder` extracts the replay's state table (one row per
champion and second: position, vision, objective, crowd control, stats, cooldowns) and from here comes
the value of each event, the WPA of the `research/ladder` model (4,276 Challenger matches).

For each event with a cost, the ten previous seconds are printed as the game saw them. The feature that
really separates is `saw_the_killer`: the killer's `seen` column is, by definition, "visible to your
team", so it distinguishes the unseen gank from the head-on fight.

Events are ordered **within their stretch of the match**: the WPA of a death saturates with the minute (all
from 35 onward are worth the same), so raw only late deaths would come out.

Two more things come out that the timeline can't give: the stretches in which a team loses gold and experience
with nobody dying and nothing falling (`silences`, split among players with `culprits`) and, with the decoder's events
JSON, what it costs each jungler to leave their small camps alive (`idle_jungle`).

With that same JSON the **wave control** (`lane_waves`) also comes out, which the timeline doesn't touch at all:
where each wave is second by second, how many minions each side has, which carry a cannon and who
collects each minion. On top of that go the lane rules: `backs` (going back to base after clearing the
wave before the cannon one), `freezes` (the wave stopped between your turret and the middle, held with
fewer minions than the enemy), `stacks` (the slow push's crash against the turret, what is done with the window
it opens and who arrives at the rebound), `accumulations` (the slow push seen from before the crash, with its
four endings: it crashes, the enemy holds it, it eats itself or it dissolves) and `payoff` (what each one does
with the prio their crash gives them: going back to base, vision —in the jungle or in lane, and at what depth—,
harass under tower, rotate or go into fog, and whether they had a ward to have placed it) and `exposure`
(how long each laner plays in enemy territory without knowing where the enemy jungler is) and `show_up`,
which is the other side: how long the jungler goes without being seen and what they get from the times they show themselves.
And `vision`, which measures each ward by the only thing that makes it good: whom it showed and for how many seconds.

For the lane itself, `trades` extracts each exchange of blows with what each spends, how it ends and what the wave
does afterwards, and `gold_in_lane` the gold that leaves the lane: minions and plates (`plates`, from the timeline's
`TURRET_PLATE_DESTROYED`, extracts each one with its minute and who took it). And `departures`,
which is where that advantage is carried to: each time a laner leaves their lane, if they had it won, with
whom they join, what they get and what it costs them in minions.

From minute 14 each one's job changes. `sidelanes` measures the sidelaner's —pushing the
side lane whenever possible without dying, with the information and tools they have— and `cost_of_dying`
what a death costs each position, which isn't the same for a marksman as for a support. And
`overgroup` marks the CS that dies on its own under a side lane's turret with the team grouped elsewhere,
which can't be blamed on anyone and so appears in no statistic. And `side_balance` looks at it
as an episode: leaving a side lane isn't paid for once, it keeps being paid for every wave until someone goes.

The jungle/support duo's job is `zones`: the six zones that are controlled —the four sectors of the
jungle and the two pits— with the vision each team places inside and the facechecks it punishes. And
`setups`, which looks at each objective from a minute and a half before it falls, which is when it is really
decided: who arrives first, who has the vision in place and who takes the other's away.
"""

import bisect
import collections
import csv
import itertools
import gzip
import json
import math
import statistics
import sys
from pathlib import Path

from ygg_core.metrics.wpa import FEATURES, PHASES, GameState, WpaEvent, blue_log_odds, wpa_report
from ygg_core.metrics.wpa_model import MODEL

WINDOW = 10.0  # seconds of context before the event


def _clock(t: float) -> str:
    """mm:ss. With `// 60` and `%%60:.0f` 59.6 s came out as "8:60"."""
    return f"{int(t) // 60}:{int(t) % 60:02d}"


REVIVE = 15.0  # two deaths of the same champion closer than this are the same one (see drop_revived)


def drop_revived(events: dict) -> dict:
    """Removes the repeated deaths of whoever gets up and falls again, and gives their place to the camps that
    the decoder leaves at (0, 0) (see `with_spot`). It is where everyone who reads a match passes through.

    Sion's passive puts the champion back on their feet a few seconds before falling for good, and the Guardian Angel or Zilean's ult
    do the same: the game sends a `Death` for each fall and the scoreboard counts only one. Measured
    in one match: 16 packets for the 12 deaths of the statsJson, in four pairs 7-9 s apart. Without this,
    `cost_of_dying` charges Sion four deaths and four respawn times that didn't exist.
    And when Akshan kills the culprit, their ally respawns early with another `Death`, sometimes 23 s
    later, so the window alone isn't enough. That packet has a signature: it arrives with the champion still dead and carries
    as its counter exactly what they had been dead. With it one knows they are alive again, and the window
    starts counting from zero: Mel revived at 4.6 s and dead again 11 s later are two deaths. The
    same rule is in `deaths` of cosecha.py (in the decoder)."""
    last: dict[str, float] = {}  # the last Death, whatever it is
    until: dict[str, float] = {}  # until when they are dead
    counted: dict[str, float] = {}  # the last death that counts
    out = []
    for e in events["events"]:
        if e["type"] == "Death":
            who, t, r = e["net_id"], e["time"], e["respawn_time"]
            revive = t < until.get(who, t) and abs(r - (t - last[who])) < 0.05
            fresh = not revive and t - counted.get(who, -REVIVE) >= REVIVE
            if revive:
                counted.pop(who, None)
            if fresh:
                counted[who] = t
            last[who], until[who] = t, (t if revive else t + r)
            if not fresh:
                continue
        out.append(e)
    return events | {"events": out, "camps": with_spot(events)}


# for each camp, how its main monster's name starts (lowercase: the crab is "Sru_Crab")
MAIN = {"Gromp": "sru_gromp", "Wolves": "sru_murkwolf", "Raptors": "sru_razorbeak", "Krugs": "sru_krug",
             "Red": "sru_red", "Blue": "sru_blue", "Scuttle": "sru_crab", "Baron": "sru_baron",
             "Herald": "sru_riftherald", "Voidgrub": "sru_horde", "Dragon": "sru_dragon"}


def with_spot(events: dict) -> list[dict]:
    """The camps, with their place and side even if the decoder left them at (0, 0).

    For 3% of monster deaths the packet carries no place (in some match, all the Gromps), and
    since the side comes from the place, the red Gromp that the red jungler clears ended up counted as the blue side's: a
    camp cleared twice in a minute and a respawn period of 63 s instead of 141. The real place
    is in the match itself: it is where the monster that dies (`UnitDeath`) was born (`SpawnNeutral`) at that same
    instant. The side is recomputed as in the decoder: the river diagonal, and for the crab, top or bottom."""
    spawned = {e["net_id"]: e for e in events["events"] if e["type"] == "SpawnNeutral"}
    dying = [(e["time"], spawned[e["net_id"]]) for e in events["events"]
              if e["type"] == "UnitDeath" and e["net_id"] in spawned]
    out = []
    for c in events["camps"]:
        if any(c["position"]):
            out.append(c)
            continue
        main_camp = MAIN.get(c["camp"].split(" ")[0])
        spawn = next((s for t, s in dying if abs(t - c["time"]) < 0.05 and main_camp
                      and s["character"].lower().startswith(main_camp)), None)
        if spawn is None:
            out.append(c)
            continue
        x, z = spawn["position"]
        c = c | {"position": [x, z]}
        if "side" in c:
            c["side"] = ("top" if z > x else "bot") if c["camp"] == "Scuttle" else ("blue" if x + z < RIVER else "red")
        out.append(c)
    return out


def open_file(path: Path):
    """The file, compressed or not: the harvest stores them as .gz because they are 33 MB per match raw."""
    return gzip.open(path, "rt", encoding="utf-8") if path.suffix == ".gz" else path.open(encoding="utf-8")


class StateTable(collections.defaultdict):
    """The state table per champion, with each one's seconds at hand (`times`) to look up a stretch without
    walking the whole thing: `_window` is called more than a thousand times per match and was a fifth of the time."""

    def __init__(self) -> None:
        super().__init__(list)
        self.times: dict[str, list[float]] = {}


def read_state(path: Path) -> dict[str, list[dict[str, str]]]:
    """The replay's table (--state), per champion and in time order.

    `seen` ("the opposing team sees them") comes out in the table from a geometric calculation: within 1350 of an enemy champion or
    900 of a ward, without walls, bushes or stealth, and not counting minions or turrets. If alongside there is the visibility
    sent by the game itself (`<match>.vision.json.gz`, from harvest 2.0), that one is used: the second counts as
    seen if the enemy has it in view at some moment of it. The two differ in one of every five seconds of a
    live champion; the game's sees more of the laners (minions also look) and less of whoever is behind
    a wall."""
    rows = StateTable()
    with open_file(path) as fh:
        for row in csv.DictReader(fh):
            rows[row["champion"]].append(row)
    vision = path.with_name(path.name.split(".")[0] + ".vision.json.gz")
    if vision.exists():
        with open_file(vision) as fh:
            seen = json.load(fh)["seen"]
        for own_rows in rows.values():
            spans, i = seen.get(own_rows[0]["net_id"], []), 0
            for row in own_rows:
                t = int(float(row["time"]))
                while i < len(spans) and spans[i][1] < t:
                    i += 1
                row["seen"] = str(i < len(spans) and spans[i][0] < t + 1)
    return rows


def read_turrets(path: Path) -> dict[str, list[tuple[float, float]]]:
    """Each turret's health every time it changes, from the `<match>.torres.json.gz` that the harvest leaves beside the
    table: {network id: [(second, health), ...]}. Empty if the match was harvested before it existed.

    Only turrets that get hit send measurements: a turret that isn't here is a turret nobody has
    touched. Each one's maximum health doesn't come either: the first measurement is already after the first hit."""
    file = path.with_name(path.name.split(".")[0] + ".torres.json.gz")
    if not file.exists():
        return {}
    with open_file(file) as fh:
        return {net: [(t, v) for t, v in series] for net, series in json.load(fh)["torres"].items()}  # the decoder's own key


def _num(row: dict[str, str], column: str) -> float | None:
    """That column's value, or None if it doesn't carry it (blank, or `nan`: one match out of 5144 writes it that way)."""
    value = row.get(column)
    return float(value) if value not in (None, "", "nan") else None


def _window(rows, champion: str, since: float, until: float) -> list[dict[str, str]]:
    own_rows = rows.get(champion, [])
    if not isinstance(rows, StateTable):  # a hand-made table (the checks): it is walked
        return [f for f in own_rows if since <= float(f["time"]) <= until]
    times = rows.times.get(champion)
    if times is None or len(times) != len(own_rows):  # the rows are in time order: the stretch is looked up
        times = rows.times[champion] = [float(f["time"]) for f in own_rows]
    return own_rows[bisect.bisect_left(times, since):bisect.bisect_right(times, until)]


def _visible(rows, champion: str, until: float, seconds: float) -> float | None:
    """What share of those seconds the unit was visible to the opposing team."""
    stretch = _window(rows, champion, until - seconds, until)
    return sum(f["seen"] == "True" for f in stretch) / len(stretch) if stretch else None


def context(rows, champion: str, t: float, killer: str | None = None) -> dict[str, object]:
    """The ten seconds before the event, in the terms a coach speaks in."""
    stretch = _window(rows, champion, t - WINDOW, t)
    if not stretch:
        return {}
    start_, end = stretch[0], stretch[-1]
    enemy = [d for f in stretch if (d := _num(f, "enemy_dist"))]
    ally = [d for f in stretch if (d := _num(f, "ally_dist"))]
    changes = [float(f["time"]) for f in stretch if int(f["vision_changes"] or 0) > 0]
    health = (_num(start_, "health") or 0) / (_num(start_, "health_max") or 1)
    out = {
        "health_on_entering": f"{health:.0%}",
        "gold_unspent": round(_num(start_, "gold") or 0),
        "spells_ready": f"{sum(end[f'{s}_ready'] == 'True' for s in 'qwerdf')}/6",
        "nearest_ally": round(sum(ally) / len(ally)) if ally else None,
        "nearest_enemy": round(min(enemy)) if enemy else None,
        "me_saw": f"{v:.0%}" if (v := _visible(rows, champion, t, WINDOW)) is not None else "—",
        "last_vision_change": f"{t - changes[-1]:.0f} s" if changes else "—",
        "seconds_with_cc": sum(1 for f in stretch if f["cc"]),
    }
    if killer:
        before, latest = _visible(rows, killer, t - 3, 7), _visible(rows, killer, t, 3)
        if before is not None:
            out["saw_the_killer"] = f"{before:.0%} before, {latest:.0%} in the last 3 s"
    return out


def moment_list(match: dict, timeline: dict) -> list[tuple[float, str, WpaEvent]]:
    """(WPA, champion, event) of everything that cost points, from the most expensive to the least."""
    out = []
    for participant in match["info"]["participants"]:
        report = wpa_report(match, timeline, participant["puuid"], MODEL)
        if report is None:
            continue
        out += [(e["wpa"], participant["championName"], e) for e in report.events if e["wpa"] < -1]
    return sorted(out, key=lambda m: m[0])


def by_stretch(items: list[tuple[float, str, WpaEvent]]) -> dict[int, list[tuple[float, str, WpaEvent]]]:
    """The moments split by the stretch of the match they belong to (PHASES of the WP model)."""
    out: dict[int, list] = collections.defaultdict(list)
    for m in items:
        minute = m[2]["time"] / 60
        out[max(p for p in PHASES if p <= minute)].append(m)
    return out


def wp_curve(state: GameState, step: float = 1.0) -> list[tuple[float, float]]:
    """(second, log-odds of the blue team) over the whole match. The model already accepts any instant:
    it uses the gold of the last closed minute plus that of the later events, and the objectives, exact."""
    end = state.duration_ms / 1000
    return [(t, blue_log_odds(state.features(t * 1000, MODEL.event_gold), MODEL))
            for t in (step * k for k in range(int(end / step) + 1))]


def economy(rows, step: float = 1.0) -> list[tuple[float, float, float]]:
    """(second, blue - red gold, blue - red xp) from the replay, exact: the timeline only gives them per minute."""
    per_second: dict[float, list[float]] = collections.defaultdict(lambda: [0.0, 0.0])
    for champion, own_rows in rows.items():
        for f in own_rows:
            sign = 1 if f["team"] == "100" else -1
            running = per_second[float(f["time"])]
            running[0] += sign * (_num(f, "total_gold") or 0)
            running[1] += sign * (_num(f, "xp") or 0)
    return [(t, *per_second[t]) for t in sorted(per_second) if t % step == 0]


def _points(gold: float, xp: float, minute: float) -> float:
    """Gold and experience translated into WP points with the model's weights, neutral (log-odds over 4)."""
    weights = MODEL.coefficients[max(k for k, phase in enumerate(PHASES) if phase <= minute)]
    return (weights[1 + FEATURES.index("gold_k")] * gold / 1000 + weights[1 + FEATURES.index("xp_k")] * xp / 1000) / 4 * 100


def gains(rows, horizon: float = 30.0) -> dict[str, list[tuple[float, float]]]:
    """Per champion: (start second, WP points gained in the following `horizon` seconds)."""
    out = {}
    for champion, own_rows in rows.items():
        series = [(float(f["time"]), _num(f, "total_gold") or 0, _num(f, "xp") or 0) for f in own_rows]
        stride = int(horizon)
        out[champion] = [(t0, _points(gold1 - gold0, xp1 - xp0, t0 / 60))
                           for (t0, gold0, xp0), (_t1, gold1, xp1) in zip(series, series[stride:])]
    return out


def culprits(rows, gains: dict[str, list[tuple[float, float]]], t0: float, team: str,
              how_many: int = 2, above: bool = False) -> list[tuple[str, float, float]]:
    """Who strays from their pace in that stretch: (champion, what they gained, what they usually gain), in WP points.

    `above` reverses the order: it serves for the team that takes the stretch.

    Each player's pace is their median in that same phase of the match, so it compares each one with
    themselves: a support isn't measured against a marksman's pace.

    ponytail: it is an attribution by economy. It doesn't see who *should* have been there; for that the value
    model with position and vision is needed."""
    phase = max(f for f in PHASES if f <= t0 / 60)
    out = []
    for champion, series in gains.items():
        if (rows[champion][0]["team"] == "100") != (team == "blue"):
            continue
        same_phase = sorted(p for tt, p in series if max(f for f in PHASES if f <= tt / 60) == phase)
        now = next((p for tt, p in series if tt == t0), None)
        if now is None or not same_phase:
            continue
        out.append((champion, now, same_phase[len(same_phase) // 2]))
    return sorted(out, key=lambda c: (c[2] - c[1]) if above else (c[1] - c[2]))[:how_many]


def silences(rows, state: GameState, items, horizon: float = 30.0, minimum: float = 1.0,
              since: float = 120.0):
    """Windows in which a team loses value with nothing "official" happening: no deaths, no objectives.

    The value is measured with the replay's gold and XP translated into WP points with the model's weights, and
    neutral (log-odds over 4), like the events' WPA: that way an already lost game doesn't crush the rest.
    They are the mistakes the timeline can't see: lost waves, bad backs, a stolen jungle.

    ponytail: it attributes the window to the team, not the player; to point at one the value model
    trained with replay features is needed."""
    econ = economy(rows)
    events = sorted(e["time"] for _, _, e in items)
    out = []
    for i, (t0, gold0, xp0) in enumerate(econ):
        j = i + int(horizon)
        if j >= len(econ):
            break
        if t0 < since:  # before the minions spawn there is only the initial gold trickle
            continue
        t1, gold1, xp1 = econ[j]
        if any(t0 - 5 <= e <= t1 + 5 for e in events):  # what an event already explains isn't a silence
            continue
        weights = MODEL.coefficients[max(k for k, p in enumerate(PHASES) if p <= t0 / 60)]
        change = (weights[1 + FEATURES.index("gold_k")] * (gold1 - gold0) / 1000
                  + weights[1 + FEATURES.index("xp_k")] * (xp1 - xp0) / 1000)
        points = change / 4 * 100  # neutral: the log-odds change is worth this in WP points at 50%
        if abs(points) >= minimum:
            out.append((points, t0, t1, gold1 - gold0, xp1 - xp0))
    out.sort(key=lambda s: -abs(s[0]))
    non_overlapping: list[tuple[float, float, float, float, float]] = []  # the same drop comes out in 30 consecutive windows
    for s in out:
        if all(s[2] <= other[1] or s[1] >= other[2] for other in non_overlapping):
            non_overlapping.append(s)
    return non_overlapping


SMALL = ("Gromp", "Wolves", "Raptors", "Krugs")  # not the buffs: they are cleared half as often (300 s against 135)
# the start of the unit names of each small camp (SRU_KrugMini and SRU_KrugMiniMini are Krugs)
UNITS = {"SRU_Gromp": "Gromp", "SRU_Murkwolf": "Wolves", "SRU_Razorbeak": "Raptors", "SRU_Krug": "Krugs"}


def idle_jungle(events: dict, rows, period: float | None = None, until: float | None = None,
                  margin: float = 15.0) -> dict[str, dict]:
    """What each jungler loses by leaving their small camps alive.

    A small camp comes back every `period` seconds. Each second it is alive uncleared delays all
    the following clears, so the cost isn't that of that respawn: it is one clear fewer for every
    `period` accumulated seconds. Each camp's value is measured in the match itself (the gold of its
    Gold events and the XP the jungler gains on clearing it), not with patch constants.

    `margin` is the seconds they are forgiven to arrive and kill it. The measured `period` (the shortest gap
    in the match) already carries some of that time inside, so the effective margin is somewhat larger: it is the
    dial to calibrate it if the alerts come out tight.

    A camp the enemy takes isn't stalled (it respawns on schedule), but its gold belongs to the other: it goes
    separately, in `thefts`, and those they take from the enemy in `invasions`. What is compared is `lost_and_stolen`:
    with only the stalled ones, winning junglers came out worse than losing ones (in 600 Master matches, 3.96
    stalled clears against 3.63), because the losers get robbed more (1.50 against 0.98) and the winners
    take more from the enemy (1.43 against 0.95). With the thefts, the winners lose less (4.94 against 5.13)."""
    team_of = {p["champion"]: p["team"] for p in events["players"]}
    net_of = {p["champion"]: p["net_id"] for p in events["players"]}
    owner_of = {p["net_id"]: (p["champion"], p["team"]) for p in events["players"]}
    junglers = {p["team"]: p["champion"] for p in events["players"] if p["position"] == "JUNGLE"}
    end = min(until or events["game_length"], events["game_length"])
    all_: dict[tuple[str, str], list[float]] = collections.defaultdict(list)
    for c in events["camps"]:
        if c["camp"] in SMALL:
            all_[(c["camp"], c["side"])].append(c["time"])
    if period is None:  # the patch's respawn, measured with the whole match: the shortest gap seen
        # of more than a minute: the same camp recorded twice at the same instant gave a period of 0
        gaps = [b - a for v in all_.values() for a, b in zip(sorted(v), sorted(v)[1:]) if b - a > 60]
        period = min(gaps) if gaps else 135.0
    clears = {k: [t for t in v if t <= end] for k, v in all_.items()}

    # The gold of a clear is what whoever does it collects for that camp's units: the big krug, the
    # medium ones and the small ones that come out on splitting (SpawnMinion), and so on for all. Summing all the monster gold
    # at ±8 s pulled in the neighbouring camp and even the enemy jungler clearing at the same time: it gave Krugs of 42 and
    # a Gromp of 160 (with the blue one inside). Measured this way, in 16.19: Gromp 80, Wolves 85, Raptors 75.
    name = {e["net_id"]: e.get("character") or e.get("name") or "" for e in events["events"]
              if e["type"] in ("SpawnNeutral", "SpawnMinion")}
    payouts: dict[tuple[str, str], list[tuple[float, float]]] = collections.defaultdict(list)
    for e in events["events"]:
        if e["type"] == "Gold" and (camp := next((c for pre, c in UNITS.items()
                                                 if name.get(e["unit"], "").startswith(pre)), None)):
            payouts[(e["net_id"], camp)].append((e["time"], e["amount"]))
    value: dict[str, tuple[float, float]] = {}
    for camp in SMALL:
        golds, xps = [], []
        for c in events["camps"]:
            if c["camp"] != camp or c["time"] > end:
                continue
            t0, jungler = c["time"], junglers.get("100" if c["side"] == "blue" else "200")
            gold = sum(a for tt, a in payouts[(c.get("killer"), camp)] if abs(tt - t0) <= 20)
            before = _window(rows, jungler, t0 - 8, t0 - 6)
            after = _window(rows, jungler, t0 + 6, t0 + 8)
            if gold:
                golds.append(gold)
            if before and after:  # ponytail: the XP doesn't come per unit, so it carries that of the neighbouring camp
                # if they clear it in a row; to separate it each monster death's XP would be needed
                xps.append(max(0.0, (_num(after[0], "xp") or 0) - (_num(before[-1], "xp") or 0)))
        value[camp] = (statistics.median(golds) if golds else 0.0, statistics.median(xps) if xps else 0.0)

    out: dict[str, dict] = {}
    for side, team in (("blue", "100"), ("red", "200")):
        jungler = junglers.get(team)
        if not jungler:
            continue
        detail, total_delay, gold_cost, xp_cost = [], 0.0, 0.0, 0.0
        for camp in SMALL:
            times = sorted(clears.get((camp, side), []))
            if not times:
                continue
            delays = [max(0.0, b - a - period - margin) for a, b in zip(times, times[1:])]
            delays.append(max(0.0, end - times[-1] - period - margin))  # what remains alive until the end
            gold, xp = value[camp]
            total_delay += sum(delays)
            gold_cost += sum(delays) / period * gold
            xp_cost += sum(delays) / period * xp
            # each stretch it was alive too long: [from, to], from when its margin runs out to when it is cleared
            windows = [[round(a + period + margin, 1), round(a + period + margin + r, 1)]
                        for a, r in zip(times, delays, strict=True) if r > 0]
            detail.append({"camp": camp, "clears": len(times), "delay": sum(delays),
                            "first_delay": delays[0] if delays else 0.0,
                            "lost": sum(delays) / period, "gold_camp": gold, "xp_camp": xp,
                            "windows": windows})
        small = [c for c in events["camps"] if c["camp"] in SMALL and c["time"] <= end]
        thefts = [{"t": round(c["time"], 1), "camp": c["camp"], "who": owner_of[c["killer"]][0],
                  "gold": value[c["camp"]][0]} for c in small
                 if c["side"] == side and owner_of.get(c.get("killer"), ("", team))[1] != team]
        invasions = [{"t": round(c["time"], 1), "camp": c["camp"], "gold": value[c["camp"]][0]}
                      for c in small if c["side"] != side and c.get("killer") == net_of[jungler]]
        out[jungler] = {"team": team_of[jungler], "period": period, "margin": margin, "delay": total_delay,
                         "clears_lost": total_delay / period, "gold": gold_cost, "xp": xp_cost,
                         "points": _points(gold_cost, xp_cost, 20), "detail": detail,
                         "stolen": len(thefts), "stolen_gold": sum(r["gold"] for r in thefts),
                         "invade": len(invasions), "invade_gold": sum(r["gold"] for r in invasions),
                         "lost_and_stolen": total_delay / period + len(thefts),
                         "thefts": thefts, "invasions": invasions}
    return out


def recall_before_second_clear(events: dict, rows, period: float = 138.0) -> dict[str, dict]:
    """The jungler has to pass through the shop before starting their second clear.

    The second clear starts at the first of their own small camps to respawn. If they arrive there without having
    bought anything since the first began, it is a conceptual mistake: they carry the gold in their pocket and do the
    second clear with the same kit as the first. It is looked at with the purchases (BuyItem) and the `recall` buff,
    both from the replay."""
    junglers = {p["team"]: p["champion"] for p in events["players"] if p["position"] == "JUNGLE"}
    net_of = {p["champion"]: p["net_id"] for p in events["players"]}
    out = {}
    for side, team in (("blue", "100"), ("red", "200")):
        jungler = junglers.get(team)
        if not jungler:
            continue
        own_ones = sorted((c["time"], c["camp"]) for c in events["camps"]
                         if c["camp"] in SMALL and c["side"] == side)
        if not own_ones:
            continue
        first, which = own_ones[0]
        respawns = first + period  # the first small camp to respawn: the second clear starts there
        starts = next((t for t, _ in own_ones if t > respawns), None)
        purchases = [e["time"] for e in events["events"]
                   if e["type"] == "BuyItem" and e["net_id"] == net_of[jungler] and first < e["time"] < (starts or respawns)]
        recalls = [e["time"] for e in events["events"]
                   if e["type"] == "AddBuff" and e["net_id"] == net_of[jungler] and e["buff"].lower() == "recall"
                   and first < e["time"] < (starts or respawns)]
        row = next((f for f in rows[jungler] if float(f["time"]) >= (starts or respawns)), None)
        out[jungler] = {"first_camp": which, "respawn": respawns, "starts_second": starts,
                         "purchases": len(purchases), "recalls": len(recalls),
                         "gold_unspent": round(_num(row, "gold") or 0) if row else None}
    return out


TOPSIDE = {"blue": {"Gromp", "Blue", "Wolves"}, "red": {"Krugs", "Red", "Raptors"}}  # the upper half of each jungle


def _lane(x: float, z: float) -> str:
    """Lane by map zone: the diagonal is mid, above it top and below it bot."""
    return "mid" if abs(x - z) < 2200 else ("top" if z > x else "bot")


def initial_push(events: dict, rows, waves: int = 2) -> dict:
    """Who has the push in the first waves and where each jungler paths.

    The push is measured by **where the wave dies**: if the minions fall near the red base, blue is pushing.
    One number per lane and wave comes out between -1 (red pushes completely) and +1 (blue pushes), which is 0 at the
    centre of the lane. It doesn't try to decide who has prio —that depends on the matchup—: it stores the datum so
    the model learns it with many matches.

    The jungler's path is the half of their jungle (top or bot) where their first clear ends.

    ponytail: the lane is decided by the map zone and the wave by the moment of appearance. With waves that
    cross a lot (after minute 10) this breaks; for the first two it is more than enough."""
    bases = _bases(rows)

    spawn_times = {e["net_id"]: e["time"] for e in events["events"] if e["type"] == "SpawnLaneMinion"}
    earliest = min(spawn_times.values()) if spawn_times else 0.0
    push: dict[tuple[str, int], list[float]] = collections.defaultdict(list)
    for e in events["events"]:
        if e["type"] != "UnitDeath" or e["net_id"] not in spawn_times:
            continue
        wave = round((spawn_times[e["net_id"]] - earliest) / 30) + 1
        if wave > waves:
            continue
        x, z = e["position"]
        if not (500 < x < 14500 and 500 < z < 14500):  # some deaths arrive with no position, at (0, 0)
            continue
        # where it falls, projected on the axis joining the two bases: 0 at blue, 1 at red
        (ax, az), (rx, rz) = bases["100"], bases["200"]
        length = (rx - ax) ** 2 + (rz - az) ** 2
        advance = ((x - ax) * (rx - ax) + (z - az) * (rz - az)) / length
        push[(_lane(x, z), wave)].append(2 * advance - 1)

    paths = {}
    junglers = {p["team"]: p["champion"] for p in events["players"] if p["position"] == "JUNGLE"}
    for side, team in (("blue", "100"), ("red", "200")):
        clear = first_clear(events, side)
        if not clear:
            continue
        paths[junglers.get(team, side)] = "top" if clear[-1][1] in TOPSIDE[side] else "bot"
    return {"push": {f"{lane}_wave{wave}": round(statistics.median(v), 3) for (lane, wave), v in sorted(push.items())},
            "paths": paths}


def save_prio(game: str, data: dict, events: dict, match: dict, dest: Path) -> None:
    """One row per jungler in a CSV that accumulates: the material to learn what prio each path requires.

    If the match is already stored it isn't written again: running this twice would duplicate its rows and
    with thousands of matches that weighs double in what the model learns."""
    if dest.exists() and any(l.startswith(game + ",") for l in dest.read_text(encoding="utf-8").splitlines()):
        return
    team_of = {p["champion"]: p["team"] for p in events["players"]}
    wins = {str(t["teamId"]): t["win"] for t in match["info"]["teams"]}
    columns = ["game", "jungler", "team", "path", "wins", *data["push"]]
    rows = [{"game": game, "jungler": jungler, "team": team_of[jungler], "path": path,
              "wins": wins.get(team_of[jungler], ""), **data["push"]}
             for jungler, path in data["paths"].items()]
    is_new = not dest.exists()
    with dest.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        if is_new:
            writer.writeheader()
        writer.writerows(rows)


def first_clear(events: dict, side: str) -> list[tuple[float, str]]:
    """The camps of that jungle's first clear, in order. It ends at the first that repeats."""
    own_items = sorted((c["time"], c["camp"]) for c in events["camps"]
                   if c.get("side") == side and c["camp"] in (SMALL + ("Blue", "Red")))
    out: list[tuple[float, str]] = []
    for t0, camp in own_items:
        if camp in [c for _t, c in out]:
            break
        out.append((t0, camp))
    return out


def fullclear(events: dict, reference: Path) -> dict[str, dict]:
    """How long each jungler takes to clear their entire jungle, against the ladder's average.

    The reference (`fullclear.csv`, taken from the Emerald-and-up playerbase) goes per champion and per
    map side, in seconds from the start of the match.

    If they don't clear the six camps, the clear **isn't compared with the average**: a cut clear isn't a
    slow clear. It is marked as **suboptimal, which isn't the same as bad**: leaving camps can be the
    right play (a gank that comes off, an objective, defending an invasion), but the gold and experience
    left there are paid for all the same, and that is already charged by `idle_jungle` as live camps."""
    table = {}
    with reference.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            table[row["champion"].lower()] = (float(row["blueside"]), float(row["redside"]))
    junglers = {p["team"]: p["champion"] for p in events["players"] if p["position"] == "JUNGLE"}
    out = {}
    for side, team in (("blue", "100"), ("red", "200")):
        jungler = junglers.get(team)
        clear = first_clear(events, side) if jungler else []
        if not clear:
            continue
        means = table.get(jungler.lower())
        mean = means[0 if side == "blue" else 1] if means else None
        whole = len(clear) >= 6
        out[jungler] = {"camps": len(clear), "ends": clear[-1][0], "order": [c for _t, c in clear],
                         "whole": whole, "mean": mean,
                         "skipped": [c for c in (*SMALL, "Blue", "Red") if c not in [x for _t, x in clear]],
                         "difference": clear[-1][0] - mean if mean and whole else None}
    return out


SIDES = {"top": "TOP", "bot": "BOTTOM"}  # the half of the map the clear ends toward → the lane that occupies it


def sides(events: dict) -> dict[str, str]:
    """Lane and team → "strong" or "weak", according to where their jungler's first clear ends.

    If the jungler ends bottom, bottom is the strong side and top the weak: those at the bottom play with the
    possibility that they will appear and those at the top, without it. Mid has no side: they reach both.

    ponytail: it is the general rule. The side changes with the matchup, the summoner spells and what
    happens in the first minutes; here the starting datum is stored, not the truth of the whole match."""
    paths = {}
    for side, team in (("blue", "100"), ("red", "200")):
        clear = first_clear(events, side)
        if clear:
            paths[team] = "top" if clear[-1][1] in TOPSIDE[side] else "bot"
    out = {}
    for p in events["players"]:
        path = paths.get(p["team"])
        if path and p["position"] in ("TOP", "BOTTOM", "UTILITY"):
            lane = "top" if p["position"] == "TOP" else "bot"
            out[p["champion"]] = "strong" if lane == path else "weak"
    return out


def resources_in_lane(events: dict, rows, since: float = 120.0, until: float = 600.0) -> list[dict]:
    """How each one spends their resources in lane, with their side (strong or weak) alongside.

    On the strong side poking is worthwhile: the enemy has to respect that the jungler may appear. On the weak side
    the opposite is worthwhile, arriving with resources —health, mana, summoner spells— because nobody is coming.
    The trade's result isn't judged here, the resources are counted: damage dealt and taken against their direct
    opponent, mean health and mana, and the summoner spells they burn."""
    position = {p["champion"]: p["position"] for p in events["players"]}
    team = {p["champion"]: p["team"] for p in events["players"]}
    net = {p["net_id"]: p["champion"] for p in events["players"]}
    side = sides(events)
    rival = {a: b for a in position for b in position
             if a != b and position[a] == position[b] and team[a] != team[b]}
    dealt: dict[tuple[str, str], float] = collections.defaultdict(float)
    spells: dict[str, list[float]] = collections.defaultdict(list)
    for e in events["events"]:
        if not since <= e["time"] <= until:
            continue
        if e["type"] == "Damage" and e["net_id"] in net and e.get("source") in net:
            dealt[(net[e["source"]], net[e["net_id"]])] += e["amount"]
        elif (e["type"] == "CastSpell" and e["net_id"] in net and e["slot"] in (4, 5)
              and e["spell"].lower().startswith("summoner")):  # those gaps also carry unnamed actives
            spells[net[e["net_id"]]].append(e["time"])
    out = []
    for champion, own in position.items():
        if own == "JUNGLE" or champion not in rival:
            continue
        stretch = _window(rows, champion, since, until)
        healths = [(_num(f, "health") or 0) / (_num(f, "health_max") or 1) for f in stretch if _num(f, "health_max")]
        manas = [(_num(f, "mana") or 0) / (_num(f, "mana_max") or 1) for f in stretch if _num(f, "mana_max")]
        out.append({"champion": champion, "lane": own, "team": team[champion],
                      "side": side.get(champion, "—"), "rival": rival[champion],
                      "damage_done": dealt[(champion, rival[champion])],
                      "damage_received": dealt[(rival[champion], champion)],
                      "health_mean": statistics.mean(healths) if healths else None,
                      "health_minimum": min(healths) if healths else None,
                      "mana_mean": statistics.mean(manas) if manas else None,
                      "summoners": spells.get(champion, [])})
    return out


def jungler_recalls(events: dict, rows, threshold: float = 1500.0, period: float = 138.0,
                       free_window: float = 30.0) -> dict[str, dict]:
    """When the jungler should have gone back to base and how long they take to spend the gold.

    Their recalls aren't marked by the waves but by gold and camps: with more than `threshold` on them they have to
    go back, and the good moment is when there is nothing to do on the map and they have no live camps, because they
    can reopen wherever they like and already bought. It measures:

    - how much gold they end up carrying and how many seconds they spend above the threshold away from base;
    - how long they take to buy from crossing the threshold;
    - the free windows (without their own live camps and without any champion death nearby) that
      they waste by carrying the gold around.

    ponytail: the threshold is fixed. The proper thing would be the price of the item they're due, which Data Dragon asks for."""
    junglers = {p["team"]: p["champion"] for p in events["players"] if p["position"] == "JUNGLE"}
    net_of = {p["champion"]: p["net_id"] for p in events["players"]}
    deaths = sorted(e["time"] for e in events["events"] if e["type"] == "Death")
    out = {}
    for side, team in (("blue", "100"), ("red", "200")):
        jungler = junglers.get(team)
        if not jungler:
            continue
        purchases = sorted(e["time"] for e in events["events"]
                         if e["type"] == "BuyItem" and e["net_id"] == net_of[jungler] and e["time"] > 60)
        own_items = sorted((c["time"], c["camp"]) for c in events["camps"]
                       if c.get("side") == side and c["camp"] in SMALL)
        def has_camp(t: float) -> bool:
            """Whether any of their small camps is alive: there is farming to do before going back."""
            for camp in SMALL:
                previous = [t0 for t0, c in own_items if c == camp and t0 < t]
                if previous and previous[-1] + period <= t:
                    return True
            return False
        base = None
        above, crossings, free, max_gold, when_max = [], [], [], 0.0, 0.0
        for row in rows[jungler]:
            t, gold = float(row["time"]), _num(row, "gold") or 0
            if base is None and row["x"] and t <= 5:
                base = (float(row["x"]), float(row["z"]))
            if gold > max_gold:
                max_gold, when_max = gold, t
            at_base = base and row["x"] and math.dist((float(row["x"]), float(row["z"])), base) < 2000
            if gold < threshold or row["alive"] != "True" or at_base:
                continue
            above.append(t)
            if not any(abs(t - m) < 20 for m in deaths) and not has_camp(t):
                free.append(t)
        for t in above:  # the first second of each stretch above the threshold
            if not crossings or t - crossings[-1][0] > 30:
                next_ = next((c for c in purchases if c > t), None)
                crossings.append((t, next_ - t if next_ else None))
        spans = []
        for t in free:
            if spans and t - spans[-1][1] <= 2:
                spans[-1][1] = t
            else:
                spans.append([t, t])
        out[jungler] = {"team": team, "max_gold": round(max_gold), "when_max": when_max,
                         "seconds_above": len(above),
                         "crossings": crossings[:4],
                         "free_windows": [(a, b) for a, b in spans if b - a >= free_window]}
    return out


def _bases(rows) -> dict[str, tuple[float, float]]:
    """Where each team's base is: the median of their champions in the first seconds of the match."""
    out = {}
    for team in ("100", "200"):
        own_items = [f for theirs in rows.values() for f in theirs[:8]
                 if f["team"] == team and f["x"] and float(f["time"]) <= 5]
        out[team] = (statistics.median(float(f["x"]) for f in own_items),
                         statistics.median(float(f["z"]) for f in own_items))
    return out


CELL = 250  # side of the cell with which each lane's corridor is drawn


def lane_waves(events: dict, gap: float = 10.0) -> dict:
    """Where each wave is and with how many minions, throughout the match.

    It comes from two replay packets: `SpawnLaneMinion` (which barracks each minion comes out of) and its `UnitDeath`
    (when and where it dies). The barracks doesn't say its lane, but the position where its minions appear does:
    there are six, three per side, and of the three on one side the bot one is the one lowest below the diagonal
    and the top one the one highest above it.

    The wave's place is measured by **where the minions fall**, projected on the axis joining the two
    barracks of the lane: 0 is the blue barracks, 1 the red one, 0.5 the centre. The sum x+z also serves as an axis in
    top and in bot, which are an L, because the elbow falls exactly halfway along the route.

    The wave number is obtained by grouping each barracks' departures, not by dividing the clock by 30: the
    interval between waves **drops during the match**, from 30 s to 25 and then to 20, and counting by clock the
    numbering drifted by more than twelve waves at minute 35.

    On the way the **corridor** of each lane (`corridors`) comes out, which isn't drawn by hand: they are the cells
    the minions really walk through, taken from their waypoints. That is what separates the lane from the
    jungle beside it, which no distance separates: Gromp and Krugs are a step from top and bot, but
    with a wall in between through which no minion passes.

    It returns a record per minion (`minions`: when it is born, when and where it dies, who kills it and who
    collects its gold), the grouped waves (`waves`, with `cannon`), each lane's corridor and the lists that
    `_advance` and `_alive` consult.

    ponytail: the cannon is detected by the wave's size (6 minions, 7 with a cannon). With a fallen
    inhibitor the super minions come in and the count stops being valid; the rules here stay in the first
    minutes, which is where wave control decides anything."""
    spawned_at = {e["net_id"]: (e["time"], e["barracks"]) for e in events["events"] if e["type"] == "SpawnLaneMinion"}
    first: dict[str, list[float]] = {}
    cells = collections.defaultdict(set)
    for e in events["events"]:
        if e["type"].startswith("WaypointGroup"):
            for u in e["units"]:
                if (own := spawned_at.get(u["net_id"])) is None:
                    continue
                first.setdefault(u["net_id"], u["path"][0])
                cells[own[1]].update((int(x // CELL), int(z // CELL)) for x, z in u["path"])
    spot = {}
    for barracks in {b for _t, b in spawned_at.values()}:
        points = [first[n] for n, (_t, b) in spawned_at.items() if b == barracks and n in first]
        spot[barracks] = (statistics.median(p[0] for p in points), statistics.median(p[1] for p in points))
    all_barracks, axis = {}, collections.defaultdict(dict)
    for side in ("blue", "red"):
        own_rows = [b for b, (x, z) in spot.items() if (x + z < 14800) == (side == "blue")]
        for lane, barracks in zip(("bot", "mid", "top"), sorted(own_rows, key=lambda b: spot[b][1] - spot[b][0])):
            all_barracks[barracks] = (side, lane)
            axis[lane][side] = sum(spot[barracks])

    died = {e["net_id"]: (e["time"], e["position"], e["killer"]) for e in events["events"]
             if e["type"] == "UnitDeath" and e["net_id"] in spawned_at}
    farm = {c["unit"]: c["net_id"] for c in events["creeps"] if c["character"] == "LaneMinion"}
    start = min(t for t, _b in spawned_at.values())
    # waves don't come out every 30 s all match: the interval drops to 25 and then to 20, so the
    # wave number is taken by grouping the real departures —within one they are a second apart
    # and between two there are twenty— and not by dividing the clock by 30
    per_barracks = collections.defaultdict(list)
    for net_id, (t0, barracks) in spawned_at.items():
        per_barracks[barracks].append((t0, net_id))
    number_of, prior = {}, None
    for own_rows in per_barracks.values():
        n, prior = 0, None
        for t0, net_id in sorted(own_rows):
            n += prior is None or t0 - prior > gap
            number_of[net_id] = n
            prior = t0
    minions, waves = {}, {}
    falls = collections.defaultdict(list)
    healths = collections.defaultdict(list)
    for net_id, (t0, barracks) in spawned_at.items():
        side, lane = all_barracks[barracks]
        t1, where, killed_by = died.get(net_id, (float("inf"), None, None))
        advance = None
        if where and 500 < where[0] < 14500 and 500 < where[1] < 14500:  # some deaths arrive at (0, 0)
            advance = (where[0] + where[1] - axis[lane]["blue"]) / (axis[lane]["red"] - axis[lane]["blue"])
            falls[lane].append((t1, advance, where[0], where[1]))
        healths[(lane, side)].append((t0, t1))
        number = number_of[net_id]
        minions[net_id] = {"side": side, "lane": lane, "wave": number, "spawned_at": t0, "died": t1,
                            "advance": advance, "where": where if advance is not None else None,
                            "farm": farm.get(net_id), "killed_by": killed_by}
        wave = waves.setdefault((lane, side, number), {"spawned_at": t0, "minions": []})
        wave["spawned_at"] = min(wave["spawned_at"], t0)
        wave["minions"].append(net_id)
    for items in list(falls.values()) + list(healths.values()):
        items.sort()
    for wave in waves.values():
        wave["cannon"] = len(wave["minions"]) >= 7
    corridors = collections.defaultdict(set)
    for barracks, own_rows in cells.items():
        for cell in own_rows:
            corridors[cell].add(all_barracks[barracks][1])
    return {"barracks": all_barracks, "axis": dict(axis), "falls": dict(falls), "healths": dict(healths),
            "minions": minions, "waves": waves, "output": start, "corridors": dict(corridors)}


def _advance(state: dict, lane: str, t: float, window: float = 20.0) -> tuple[float, float, float] | None:
    """Where the lane's wave is: the median of where the minions fell around that moment.

    Returns (advance, x, z): the advance for comparing places and the position for seeing who is holding it."""
    near = [c for c in state["falls"].get(lane, []) if t - window <= c[0] <= t + window]
    if len(near) < 3:
        return None
    return tuple(statistics.median(c[i] for c in near) for i in (1, 2, 3))


def _alive(state: dict, lane: str, side: str, t: float) -> int:
    """Live minions of that side in that lane at that moment."""
    return sum(1 for t0, t1 in state["healths"].get((lane, side), []) if t0 <= t < t1)


def _cs_lost(state: dict, lane: str, team: str, since: float, until: float,
                owner_of: dict[str, str]) -> tuple[int, int]:
    """Minions that `team` had to eat in that lane and that stretch: how many fall and how many escape them.

    Those one eats are the opposing team's, so the other side's minions are looked at; one escapes
    if it dies without anyone on your team collecting its gold (the turret, the enemy jungle, the enemy itself)."""
    rival = "red" if team == "100" else "blue"
    fall = lost = 0
    for s in state["minions"].values():
        if s["lane"] != lane or s["side"] != rival or not since <= s["died"] <= until:
            continue
        fall += 1
        if owner_of.get(s["farm"]) != team:
            lost += 1
    return fall, lost


# The outer turret of each lane and side, in advance: the median of `_towers` across 126 matches of 16.19, which
# varies ±0.01 from one match to another
TYPICAL_TOWERS = {("top", "blue"): 0.369, ("top", "red"): 0.622, ("mid", "blue"): 0.376,
                  ("mid", "red"): 0.589, ("bot", "blue"): 0.373, ("bot", "red"): 0.642}


def _towers(events: dict, state: dict, minimum: int = 5) -> dict[tuple[str, str], float]:
    """Where the outer turret of each lane and side is, in advance.

    Turrets don't move and don't send their position, but they kill minions: the median of where the ones a turret
    finishes fall is a shot's distance from it. Of a side's turrets, the most advanced is kept, which is the
    outer; it holds even if it has fallen, because its kills were recorded earlier.

    If a turret finishes fewer than `minimum` minions (short match, a lane that never reaches it), it stays
    in its usual place (`TYPICAL_TOWERS`): turrets don't move, and without this `stacks` threw out 7% of
    the matches."""
    towers = {e["net_id"] for e in events["events"]
              if e["type"] == "SetSpell" and "Turret" in (e.get("name") or "")}
    fall = collections.defaultdict(list)
    for e in events["events"]:
        s = state["minions"].get(e["net_id"]) if e["type"] == "UnitDeath" else None
        if s and s["advance"] is not None and e["killer"] in towers:
            fall[(s["lane"], e["killer"])].append(s["advance"])
    spots = {k: statistics.median(v) for k, v in fall.items() if len(v) >= minimum}
    out = dict(TYPICAL_TOWERS)
    for lane in ("top", "mid", "bot"):
        own_rows = [a for (c, _t), a in spots.items() if c == lane]
        if [a for a in own_rows if a < 0.5]:
            out[(lane, "blue")] = max(a for a in own_rows if a < 0.5)
        if [a for a in own_rows if a > 0.5]:
            out[(lane, "red")] = min(a for a in own_rows if a > 0.5)
    return out


def freezes(events: dict, state: dict, rows, since: float = 120.0, until: float = 840.0,
                  minimum: float = 30.0, still: float = 0.07, advantage: int = 2,
                  near: float = 2000.0, step: float = 5.0) -> list[dict]:
    """Frozen waves: the wave stopped between your turret and the middle, held with fewer minions than the enemy.

    Freezing is leaving the wave still in front of your turret with **fewer of your minions than the enemy's** —the
    classic count is three—: that way the one who has to come forward to farm is them, far from their turret and
    within your range. If the formation breaks the wave goes by itself toward your turret and that's that.

    It is marked when four things hold at once, looking every `step` seconds:

    - the wave is **between your outer turret and the middle of the lane** (the turret comes from `_towers`, measured
      from the data itself, so there is no hand-set number);
    - you have at least `advantage` fewer minions than the enemy, which is what keeps it still;
    - the wave doesn't move: less than `still` of advance over the whole window;
    - someone on your team is holding it, within `near` of it.

    Whether freezing was right or wrong isn't judged: it says who holds it, how long it lasts and how many minions
    escape the opponent meanwhile."""
    team_of = {"blue": "100", "red": "200"}
    owner_of = {p["net_id"]: p["team"] for p in events["players"]}
    towers = _towers(events, state)
    own_items = collections.defaultdict(list)
    for p in events["players"]:
        if p["position"] in LANES:
            own_items[(LANES[p["position"]], "blue" if p["team"] == "100" else "red")].append(p["champion"])

    def holds(lane: str, side: str, t: float, where: tuple[float, float]) -> str | None:
        """Who of that lane is against the wave at that moment."""
        for champion in own_items[(lane, side)]:
            for f in _window(rows, champion, t - 2, t + 2):
                if f["alive"] == "True" and f["x"] and math.dist((float(f["x"]), float(f["z"])), where) < near:
                    return champion
        return None

    out = []
    for lane in ("top", "mid", "bot"):
        open_, t = None, since
        while t <= until:
            spot = _advance(state, lane, t)
            who = owner = advance = blues = reds = None
            if spot:
                advance, x, z = spot
                blues, reds = _alive(state, lane, "blue", t), _alive(state, lane, "red", t)
                for side, inside, missing in (("blue", towers.get((lane, "blue"), 1) < advance < 0.5, reds - blues),
                                            ("red", 0.5 < advance < towers.get((lane, "red"), 0), blues - reds)):
                    if inside and missing >= advantage and (owner := holds(lane, side, t, (x, z))):
                        who = side
                        break
            continues = (who and open_ and open_["side"] == who
                     and max(open_["advances"] + [advance]) - min(open_["advances"] + [advance]) <= still)
            if continues:
                open_ |= {"until": t}
                open_["advances"].append(advance)
                open_["differences"].append(abs(blues - reds))
                open_["who"].add(owner)
            else:
                if open_ and open_["until"] - open_["since"] >= minimum:
                    out.append(open_)
                open_ = ({"lane": lane, "side": who, "since": t, "until": t, "who": {owner},
                            "advances": [advance], "differences": [abs(blues - reds)]} if who else None)
            t += step
        if open_ and open_["until"] - open_["since"] >= minimum:
            out.append(open_)
    for c in out:
        victim = "200" if c["side"] == "blue" else "100"
        fall, lost = _cs_lost(state, c["lane"], victim, c["since"], c["until"], owner_of)
        c |= {"team": team_of[c["side"]], "advance": statistics.median(c["advances"]),
              "difference": statistics.median(c["differences"]), "rival_cs": fall,
              "rival_cs_lost": lost, "who": sorted(c["who"])}
    return sorted(out, key=lambda c: c["since"])


LANES = {"TOP": "top", "MIDDLE": "mid", "BOTTOM": "bot", "UTILITY": "bot"}


def _last_cleared(state: dict, lane: str, side: str, t: float, share: float = 0.8) -> int:
    """The last wave of that side that is already cleared (`share` of its minions dead) at that moment.

    It is what separates "going back after clearing" from "going back leaving the wave": the video counts the back
    from the cleared wave, not from the one that has come out of the barracks."""
    return max((n for (c, l, n), o in state["waves"].items() if c == lane and l == side
                and sum(state["minions"][s]["died"] <= t for s in o["minions"]) >= share * len(o["minions"])),
               default=0)


CRASH_RETURN = 40.0  # seconds since their wave crashed into the enemy turret: the time during which the back comes free
NEUTRAL = 0.12  # within this of the lane's centre, the wave is in no-man's land
LOW_MANA = 0.20  # with less than this share of mana, or of health (`LOW_HEALTH`), going back to base is worth more than the wave left behind
LOW_HEALTH = 0.35
PUSH = 2  # extra minions over the enemy for a wave in the middle to go by itself to their turret
AT_THEIR_TOWER = 0.06  # within this of their turret, the wave is dying against it


def wave_on_return(state: dict, lane: str, team: str, t: float, clashes: list[dict], cold: list[dict],
                  towers: dict[tuple[str, str], float]) -> tuple[str, str]:
    """How the wave is when they press recall and whether that is a good moment to leave: (state, verdict).

    A recall isn't judged by the minions lost afterwards —that already counts how long they take to return— but by
    **where the wave is on leaving**, which is what decides whether anything is lost:

    - `crash`, their wave has just crashed into the enemy turret (`stacks`, up to CRASH_RETURN s): **good**,
      the turret eats it and the next one takes a while to arrive;
    - `frozen`, there is a live freeze in the lane (`freezes`): **bad**, leaving breaks it or leaves the enemy
      freezing at their leisure;
    - `neutral with cannon`: **good**. The cannon withstands the hits and slows the wave, so it is still there;
    - `neutral without cannon`: **bad**, it goes by itself toward one of the two turrets and is lost whole;
    - `pushed in their favour`, in the middle but with `PUSH` more minions than the enemy: **good**. It goes by itself toward the
      enemy turret and crashes there; in the 16.19 harvest 3.3 minions are lost on average after going back,
      against 6.4 with the enemy's wave bigger;
    - `picked up under their tower` of a wave **without a cannon**: **good**; **with a cannon**: **bad**, because the cannon's
      rebound is theirs and they have to be there to receive it;
    - any of the **bad** ones becomes `no resources`, **good**, if on pressing they have little mana or little health
      left (`_without_resources`): decided by the author of the reference review (see `research/coaching`);
    - the rest (pushed without reaching the turret, an enemy slow push on top) isn't judged: `""`.

    The cannon that matters is that of the **enemy's** wave, which is the one they farm."""
    own_side = "blue" if team == "100" else "red"
    rival = "red" if own_side == "blue" else "blue"
    spot = _advance(state, lane, t)
    if spot is None:
        return "", ""
    advance = spot[0] if team == "100" else 1 - spot[0]  # 0 their turret, 1 the enemy's
    if any(c["lane"] == lane and c["side"] == own_side and 0 <= t - c["ends"] <= CRASH_RETURN for c in clashes):
        return "crash", "good"
    if any(c["lane"] == lane and c["since"] <= t <= c["until"] for c in cold):
        return "frozen", "bad"

    def cannon(number: int) -> bool:
        wave = state["waves"].get((lane, rival, number))
        return bool(wave and wave["cannon"])

    pickup = _last_cleared(state, lane, rival, t)
    own_entry = towers.get((lane, own_side))
    own_advance = (own_entry if team == "100" else 1 - own_entry) if own_entry is not None else 0.25
    if advance <= own_advance + AT_THEIR_TOWER:
        return ("picked up under their tower with cannon", "bad") if cannon(pickup) else ("picked up under their tower", "good")
    if abs(advance - 0.5) <= NEUTRAL:
        if cannon(pickup + 1):
            return "neutral with cannon", "good"
        if _alive(state, lane, own_side, t) - _alive(state, lane, rival, t) >= PUSH:
            return "pushed in their favour", "good"
        return "neutral without cannon", "bad"
    return "", ""


def _without_resources(rows, champion: str, t: float) -> bool:
    """They have very little mana or very little health on pressing recall: without them they can neither farm nor defend, and
    refilling them in base is worth more than the wave left behind."""
    last = _window(rows, champion, t - 3, t)
    if not last:
        return False
    f = last[-1]
    max_health, mana_max = float(f["health_max"] or 0), float(f["mana_max"] or 0)  # at the start the mana may come empty: each is looked at separately
    return bool((max_health and float(f["health"]) <= LOW_HEALTH * max_health) or (mana_max and float(f["mana"] or 0) <= LOW_MANA * mana_max))


def backs(events: dict, rows, state: dict, until: float = 840.0, horizon: float = 60.0,
          clashes: list[dict] | None = None, cold: list[dict] | None = None) -> list[dict]:
    """The backs of each lane, with the wave that was coming at them and what it cost them in minions.

    The good back in the video is the one **right after clearing the wave before the cannon one**: the one that
    comes down the lane is the cannon one, the hardest to push, and even if the enemy pushes it whole the
    cannon withstands many turret hits and gives time to arrive. The other good back is the one after the cannon,
    which accumulates cannon + next. The rest come out expensive.

    The reference wave is the **last one they left cleared** (`_last_cleared`), not the one that has just come out
    of the barracks: going back with the wave half-cleared is neither of the two good cases.

    The `recall` buff that **completes** (the champion ends up in their base) and the minions that
    escape them in their lane in the following minute are counted.

    The verdict (`verdict`, with `wave` saying why) comes from where the wave is on pressing it, not from what
    is lost afterwards: see `wave_on_return`."""
    owner_of = {p["net_id"]: p["team"] for p in events["players"]}
    clashes = stacks(events, state, rows, until=until + 60) if clashes is None else clashes
    cold = freezes(events, state, rows, until=until) if cold is None else cold
    towers = _towers(events, state)
    net_of = {p["net_id"]: p for p in events["players"]}
    bases, out = _bases(rows), []
    for e in events["events"]:
        if e["type"] != "AddBuff" or e["buff"].lower() != "recall" or e["time"] > until:
            continue
        player = net_of.get(e["net_id"])
        if not player or player["position"] not in LANES:
            continue
        champion, lane, team = player["champion"], LANES[player["position"]], player["team"]
        lane = _real_lane(rows, champion, e["time"]) or lane
        if not any(f["x"] and math.dist((float(f["x"]), float(f["z"])), bases[team]) < 2000
                   for f in _window(rows, champion, e["time"], e["time"] + 15)):
            continue  # cancelled recall: doesn't count as a back
        if any(b["champion"] == champion and e["time"] - b["time"] < 20 for b in out[-5:]):
            continue  # the buff refreshes on starting again: a single back
        cleared = _last_cleared(state, lane, "red" if team == "100" else "blue", e["time"])
        next_ = state["waves"].get((lane, "red" if team == "100" else "blue", cleared + 1))
        kind = ("without clearing the wave" if not cleared else
                "cannon on the way" if next_ and next_["cannon"] else
                "cannon + next" if state["waves"][(lane, "red" if team == "100" else "blue",
                                                       cleared)]["cannon"] else "normal wave")
        fall, lost = _cs_lost(state, lane, team, e["time"], e["time"] + horizon, owner_of)
        where, verdict = wave_on_return(state, lane, team, e["time"], clashes, cold, towers)
        if _without_resources(rows, champion, e["time"]):  # whatever the wave, that is the reason to go back
            where, verdict = "no resources", "good"
        out.append({"champion": champion, "team": team, "lane": lane, "time": e["time"],
                      "wave_number": cleared, "kind": kind, "cs_in_play": fall, "cs_lost": lost,
                      "wave": where, "verdict": verdict})
    return out


def recalls(events: dict, rows, channel: float = 8.0) -> list[dict]:
    """Each recall started in the whole match (slot 13, the go-back-to-base one, with any name), and whether it was
    **cancelled**: the first time the champion changes place not in their base, or starts the recall again
    before the `channel` seconds it lasts (4 for the empowered one). The first change is looked at and not where they are at 8 s
    because the table only moves the champion when they walk: after the recall they stay in the place they left until
    they take the first step in the base, which after shopping can be 10 s or more. Those cut by a death don't count,
    nor those of someone who doesn't move in a minute (unknown).

    `cut_short` is the cancelled one that an enemy cuts: damage or a crowd control from an enemy champion reaches them between its
    start and their moving (with the table's second of margin). But punishing a recall doesn't require hitting: approaching is enough.
    `rival_near` is the closest a living enemy champion gets while they channel (until they
    move), seen or not, to measure the recall done too close."""
    net_of = {p["net_id"]: p for p in events["players"]}
    bases = _bases(rows)
    deaths = collections.defaultdict(list)
    for e in events["events"]:
        if e["type"] == "Death":
            deaths[e["net_id"]].append(e["time"])
    casts, hits = collections.defaultdict(list), collections.defaultdict(list)
    for e in events["events"]:
        if e["type"] == "CastSpell" and e["slot"] == 13 and e["net_id"] in net_of:
            casts[e["net_id"]].append(e["time"])
        elif e["type"] == "Damage" and e["net_id"] in net_of and e.get("source") in net_of:
            hits[e["net_id"]].append((e["time"], e["source"]))
    for c in events["controls"]:
        if c["net_id"] in net_of and c["caster"] in net_of:
            hits[c["net_id"]].append((c["time"], c["caster"]))
    table = {p["champion"]: {int(float(f["time"])): f for f in rows.get(p["champion"], [])} for p in events["players"]}
    out = []
    for who, when in casts.items():
        p = net_of[who]
        rivals = [r["champion"] for r in events["players"] if r["team"] != p["team"]]
        for t, next_ in zip(when, [*when[1:], math.inf], strict=True):
            if any(t <= m <= t + channel for m in deaths[who]):
                continue
            spots = [(float(f["time"]), (float(f["x"]), float(f["z"])))
                      for f in _window(rows, p["champion"], t, t + 60) if f["x"]]
            then = next(((tt, s) for tt, s in spots if math.dist(s, spots[0][1]) > 100), None)
            if then is None:
                continue
            cancelled = next_ < t + channel or math.dist(then[1], bases[p["team"]]) >= 2000
            until = min(next_, then[0] + 1, t + channel)
            cut_short = cancelled and any(t <= tg <= until and net_of[source]["team"] != p["team"] for tg, source in hits[who])
            near = min((math.dist(spots[0][1], (float(f["x"]), float(f["z"])))
                         for second in range(int(t), int(until) + 1) for r in rivals
                         if (f := table[r].get(second)) and f["x"] and f["alive"] == "True"), default=None)
            out.append({"champion": p["champion"], "position": p["position"], "team": p["team"],
                          "time": round(t, 1), "cancelled": int(cancelled), "cut_short": int(cut_short),
                          "rival_near": round(near) if near is not None else ""})
    return sorted(out, key=lambda x: x["time"])


def _rafagas(pairs: list[tuple[float, int]], gap: float) -> list[list[tuple[float, int]]]:
    """The (second, datum) pairs split into runs: cut when more than `gap` seconds pass with nothing."""
    out: list[list[tuple[float, int]]] = []
    for pair in sorted(pairs):
        if out and pair[0] - out[-1][-1][0] <= gap:
            out[-1].append(pair)
        else:
            out.append([pair])
    return out


def _real_lane(rows, champion: str, t: float, back: float = 25.0) -> str | None:
    """The lane they are really in: the one they step on most in the previous `back` seconds. It need not be their
    position's (lane swaps, or a teammate covering another's wave): the wave belongs to whoever is in it."""
    zones = collections.Counter(_lane(float(f["x"]), float(f["z"])) for f in _window(rows, champion, t - back, t)
                                if f["alive"] == "True" and f["x"])
    return zones.most_common(1)[0][0] if zones else None


def _in_lane(rows, champion: str, lane: str, t: float) -> bool:
    """The champion is alive and in their lane at that moment."""
    return any(f["alive"] == "True" and f["x"] and _lane(float(f["x"]), float(f["z"])) == lane
               for f in _window(rows, champion, t - 3, t + 3))


def stacks(events: dict, state: dict, rows, until: float = 900.0, minimum: int = 3, gap: float = 12.0,
           window: float = 30.0, horizon: float = 60.0, max_bounce: float = 120.0,
           go_back: int = 3) -> list[dict]:
    """Wave accumulations: the crash against the turret and the rebound that comes behind.

    Everything else is played around an accumulated wave. A **slow push** joins two or three waves and crashes
    them all together into the enemy turret: while the turret eats them there is a free window to
    go back to base, steal a camp or rotate. The **rebound** is what happens afterwards: on the other side more
    minions remain and the wave comes toward you, so either you are there to receive it or you lose it whole.

    The crash is detected with no invented threshold: the minions that the **enemy turret finishes**, grouped in
    runs. That it is a stack and not a loose wave is told by the **distinct waves** that put at least two
    minions in the run, which come already marked on each minion: with only one it is the usual wave. The
    rebound is the moment when the wave goes back past the centre toward whoever pushed —halfway to
    their own turret— with the enemy `go_back` minions ahead, which are the three of the usual count.

    From each crash comes what the pusher did with the window, whether they returned in time for the rebound and what
    it cost them in minions.

    Slow pushes that don't reach the turret don't come out here, because there is no crash: those are seen by
    `accumulations`, which follows them by the difference in minions."""
    turrets = {e["net_id"] for e in events["events"]
                if e["type"] == "SetSpell" and "Turret" in (e.get("name") or "")}
    towers = _towers(events, state)
    fallen = collections.defaultdict(list)
    recalls = collections.defaultdict(list)
    for e in events["events"]:
        if e["type"] == "AddBuff" and e["buff"].lower() == "recall":
            recalls[e["net_id"]].append(e["time"])
        s = state["minions"].get(e["net_id"]) if e["type"] == "UnitDeath" else None
        if s and e["killer"] in turrets and s["died"] <= until:
            fallen[(s["lane"], s["side"])].append((s["died"], s["wave"]))

    owner_of = {p["net_id"]: p["team"] for p in events["players"]}
    net_of = {p["champion"]: p["net_id"] for p in events["players"]}
    own_items = collections.defaultdict(list)
    for p in events["players"]:
        if p["position"] in LANES:
            own_items[(LANES[p["position"]], "blue" if p["team"] == "100" else "red")].append(p["champion"])

    def what_it_does(champion: str, lane: str, since: float, until_: float) -> str:
        """What they do with the seconds the crash has bought them."""
        net = net_of[champion]
        if any(since <= t <= until_ for t in recalls[net]):
            return "goes back to base"
        if any(c["killer"] == net and since <= c["time"] <= until_ for c in events["camps"]):
            return "camp"
        stretch = [f for f in _window(rows, champion, since, until_) if f["x"] and f["alive"] == "True"]
        if not stretch:
            return "dead"
        return ("leaves the lane" if sum(_lane(float(f["x"]), float(f["z"])) != lane
                                          for f in stretch) > len(stretch) / 2 else "stays")

    out = []
    for (lane, side), pairs in fallen.items():
        rival, team = ("red", "100") if side == "blue" else ("blue", "200")
        for streak in _rafagas(pairs, gap):
            if len(streak) < minimum:
                continue
            t0, t1 = streak[0][0], streak[-1][0]
            counts = collections.Counter(o for _t, o in streak)
            thick = {o for o, n in counts.items() if n >= 2}  # a wave that puts in only one minion doesn't make a stack
            bounce, turnaround = None, (0.5 + towers[(lane, side)]) / 2  # halfway between the centre and their turret
            for t in (t1 + 10 * k for k in range(1, int(max_bounce / 10) + 1)):
                spot = _advance(state, lane, t)
                ahead = _alive(state, lane, rival, t) - _alive(state, lane, side, t)
                if spot and ahead >= go_back and (spot[0] < turnaround if side == "blue" else spot[0] > turnaround):
                    bounce = t
                    break
            _fall, lost = _cs_lost(state, lane, team, t1, t1 + horizon, owner_of)
            out.append({"lane": lane, "side": side, "team": team, "time": t0, "ends": t1,
                          "minions": len(streak), "waves": sorted(thick),
                          "stack": len(thick) >= 2,
                          "bounce": bounce, "cs_lost": lost,
                          "do": {c: what_it_does(c, lane, t1, t1 + window) for c in own_items[(lane, side)]},
                          "arrive": {c: _in_lane(rows, c, lane, bounce) for c in own_items[(lane, side)]}
                          if bounce else {}})
    return sorted(out, key=lambda c: c["time"])


def accumulations(events: dict, state: dict, rows, since: float = 120.0, until: float = 840.0,
                  advantage: int = 3, peak: int = 5, lasts: float = 40.0, step: float = 10.0,
                  tail: float = 30.0, share: float = 0.4, clashes: list[dict] | None = None,
                  cold: list[dict] | None = None) -> list[dict]:
    """Who is building a stack and **how it ends**, which is what says whether it did any good.

    A slow push is seen before reaching any turret: one side is `advantage` minions ahead for
    `lasts` seconds and the difference reaches `peak`. From there there are four endings, and all four are
    marked separately because two can happen at once:

    - it **crashes** into the enemy turret: the stack fulfils its function and opens the window (see `stacks`);
    - **the enemy freezes it**: holds it in front of their turret instead of clearing it, and then the stack is no longer
      yours, it is their freeze (see `freezes`);
    - **the enemy eats it**: their laner clears it themselves, normally under their turret. The slow push
      went nowhere and on top of that you gave them the gold;
    - it **dissolves**: neither of the two, it is spent against the minions.

    It is looked at who finishes the accumulator's minions, which already comes in `minions["killed_by"]`: if an enemy
    champion takes `share` of them, they ate it."""
    champion_by_net = {p["net_id"]: p["champion"] for p in events["players"]}
    side_of = {p["net_id"]: ("blue" if p["team"] == "100" else "red") for p in events["players"]}
    # `clashes` and `cold`, if the caller already has them (crashes after `until + tail` match nothing)
    clashes = stacks(events, state, rows, until=until + tail) if clashes is None else clashes
    cold = freezes(events, state, rows, since=since, until=until) if cold is None else cold

    out = []
    for lane in ("top", "mid", "bot"):
        for side in ("blue", "red"):
            rival = "red" if side == "blue" else "blue"
            open_ = None
            for t in [since + step * k for k in range(int((until - since) / step) + 1)] + [None]:
                diff = None if t is None else _alive(state, lane, side, t) - _alive(state, lane, rival, t)
                if diff is not None and diff >= advantage:
                    open_ = open_ or {"since": t, "peaks": []}
                    open_["peaks"].append(diff)
                    open_["until"] = t
                    continue
                if not open_ or open_["until"] - open_["since"] < lasts or max(open_["peaks"]) < peak:
                    open_ = None
                    continue
                t0, t1 = open_["since"], open_["until"]
                own_items = [s for s in state["minions"].values() if s["lane"] == lane and s["side"] == side
                         and t0 <= s["died"] <= t1 + tail]
                finishers = collections.Counter(champion_by_net[s["killed_by"]] for s in own_items
                                              if side_of.get(s["killed_by"]) == rival)
                come = finishers.most_common(1)
                clash = next((c["time"] for c in clashes if c["lane"] == lane and c["side"] == side
                              and t0 - step <= c["time"] <= t1 + tail), None)
                cold_one = next((c for c in cold if c["lane"] == lane and c["side"] == rival
                             and c["since"] <= t1 and c["until"] >= t0), None)
                out.append({"lane": lane, "side": side, "since": t0, "until": t1,
                              "peak": max(open_["peaks"]), "minions": len(own_items), "clash": clash,
                              "freezes": (sorted(cold_one["who"]), cold_one["since"]) if cold_one else None,
                              "come": come[0] if come and come[0][1] >= share * len(own_items) else None})
                open_ = None
    return sorted(out, key=lambda a: a["since"])


WARDS = {"TrinketTotemLvl1", "JammerDevice", "TrinketOrbLvl3", "ItemGhostWard"}  # the items that place a ward
RIVER = 14800.0  # the diagonal that splits the map into two halves


def _depth(x: float, z: float, side: str) -> float:
    """How far a point goes into the enemy's side: 0 is the river, 1 their fountain, negative is your own half."""
    return ((x + z - RIVER) if side == "blue" else (RIVER - x - z)) / RIVER


def _corridor(state: dict, x: float, z: float) -> str | None:
    """Which lane a point falls in, or None if it is jungle or river.

    The corridor is the cells the minions walk through (see `lane_waves`), so a point behind
    a wall isn't lane however close it is. Its cell and the eight around it are looked at; near
    the bases a cell can belong to two lanes and then it doesn't matter which of the two comes out."""
    cx, cz = int(x // CELL), int(z // CELL)
    for i, j in ((0, 0), (0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)):
        if own := state["corridors"].get((cx + i, cz + j)):
            return min(own)
    return None


CHARGES = {"TrinketTotemLvl1": (2, 100.0), "TrinketOrbLvl3": (2, 100.0), "ItemGhostWard": (5, 20.0)}
WARD_UNITS = ("SightWard", "YellowTrinket", "JammerDevice")  # the character a ward is born as:
# the yellow one was renamed YellowTrinket in 16.19 (in 16.18 all three were born as SightWard)
CONTROL = 2055  # the control ward is the only one that is bought, so that one is counted exactly


def _charges(placed_times: list[float], maximum: int, refresh: float, t: float) -> float:
    """Charges of the ward item at that moment: it starts full and recovers one every `refresh` seconds.

    The two numbers come from the data itself, not from the game: they are the strictest that **contradict
    no placed ward** in the matches read (with a 120 s refresh the model said five wards were
    placed with no charges, with 100 none fails).

    ponytail: the real cooldown of the trinket drops with level and that of the support item rises with the
    upgrades. The exact value would come from Data Dragon, like the item prices."""
    charges, last_ = float(maximum), 0.0
    for put in placed_times:
        if put > t:
            break
        charges = max(0.0, min(maximum, charges + (put - last_) / refresh) - 1)
        last_ = put
    return min(maximum, charges + (t - last_) / refresh)


def _under_tower(rows, champion: str, state: dict, towers: dict, lane: str,
                since: float, until: float) -> set[int]:
    """The seconds of that stretch in which the champion is behind their own outer turret.

    Their position is projected on the same axis as the waves and compared with where their turret is, which
    `_towers` measures with the minions it finishes."""
    blue, red = state["axis"][lane]["blue"], state["axis"][lane]["red"]
    out = set()
    for f in _window(rows, champion, since, until):
        if not f["x"] or f["alive"] != "True":
            continue
        advance = (float(f["x"]) + float(f["z"]) - blue) / (red - blue)
        own_entry = towers.get((lane, "blue" if f["team"] == "100" else "red"))
        if own_entry is not None and (advance <= own_entry if f["team"] == "100" else advance >= own_entry):
            out.add(round(float(f["time"])))
    return out


def payoff(events: dict, state: dict, rows, clashes: list[dict], window: float = 30.0,
             fog: float = 8.0, hit: float = 0.03) -> list[dict]:
    """What each one does with the prio that crashing the wave gives.

    A crashed wave is prio: the enemy is tied to their turret and you are left a few seconds free.
    There is always something to do with them —go back to base, place vision (the deeper on the enemy side,
    the better), hit the enemy under their turret, rotate to another lane or a camp— and, if there is nothing better,
    at least **go into fog** so the enemy doesn't know what you are going to do. A crash with no use at all is
    suboptimal.

    Here it isn't said which of the uses was the good one: that depends on the match context and is exactly what
    the model has to learn with many matches. The one chosen is noted, and the only judgement made
    is that of choosing none.

The fog comes from the state table's `seen` column, which is "visible to the opposing team":
    `fog` consecutive seconds without being seen count. Wards come from the `CastSpell` of their item, which
    carries the point where the ward lands and not the placer's. Harass only counts when the enemy is
    **behind their own turret** —which is what the crashed wave gives you— and is measured as a share of their maximum
    health, not as loose damage, so that it is worth the same at minute 3 as at 13.

    From each crash it also comes out whether they **could** place vision (`could_ward`): a charge of their ward item,
    with the `_charges` model, or a control ward bought and unplaced. Not warding isn't the same as not being
    able to."""
    net_of = {p["champion"]: p["net_id"] for p in events["players"]}
    towers = _towers(events, state)
    position = {p["champion"]: p["position"] for p in events["players"]}
    team = {p["champion"]: p["team"] for p in events["players"]}
    rival_of = {a: b for a in position for b in position
                if a != b and position[a] == position[b] and team[a] != team[b]}
    own_items = collections.defaultdict(list)
    for p in events["players"]:
        if p["position"] in LANES:
            own_items[(LANES[p["position"]], "blue" if p["team"] == "100" else "red")].append(p["champion"])

    recalls, placements = collections.defaultdict(list), collections.defaultdict(list)
    damage, per_item, bought = collections.defaultdict(list), collections.defaultdict(list), collections.defaultdict(list)
    for e in events["events"]:
        if e["type"] == "AddBuff" and e["buff"].lower() == "recall":
            recalls[e["net_id"]].append(e["time"])
        elif e["type"] == "CastSpell" and e["spell"] in WARDS:
            placements[e["net_id"]].append((e["time"], e["target"]))
            per_item[(e["net_id"], e["spell"])].append(e["time"])
        elif e["type"] == "BuyItem" and e["item_id"] == CONTROL:
            bought[e["net_id"]].append(e["time"])
        elif e["type"] == "Damage" and e.get("source"):
            damage[(e["source"], e["net_id"])].append((e["time"], e["amount"]))

    def has_ward(net: str, t: float) -> bool:
        """They have some ward left to place: a charge of their item or a control ward bought and unplaced."""
        if sum(c <= t for c in bought[net]) > sum(x <= t for x in per_item[(net, "JammerDevice")]):
            return True
        return any(_charges(per_item[(net, item)], *charges, t) >= 1
                   for item, charges in CHARGES.items() if per_item[(net, item)])

    out = []
    for c in clashes:
        since, until = c["time"], c["ends"] + window
        for champion in own_items[(c["lane"], c["side"])]:
            net, uses = net_of[champion], []
            if any(since <= t <= until for t in recalls[net]):
                uses.append("goes back to base")
            deepest = sorted(((_depth(*w, c["side"]), _corridor(state, *w))
                             for t, w in placements[net] if since <= t <= until), reverse=True)
            if deepest:
                deep, where = deepest[0]
                uses.append(f"vision {'in ' + where if where else 'in the jungle'} at {deep:+.0%} from the river")
            rival = rival_of.get(champion, "")
            under, endures = _under_tower(rows, rival, state, towers, c["lane"], since, until), 0.0
            hit_damage = sum(a for t, a in damage[(net, net_of.get(rival, ""))] if round(t) in under)
            for f in _window(rows, rival, since, until):
                endures = max(endures, _num(f, "health_max") or 0)
            if endures and hit_damage >= hit * endures:  # only the damage you put in while keeping them tied to their turret counts
                uses.append(f"harass under tower for {hit_damage / endures:.0%} of their health")
            if any(cam["killer"] == net and since <= cam["time"] <= until for cam in events["camps"]):
                uses.append("camp")
            stretch = [f for f in _window(rows, champion, since, until) if f["x"] and f["alive"] == "True"]
            if stretch and sum(_lane(float(f["x"]), float(f["z"])) != c["lane"] for f in stretch) > len(stretch) / 2:
                uses.append("rotates to another lane")
            hidden = max((len(list(g)) for visible, g in itertools.groupby(f["seen"] == "True" for f in stretch)
                          if not visible), default=0)
            if not uses and hidden >= fog:
                uses.append(f"goes into the fog for {hidden} s")
            out.append({"lane": c["lane"], "side": c["side"], "time": c["time"], "stack": c["stack"],
                          "champion": champion, "uses": uses, "hidden": hidden,
                          "could_ward": has_ward(net, since),
                          "dead": not stretch, "cs_lost": c["cs_lost"]})
    return out


RANGE = {"ward": 900.0, "champion": 1350.0}  # what each thing sees, as in the decoder


def _wards(events: dict) -> list[tuple[float, float, tuple[float, float], str, str]]:
    """Each ward: (when it appears, when it disappears, where, which team, who places it).

    The item's `CastSpell` says where the ward lands and whose it is; the `SpawnMinion` of the same instant gives
    the id by which it later dies. The two arrive with the same timestamp, so they pair up by themselves."""
    owner_of = {p["net_id"]: p["team"] for p in events["players"]}
    champion_by_net = {p["net_id"]: p["champion"] for p in events["players"]}
    cast = collections.defaultdict(list)
    for e in events["events"]:
        if e["type"] == "CastSpell" and e["spell"] in WARDS:
            cast[round(e["time"], 3)].append((e["net_id"], tuple(e["target"])))
    died = {e["net_id"]: e["time"] for e in events["events"] if e["type"] == "UnitDeath"}
    out = []
    for e in events["events"]:
        if e["type"] == "SpawnMinion" and e.get("character") in WARD_UNITS:
            if own_items := cast.get(round(e["time"], 3)):
                net, where = own_items.pop(0)
                out.append((e["time"], died.get(e["net_id"], float("inf")), where,
                              owner_of.get(net, ""), champion_by_net.get(net, "")))
    return out


def _river_passes(events: dict) -> dict[str, tuple[float, float]]:
    """The two river passes, taken from where each crab dies: they don't have to be set by hand."""
    out = {}
    for side in ("top", "bot"):
        own_items = [c["position"] for c in events["camps"] if c["camp"] == "Scuttle" and c.get("side") == side]
        if own_items:
            out[side] = (statistics.median(p[0] for p in own_items), statistics.median(p[1] for p in own_items))
    return out


def exposure(events: dict, state: dict, rows, since: float = 120.0, until: float = 840.0,
               near: float = 2000.0) -> list[dict]:
    """How long each laner plays on enemy ground without knowing where the enemy jungler is.

    The concept is playing always against the worst case: if you have no information, you have to assume
    the enemy jungler is in the fog waiting to gank you. Here that isn't approximated with a hand-set number of
    seconds, it is computed: since your team last saw them, **have they had time to
    reach you?** It is measured with the distance from their last known position to yours and their movement
    speed at that moment. If they have had time, you are playing blind.

    It is a conservative count in the good sense: the straight line ignores walls, so it says they
    could be on top of you sooner than they really could. That is exactly what the concept asks for.

    The time is split into three zones, and none is an invented number: your half, the enemy's half (from
    the lane's centre) and **overextend**, which is past where their outer turret is,
    which `_towers` measures with the minions it finishes.

    For each zone come the blind seconds, how many of them also without vision of the river —neither a live ward
    nor a teammate near the crab's pass—, and how many with the wave also pushed into enemy territory, which
    is the part that comes from bad wave management and not from a decision.

    The last column is the check: of those blind seconds, in how many were they **really** within
    `near`. The player didn't know that, but it says whether the risk was real or they got away with it. And
    `blind_deaths` are the times they died while like that, whether or not the jungler was the one who killed them: what is
    judged is being there without information, not whom the blow came from."""
    towers = _towers(events, state)
    passes = _river_passes(events)
    wards = _wards(events)
    junglers = {p["team"]: p["champion"] for p in events["players"] if p["position"] == "JUNGLE"}
    deaths = collections.defaultdict(list)
    champion_by_net = {p["net_id"]: p["champion"] for p in events["players"]}
    for e in events["events"]:
        if e["type"] == "Death" and e["net_id"] in champion_by_net:
            deaths[champion_by_net[e["net_id"]]].append(e["time"])

    def per_second(champion):
        return {int(float(f["time"])): f for f in rows.get(champion, [])}

    table = {p["champion"]: per_second(p["champion"]) for p in events["players"]}
    out = []
    for player in events["players"]:
        champion, own = player["champion"], player["position"]
        if own not in LANES:
            continue
        lane, team = LANES[own], player["team"]
        side = "blue" if team == "100" else "red"
        jungler = junglers.get("200" if team == "100" else "100")
        if not jungler:
            continue
        blue, red = state["axis"][lane]["blue"], state["axis"][lane]["red"]
        tower = towers.get((lane, "red" if side == "blue" else "blue"))
        count, died = collections.Counter(), collections.defaultdict(set)
        seen_where, seen_when = None, None
        for t in range(int(since), int(until) + 1):
            own_t, jg = table[champion].get(t), table[jungler].get(t)
            if not jg or not jg["x"]:
                continue
            if jg["seen"] == "True":
                seen_where, seen_when = (float(jg["x"]), float(jg["z"])), t
            if not own_t or not own_t["x"] or own_t["alive"] != "True":
                continue
            me = (float(own_t["x"]), float(own_t["z"]))
            advance = (me[0] + me[1] - blue) / (red - blue)
            ahead = advance > 0.5 if side == "blue" else advance < 0.5
            if not ahead:
                count["at_home"] += 1
                continue
            past = tower is not None and (advance > tower if side == "blue" else advance < tower)
            zone = "overextend" if past else "half_rival"
            count[zone] += 1
            # have they had time to arrive since the last time we saw them?
            speed = _num(jg, "move_speed") or 330.0
            blind = seen_where is None or (t - seen_when) >= math.dist(seen_where, me) / speed
            if not blind:
                continue
            count[f"{zone}_blind"] += 1
            step = min(passes.values(), key=lambda p: math.dist(p, me)) if passes else None
            if step and not _sees_river(wards, table, events, team, step, t):
                count[f"{zone}_no_river"] += 1
            spot = _advance(state, lane, t)
            if spot and (spot[0] > 0.5 if side == "blue" else spot[0] < 0.5):
                count[f"{zone}_with_the_wave"] += 1
            if math.dist((float(jg["x"]), float(jg["z"])), me) <= near:
                count[f"{zone}_and_was"] += 1
            died[zone] |= {m for m in deaths[champion] if t <= m <= t + 3}  # dies there, playing blind
        all_ = set().union(*died.values()) if died else set()
        in_lane = count["at_home"] + count["half_rival"] + count["overextend"]
        out.append({"champion": champion, "lane": lane, "team": team, "rival_jungler": jungler,
                      "blind_deaths": sorted(all_),
                      # the share of living time in lane spent past the centre toward the enemy turret, whether or not they see the jungler
                      "rival_side": (count["half_rival"] + count["overextend"]) / in_lane if in_lane else None}
                     | dict(count) | {f"{zone}_dies": len(when) for zone, when in died.items()})
    return out


def _sees_river(wards, table, events: dict, team: str, step: tuple[float, float], t: float) -> bool:
    """The team has vision of that river pass: a live ward on top or one of their own beside it."""
    if any(t0 <= t <= t1 and own == team and math.dist(where, step) <= RANGE["ward"]
           for t0, t1, where, own, _who in wards):
        return True
    for p in events["players"]:
        f = table[p["champion"]].get(int(t))
        if (p["team"] == team and f and f["x"] and f["alive"] == "True"
                and math.dist((float(f["x"]), float(f["z"])), step) <= RANGE["champion"]):
            return True
    return False


def _gets_burned(spell: str) -> bool:
    """A summoner spell of those spent when you are pressed (flash, heal, barrier, ignite…). Not Smite,
    which the jungler uses on every camp and which came out as "burns Smite" in any fight in the jungle, nor
    Teleport."""
    name = spell.lower()
    return name.startswith("summoner") and "smite" not in name and "teleport" not in name


SUMMONERS = {"summonerdot": "Ignite", "summonerboost": "Cleanse", "summonerhaste": "Ghost",
               "summonerbarrier": "Barrier", "summonerexhaust": "Exhaust", "summonerflash": "Flash",
               "summonerheal": "Heal", "summonerteleport": "TP", "summonersmite": "Smite"}


def _camps(events: dict, side: str) -> dict[str, list[float]]:
    """When each small camp on that side of the jungle falls, in order."""
    out = collections.defaultdict(list)
    for c in events["camps"]:
        if c["camp"] in SMALL and c.get("side") == side:
            out[c["camp"]].append(c["time"])
    return {camp: sorted(when) for camp, when in out.items()}


def _alive_now(falls: dict[str, list[float]], t: float, period: float = 138.0) -> list[str]:
    """Which of their small camps are alive at that moment: farming being left behind."""
    return sorted(camp for camp, when in falls.items()
                  if (before := [x for x in when if x < t]) and before[-1] + period <= t)


PRESSURE = 2500.0  # how far whoever shows themselves pressures an enemy laner: see `_pressured`
RETREATS = 0.12  # how far that laner must retreat, in advance along their lane, to count
PUSHES = 0.10  # how far the wave of that lane must advance in favour of whoever shows themselves


def _pressured(table: dict, state: dict, who: str, rivals: list[dict], recalls: dict[str, list[float]],
                 a: int, b: int, drag: float) -> list[tuple[str, str, str]]:
    """The enemy laners that `who` pressures by showing themselves between `a` and `b`, with what each does:
    (champion, lane, "goes back to base" | "retreats" | "").

    They pressure the laner who is in their lane and has them in view within PRESSURE at some second of the
    window. The
    range is measured, not set by eye (255 matches of 16.19, from Gold to Challenger): in any 16 s with
    no enemy in view, a laner retreats 0.05 of lane or goes back to base 28% of the time; with the enemy jungler
    in view within 2500, 40-47%; between 2500 and 4000, 33%; and farther, 27-30%, the same
    as with nobody. With the roaming support it's the same (44% within 1600, 31% between 3000 and 3500). Before,
    any laner in that zone of the map counted: a top who went back to base after crashing their wave came out as
    pressure from a jungler who was at their Raptors.

    And since one in four retreats 0.05 without anyone forcing them, RETREATS is required: 0.12 of lane is walked
    by 25% with the jungler near and 11% with nobody (with 0.05 it was 38% and 23%)."""

    def spot(champion: str, t: float) -> tuple[float, float] | None:
        f = table[champion].get(int(t))
        return (float(f["x"]), float(f["z"])) if f and f["x"] and f["alive"] == "True" else None

    out = []
    for r in rivals:
        rival, lane = r["champion"], LANES[r["position"]]
        near = [t for t in range(int(a), int(b) + 1)
                 if table[who].get(t, {}).get("seen") == "True"
                 and (p := spot(who, t)) and (q := spot(rival, t)) and math.dist(p, q) <= PRESSURE
                 and not _out_of_lane(state, lane, *q)]
        if not near:
            continue
        does, axis = "", state["axis"].get(lane)
        going = [spot(rival, t) for t in (near[0], b + drag)]
        if any(near[0] <= x <= b + drag for x in recalls[rival]):
            does = "goes back to base"
        elif all(going) and axis:
            adv = [(p[0] + p[1] - axis["blue"]) / (axis["red"] - axis["blue"]) for p in going]
            if (adv[1] - adv[0]) * (1 if r["team"] == "200" else -1) >= RETREATS:  # toward their own base
                does = "retreats"
        out.append((rival, lane, does))
    return out


def show_up(events: dict, state: dict, rows, since: float = 120.0, until: float = 840.0,
              minimum: float = 3.0, stuck: float = 3.0, near: float = 1500.0, drag: float = 8.0,
              period: float = 138.0) -> list[dict]:
    """How long the jungler goes without being seen, and what they get from the times they show themselves.

    It is the other side of `exposure`. If the enemy lanes don't know where you are, **you are pressuring all
    three at once** doing nothing: they have to play against the worst case. That is why invisible time is worth
    something by itself, and why showing yourself costs something and has to be made to count.

    An exposure window is a run of seconds in which the enemy team sees them (`seen`), merging
    those less than `stuck` seconds apart and keeping those of `minimum` and up. For each one it is
    looked at what came out, in the window and up to `drag` seconds afterwards:

    - **summoner**: an enemy within `near` burns a summoner spell. Showing yourself for a gank and not
      getting even the flash is the case worth nothing;
    - **kill**: an enemy dies that they managed to hit (being next to one their laner takes
      doesn't count as theirs);
    - **the enemy retreats** or goes back to base: only the laner they have in range (`_pressured`);
    - **the wave moves** in favour in that laner's lane by more than PUSHES: their teammate could push (with the
      jungler within PRESSURE it advances 0.10 21% of the time; with nobody in view, 9%).

    `near` are the enemy laners they pressure, and `lane`, the first one's. A window with nobody in range
    isn't showing yourself in a lane: it is that a ward (or a minion) far from everyone saw them, and it neither pressures nor can be
    asked to get anything; it goes with `lane` None.

    And against that, what it cost: their small camps that were alive meanwhile. A gank that
    comes off but with two camps stalled isn't free.

    It isn't weighed which of the four is worth more: that depends on the game state and is what the model has to
    learn. The only thing judged here is showing yourself in a lane and getting none."""
    junglers = {p["team"]: p["champion"] for p in events["players"] if p["position"] == "JUNGLE"}
    champion_by_net = {p["net_id"]: p["champion"] for p in events["players"]}
    team_of = {p["champion"]: p["team"] for p in events["players"]}

    summoners, deaths, recalls = collections.defaultdict(list), [], collections.defaultdict(list)
    hit_damage = collections.defaultdict(list)
    for e in events["events"]:
        if e["type"] == "Damage" and e.get("source") in champion_by_net and e["net_id"] in champion_by_net:
            hit_damage[(champion_by_net[e["source"]], champion_by_net[e["net_id"]])].append(e["time"])
        if e["type"] == "CastSpell" and e["net_id"] in champion_by_net and e["slot"] in (4, 5) and _gets_burned(e["spell"]):
            summoners[champion_by_net[e["net_id"]]].append((e["time"], e["spell"]))
        elif e["type"] == "Death" and e["net_id"] in champion_by_net:
            deaths.append((e["time"], champion_by_net[e["net_id"]]))
        elif e["type"] == "AddBuff" and e["buff"].lower() == "recall" and e["net_id"] in champion_by_net:
            recalls[champion_by_net[e["net_id"]]].append(e["time"])
    table = {p["champion"]: {int(float(f["time"])): f for f in rows.get(p["champion"], [])}
             for p in events["players"]}

    def where(champion: str, t: float) -> tuple[float, float] | None:
        f = table[champion].get(int(t))
        return (float(f["x"]), float(f["z"])) if f and f["x"] and f["alive"] == "True" else None

    out = []
    for team, jungler in junglers.items():
        rival_team = "200" if team == "100" else "100"
        side = "blue" if team == "100" else "red"
        rival_laners = [p for p in events["players"] if p["team"] == rival_team and p["position"] in LANES]
        falls = _camps(events, side)
        own_items = table[jungler]
        windows, open_, last_ = [], None, None
        invisible, sighted, streak, worst = 0, 0, 0, 0
        for t in range(int(since), int(until) + 1):
            f = own_items.get(t)
            if f and f["seen"] == "True" and f["alive"] == "True":
                sighted, streak = sighted + 1, 0
                if open_ and t - last_ <= stuck:
                    open_[1] = t
                else:
                    if open_:
                        windows.append(open_)
                    open_ = [t, t]
                last_ = t
            elif f and f["alive"] == "True":
                invisible, streak = invisible + 1, streak + 1
                worst = max(worst, streak)
        if open_:
            windows.append(open_)

        departures = []
        for a, b in (v for v in windows if v[1] - v[0] + 1 >= minimum):
            wins = []
            # the spell is burned by an enemy who has them within `near` in that same second
            burned = [(t, s, champion) for champion, own_rows in summoners.items()
                        if team_of[champion] == rival_team
                        for t, s in own_rows if a <= t <= b + drag
                        and (p := where(champion, t)) and (me := where(jungler, t)) and math.dist(p, me) <= near]
            if burned:
                wins.append("burns " + ", ".join(sorted({SUMMONERS.get(s.lower(), s) for _t, s, _c in burned})))
            # the kill counts if they managed to hit: being next to one their laner takes isn't theirs
            falls_ = [c for t, c in deaths if a <= t <= b + drag and team_of.get(c) == rival_team
                   and any(t - drag <= x <= t for x in hit_damage[(jungler, c)])]
            if falls_:
                wins.append("kills " + ", ".join(sorted(set(falls_))))
            presses = _pressured(table, state, jungler, rival_laners, recalls, a, b, drag)
            for lane in dict.fromkeys(c for _r, c, _h in presses):
                before, after = _advance(state, lane, a), _advance(state, lane, b + drag + 12)
                if before and after and (advances := (after[0] - before[0]) * (1 if side == "blue" else -1)) >= PUSHES:
                    wins.append(f"their wave advances {advances:+.2f}")
            wins += [f"{rival} {does}" for rival, _c, does in presses if does]
            standing = _alive_now(falls, a, period)
            departures.append({"since": a, "until": b, "lane": presses[0][1] if presses else None,
                            "near": [r for r, _c, _h in presses], "wins": wins, "standing": standing})
        out.append({"jungler": jungler, "team": team, "invisible": invisible, "visible": sighted,
                      "streak_invisible": worst, "windows": departures})
    return out


RANKS = ("OUTER_TURRET", "INNER_TURRET", "BASE_TURRET", "NEXUS_TURRET")  # from outside inward
LANE_TL = {"TOP_LANE": "top", "MID_LANE": "mid", "BOT_LANE": "bot"}


def turrets(events: dict, state: dict, minimum: int = 5) -> list[dict]:
    """Each turret with its place, which team it belongs to, which lane it is in and which of the four it is (`rank`:
    OUTER_TURRET is the tier 1, INNER_TURRET the tier 2).

    The place comes from the replay without the turret sending it: turrets finish minions and the median of where the ones
    they finish fall is a shot's distance from it (against the position the timeline gives on falling, the offset is 500
    to 850 units, always toward the attacker). The rank comes from the order: of theirs in that lane, the first
    toward the enemy is the outer. Only those finishing `minimum` minions enter, so the base and nexus ones almost
    never come out."""
    ids = {e["net_id"] for e in events["events"]
           if e["type"] == "SetSpell" and "Turret" in (e.get("name") or "")}
    finish = collections.defaultdict(list)
    for e in events["events"]:
        s = state["minions"].get(e["net_id"]) if e["type"] == "UnitDeath" else None
        if s and s["where"] and e["killer"] in ids:
            finish[e["killer"]].append((s["where"], s["lane"]))

    towers = []
    for tower, own_items in finish.items():
        if len(own_items) < minimum:
            continue
        x, z = (statistics.median(d[i] for d, _c in own_items) for i in (0, 1))
        towers.append({"spot": x + z, "x": x, "z": z, "team": "100" if x + z < RIVER else "200", "id": tower,
                       "lane": collections.Counter(c for _d, c in own_items).most_common(1)[0][0]})
    for team in ("100", "200"):
        ahead = -1 if team == "100" else 1  # blue advances by raising x+z; red, by lowering it
        for lane in ("top", "mid", "bot"):
            own_rows = sorted((t for t in towers if t["team"] == team and t["lane"] == lane),
                           key=lambda t: ahead * t["spot"])
            for rank, tower in zip(RANKS, own_rows, strict=False):
                tower["rank"] = rank
    return [t for t in towers if t.get("rank")]


def _tower_line(events: dict, state: dict, timeline: dict | None = None,
                     minimum: int = 5) -> collections.abc.Callable[[str, float], float]:
    """Each team's "turret line" second by second, in x+z.

    It is the line from the Dignitas guide: the frontier of what is yours and the place up to which you ward without asking
    permission. It returns a function (team, lane, second) → x+z, with the two things that move it:

    - **the lane**, because the line goes from your outer mid turret to the top or bot one, and between the three there are
      up to 900 units of x+z; comparing a top ward against the mid one overshoots by almost a turret shot;
    - **the moment**, because when a turret of yours is taken your frontier in that lane becomes the next one
      inward, and that of whoever took it stretches to there. That is what the guide says with "as your
      team takes turrets, the warding line moves".

    Each turret's position comes from the replay without it sending it: turrets kill minions, and the median
    of where the ones they finish fall is a shot's distance from it (against the exact position the timeline gives on
    falling, the offset is 500 to 850 units, always toward the attacker).

    When each turret falls doesn't come in `UnitDeath`, but it does in the gold it distributes on falling: the `Gold` with it as
    the origin. Against the timeline's `BUILDING_KILL` (25 matches), 265 of 285 falls come out this way, to the second and with
    none extra; those missing are the ones minions take down with nobody near, which distribute no local gold. With the timeline
    both things are used: its `BUILDING_KILL`, matched by team, lane and rank, and the gold.

    ponytail: only the turrets that finish minions enter, and the base and nexus ones almost never reach the minimum.
    When the outer and inner of a lane fall, the frontier goes to the base instead of staying at the
    base one. It happens from minute 17 on and always toward the permissive side."""
    towers = turrets(events, state, minimum)

    falls_ = {}
    for e in api_events(timeline):
        if e.get("type") == "BUILDING_KILL" and e.get("buildingType") == "TOWER_BUILDING":
            falls_[(str(e["teamId"]), LANE_TL.get(e.get("laneType")), e.get("towerType"))] = e["timestamp"] / 1000
    for e in events["events"]:
        if e["type"] == "Gold" and e["unit"] in {x["id"] for x in towers}:
            falls_.setdefault(e["unit"], e["time"])

    def line(team: str, lane: str, t: float) -> float:
        """That team's frontier in that lane and at that moment: its most advanced turret still standing."""
        standing_ = [x["spot"] for x in towers if x["team"] == team and x["lane"] == lane
                  and falls_.get((team, lane, x.get("rank")), math.inf) > t and falls_.get(x["id"], math.inf) > t]
        if not standing_:  # with no turrets in that lane the frontier goes to their base: it no longer limits anything
            return -math.inf if team == "100" else math.inf
        return max(standing_) if team == "100" else min(standing_)

    return line


SIEGE = 20.0  # seconds without touching a turret that split a siege in two
NEAR_TOWER = 1300.0  # within this of the turret, they are at it (a turret shot is 775)
MIN_HIT = 150.0  # health a turret must lose for it to count as having been hit


def sieges(events: dict, state: dict, rows, healths: dict[str, list[tuple[float, float]]],
            minimum: float = MIN_HIT, gap: float = SIEGE, near: float = NEAR_TOWER) -> list[dict]:
    """Each stretch in which a turret is hit, with what is taken from it and who was in front.

    The turrets' health comes from the harvest (`read_turrets`, from the `UpdateState` they send themselves), and
    each turret is placed with `turrets`. The health drops that are no more than `gap` seconds apart are
    grouped, and from each group comes which turret, how much health is taken, who of each team was within `near` of
    it meanwhile and whether it ended up falling.

    It is what couldn't be seen with the events: a turret that doesn't fall but loses half its health while its
    owner is elsewhere, which conditions all the following waves of that lane. Rises
    don't count: turrets regenerate in steps of two."""
    where = {t["id"]: t for t in turrets(events, state)}
    table = _table(events, rows)
    team_of = {p["champion"]: p["team"] for p in events["players"]}
    falls_ = {}
    for e in events["events"]:  # the gold it distributes on falling, as in `_tower_line`
        if e["type"] == "Gold" and e.get("unit") in where:
            falls_[e["unit"]] = e["time"]

    out = []
    for net, series in healths.items():
        tower = where.get(net)
        if not tower:
            continue
        group: list[tuple[float, float, float]] = []  # (t, health before, health after)
        for (t0, a), (t1, b) in zip(series, series[1:], strict=False):
            if b < a:
                if group and t1 - group[-1][0] > gap:
                    out.append(_siege(tower, group, table, team_of, falls_, near))
                    group = []
                group.append((t1, a, b))
        if group:
            out.append(_siege(tower, group, table, team_of, falls_, near))
    return sorted((a for a in out if a["health_lost"] >= minimum), key=lambda a: a["since"])


def _siege(tower: dict, group: list[tuple[float, float, float]], table: dict, team_of: dict[str, str],
            falls_: dict[str, float], near: float) -> dict:
    """A stretch of hits on a turret: what it loses and who was in front for each team."""
    since, until = group[0][0], group[-1][0]
    loss = sum(a - b for _t, a, b in group)
    spot = (tower["x"], tower["z"])
    who = {"100": set(), "200": set()}
    for champion, own_rows in table.items():
        for t in range(int(since) - 3, int(until) + 4):
            f = own_rows.get(t)
            if f and f["x"] and f["alive"] == "True" and math.dist((float(f["x"]), float(f["z"])), spot) <= near:
                who[team_of[champion]].add(champion)
                break
    rival = "200" if tower["team"] == "100" else "100"
    return {"tower": tower["id"], "team": tower["team"], "lane": tower["lane"], "rank": tower["rank"],
            "x": round(tower["x"]), "z": round(tower["z"]), "since": round(since, 1), "until": round(until, 1),
            "health_before": round(group[0][1]), "health_after": round(group[-1][2]),
            "health_lost": round(loss), "hits": len(group),
            "defend": sorted(who[tower["team"]]), "attack": sorted(who[rival]),
            "falls": int(tower["id"] in falls_ and since <= falls_[tower["id"]] <= until + 5)}

KINDS = {"TrinketTotemLvl1": "totem", "TrinketOrbLvl3": "totem", "JammerDevice": "control",
         "ItemGhostWard": "support"}
EPICS_WARD = ("sru_dragon", "sru_baron", "sru_riftherald", "sru_horde", "sru_atakhan")  # what is set up with vision
SETUP = 90.0  # seconds before an objective spawns in which a ward in its zone is setting it up (the guides: 45-90)
OBJECTIVE_ZONE = 3500.0  # how far an objective's zone reaches from its pit: the river and the jungle entrances
RESET = 75.0  # seconds after leaving base in which a ward is the on-the-way-back one


def _spawns(events: dict) -> list[tuple[float, float, tuple[float, float]]]:
    """(when it spawns, when it falls, where) of each epic objective in the match, to know which one is being set up."""
    spawn_times = sorted((e["time"], e["net_id"], tuple(e["position"])) for e in events["events"]
                   if e["type"] == "SpawnNeutral" and (e.get("character") or "").lower().startswith(EPICS_WARD))
    died = {e["net_id"]: e["time"] for e in events["events"] if e["type"] == "UnitDeath"}
    return [(t, died.get(net, math.inf), spot) for t, net, spot in spawn_times if any(spot)]


def vision(events: dict, state: dict, rows, timeline: dict | None = None, since: float = 120.0,
           until: float | None = 840.0, push: float = 0.02) -> list[dict]:
    """What information each ward produces, which is the only thing that makes a ward good, when it was placed and what
    was risked by placing it. With `until=None`, the whole match.

    The three guides say the same in different words: a ward is worth the play it allows, not
    being placed. Here that is really measured: **did it show anyone?** An enemy counts as revealed by the
    ward if they are within its range, visible to the team that placed it, and **there is no living ally
    close enough to see them themselves**. That way the information is credited to the ward and not to the teammate who
    was passing by.

    For each ward come where it lands —own half, river or enemy half, with the depth—, whether it is **past the
    enemy's turret line** (see `_tower_line`), which is where nothing covers you any more, how long it
    lives, whether an enemy kills it (`sweep`), whom it showed and for how many seconds.

    **When it was placed** (`moment`), with the windows the guides give, in order:

    - `objective`: within OBJECTIVE_ZONE of the pit of an objective that is alive or spawns in SETUP seconds.
      It is the vision that sets up the objective: the entrances before the pit;
    - `prio`: with their lane's wave pushed, which is when the deep ward is earned (the rule below);
    - `reset`: in the RESET seconds after leaving base, which is the on-the-way-back ward, with the
      charges just renewed;
    - `loose`: none of the above.

    **What was risked** (`risk`), by where they were when placing it and not by where the ward lands. The level comes from
    what really happens after wards like that (`costs_it`: dying in the following 15 s), measured over the 255,928
    support wards from the 5,143 matches of 16.19 placed outside a fight, after which 3.9% die:

    - **what predicts death is having enemies already seen on top of you**: with none in view within 1500
      (`in_sight`) 2.4% die; with one, 6.4%; with two, 10.1%; with three or more, 15.7%;
    - **and who you are with, but only once they already see you**. With two enemies in view, 9.2% die if they have a
      teammate within 2000 and 14.4% if alone; with three or more, 15.3% against 19.3%. With one or
      none it makes no difference (6.3 against 6.4, and 2.5 against 2.2): placing a ward accompanied isn't safer in itself,
      what changes is whether they can jump on you with nobody answering;
    - **walking in blind doesn't kill by itself**: with no enemies in view, being past the river or alone makes no difference
      (2.0-2.7% in the four cases), and adding the unaccounted-for enemies (`uncounted`, `exposure`'s count:
      since they were seen, have they had time to arrive?) moves nothing either: 1.6% with zero, 2.2% with four and
      2.4% with all five. A sample of 8,480 wards said that with all five it rose to 22%; with all the matches,
      it was noise.

    `high`: three or more enemies in view, or two while alone (16% die). `mid`: one in view, or two with
    someone beside you (7%). `under`: none in view (2.4%). `passed` and `uncounted` are stored all the same, because they
    describe the ward even if they don't predict death. `in_fight` says whether they were already fighting someone in the 5 s
    before: that ward belongs to the fight, it isn't a facecheck.

    And the two rules that all three sources repeat:

    - **push before warding**: a ward **past the enemy's turret line** is only earned with the
      wave pushed. Up to there it is normal warding; beyond, without prio, it is the one that ends in death.
      **The support is exempt** (`exempt`): their job is vision and they move around the map without the
      state of the bot wave giving or taking away permission, so skipping the prio is suboptimal but doesn't
      count as a mistake. The datum is stored all the same —the ward is still marked without prio— and what changes is the
      judgement, not the measurement: if with many matches it turns out it also costs the support dearly, it will be there
      to be seen;
    - **don't go back to base with wards to spare**: the recall that completes carrying the ward item
      **at full charges** or a control ward bought and unplaced is counted. Having one loose charge is
      normal; arriving at base with a full bar is a refresh thrown away.

    The place isn't judged against any list of good places: what it produced is judged."""
    until = events["game_length"] if until is None else until
    owner_of = {p["net_id"]: p["team"] for p in events["players"]}
    champion_by_net = {p["net_id"]: p["champion"] for p in events["players"]}
    junglers = {p["team"]: p["champion"] for p in events["players"] if p["position"] == "JUNGLE"}
    line = _tower_line(events, state, timeline)
    table = {p["champion"]: {int(float(f["time"])): f for f in rows.get(p["champion"], [])}
             for p in events["players"]}
    sighted = {p["champion"]: _last_seen(rows, p["champion"], until) for p in events["players"]}
    pits = _spawns(events)

    placements, per_item, recalls = [], collections.defaultdict(list), collections.defaultdict(list)
    cast, bought = collections.defaultdict(list), collections.defaultdict(list)
    bases = _bases(rows)
    deaths, hits = collections.defaultdict(list), collections.defaultdict(list)
    for e in events["events"]:
        if e["type"] == "BuyItem" and e["item_id"] == CONTROL:
            bought[e["net_id"]].append(e["time"])
        if e["type"] == "CastSpell" and e["spell"] in WARDS:
            cast[round(e["time"], 3)].append((e["net_id"], tuple(e["target"]), e["spell"], tuple(e["origin"])))
            per_item[(e["net_id"], e["spell"])].append(e["time"])
        elif e["type"] == "AddBuff" and e["buff"].lower() == "recall" and e["net_id"] in champion_by_net:
            recalls[e["net_id"]].append(e["time"])
        elif e["type"] == "Death" and e["net_id"] in champion_by_net:
            deaths[e["net_id"]].append(e["time"])
        elif e["type"] == "Damage" and e["net_id"] in champion_by_net and e.get("source") in champion_by_net:
            for who in (e["net_id"], e["source"]):
                hits[who].append(e["time"])
    died = {e["net_id"]: (e["time"], e.get("killer")) for e in events["events"] if e["type"] == "UnitDeath"}
    for e in events["events"]:
        if e["type"] == "SpawnMinion" and e.get("character") in WARD_UNITS:
            if own_items := cast.get(round(e["time"], 3)):
                net, where, item, from_where = own_items.pop(0)
                falls_, killed_by = died.get(e["net_id"], (float("inf"), None))
                placements.append({"net_id": net, "champion": champion_by_net.get(net), "team": owner_of.get(net),
                                "kind": KINDS.get(item, item), "when": e["time"], "where": where,
                                "places_since": from_where, "until": min(falls_, e["time"] + 300),
                                # an enemy champion kills it (if it runs out, the one who "kills" it is itself)
                                "sweep": owner_of.get(killed_by) not in (None, owner_of.get(net)),
                                "reveals": collections.Counter()})

    def spot(champion, t):
        f = table[champion].get(int(t))
        return (float(f["x"]), float(f["z"])) if f and f["x"] and f["alive"] == "True" else None

    for t in range(int(since), int(until) + 1):
        alive = [w for w in placements if w["when"] <= t <= w["until"]]
        if not alive:
            continue
        for p in events["players"]:
            f = table[p["champion"]].get(t)
            if not f or f["seen"] != "True" or f["alive"] != "True" or not f["x"]:
                continue
            me, rival = (float(f["x"]), float(f["z"])), "200" if p["team"] == "100" else "100"
            if any((a := spot(o["champion"], t)) and math.dist(a, me) <= RANGE["champion"]
                   for o in events["players"] if o["team"] == rival):
                continue  # a champion of the team that is looking sees it: the information isn't the ward's
            near = [w for w in alive if w["team"] == rival
                     and math.dist(w["where"], me) <= RANGE["ward"]]
            if near:
                min(near, key=lambda w: math.dist(w["where"], me))["reveals"][p["champion"]] += 1

    base_departures = {}  # champion → seconds at which they just left their base
    for p in events["players"]:
        inside, leaves = True, []
        for t in sorted(table[p["champion"]]):
            q = spot(p["champion"], t)
            at_base = q is None or math.dist(q, bases[p["team"]]) < 2000
            if inside and not at_base:
                leaves.append(t)
            inside = at_base
        base_departures[p["champion"]] = leaves

    out = []
    for p in events["players"]:
        own_items = [w for w in placements if w["net_id"] == p["net_id"] and since <= w["when"] <= until]
        side = "blue" if p["team"] == "100" else "red"
        rival_team = "200" if p["team"] == "100" else "100"
        rival_jungler = junglers.get(rival_team)
        own_side = LANES.get(p["position"])
        detail = []
        for w in own_items:
            t = w["when"]
            deep = _depth(*w["where"], side)
            lane = _lane(*w["where"])
            advance = _advance(state, lane, t)
            prio = advance is not None and (
                (advance[0] - 0.5) * (1 if p["team"] == "100" else -1)) >= push
            own_entry = _advance(state, own_side, t) if own_side else None
            pushed = own_entry is not None and ((own_entry[0] - 0.5) * (1 if p["team"] == "100" else -1)) >= push
            moment = ("objective" if any(leaves - SETUP <= t <= falls_ and math.dist(w["where"], pit) <= OBJECTIVE_ZONE
                                         for leaves, falls_, pit in pits) else
                       "prio" if (pushed if own_side else prio) else
                       "reset" if any(0 <= t - s <= RESET for s in base_departures[p["champion"]]) else "loose")
            # the risk belongs to whoever places it, where they are: past the river, alone and not knowing where they are
            me = w["places_since"] if any(w["places_since"]) else w["where"]
            passed = _depth(*me, side) > 0.02
            alone = not any((a := spot(o["champion"], t)) and math.dist(a, me) <= 2000 for o in events["players"]
                           if o["team"] == p["team"] and o["champion"] != p["champion"])
            uncounted = sum(1 for o in events["players"] if o["team"] == rival_team
                             and (f := table[o["champion"]].get(int(t))) and f["alive"] == "True"
                             and ((v := sighted[o["champion"]].get(int(t))) is None
                                  or (t - v[0]) >= math.dist(v[1], me) / (_num(f, "move_speed") or 330.0)))
            in_fight = any(t - 5 <= g <= t for g in hits[p["net_id"]])
            in_sight = sum(1 for o in events["players"] if o["team"] == rival_team
                             and (f := table[o["champion"]].get(int(t))) and f["seen"] == "True"
                             and (a := spot(o["champion"], t)) and math.dist(a, me) <= 1500)
            detail.append({"when": t, "kind": w["kind"], "depth": deep,
                            "x": round(w["where"][0]), "z": round(w["where"][1]),
                            "lane": lane if _corridor(state, *w["where"]) else None,
                            # the frontier that matters is the enemy's, and that of that moment: beyond it
                            # nothing covers you, and when you take a turret from them it stretches
                            "past_the_lane": (sum(w["where"]) > line("200", lane, t)
                                                if p["team"] == "100"
                                                else sum(w["where"]) < line("100", lane, t)),
                            "lives": min(w["until"], until) - t, "with_prio": prio, "sweep": w["sweep"],
                            "moment": moment, "alone": alone, "uncounted": uncounted,
                            "in_fight": in_fight, "in_sight": in_sight, "passed": passed,
                            # with two enemies on you, having someone beside you is the difference between 9% and
                            # 14% of dying: the risk isn't only how many see you, it's how many see you alone
                            "risk": ("high" if in_sight >= 3 or (in_sight >= 2 and alone) else
                                       "mid" if in_sight >= 1 else "low"),
                            "costs_it": any(t < m <= t + 15 for m in deaths[p["net_id"]]),
                            "to_jungler": rival_jungler in w["reveals"],
                            "reveals": dict(w["reveals"]), "seconds": sum(w["reveals"].values())})
        unspent = []
        for t in recalls[p["net_id"]]:
            if not since <= t <= until or (unspent and t - unspent[-1] < 20):
                continue
            if not any(f["x"] and math.dist((float(f["x"]), float(f["z"])), bases[p["team"]]) < 2000
                       for f in _window(rows, p["champion"], t, t + 15)):
                continue  # recall cancelled
            full = any(_charges(per_item[(p["net_id"], item)], *charges, t) >= charges[0]
                        for item, charges in CHARGES.items() if per_item[(p["net_id"], item)])
            saved = (sum(c <= t for c in bought[p["net_id"]])
                        > sum(x <= t for x in per_item[(p["net_id"], "JammerDevice")]))
            if full or saved:
                unspent.append(t)
        out.append({"champion": p["champion"], "team": p["team"], "position": p["position"],
                      "wards": detail, "useful": sum(1 for d in detail if d["reveals"]),
                      "seconds_of_info": sum(d["seconds"] for d in detail),
                      "to_jungler": sum(1 for d in detail if rival_jungler in d["reveals"]),
                      "deepest_no_prio": [d for d in detail if d["past_the_lane"] and not d["with_prio"]],
                      "exempt": p["position"] == "UTILITY",  # see the prio rule in the docstring
                      "backs_with_charges": unspent})
    return out


SUPPORT_ITEM = {3866: 3, 3867: 4}  # the support item's charges: 3 on completing the first quest (Runic Compass) and 4
# with the second (Bounty of Worlds and what comes out of it). Measured in 120 matches of 16.19: between two visits to the
# shop nobody places more than 3 with the first nor more than 4 with the second; the first ward comes out before going back to base
# two out of three times (it brings them on transforming), and on going to the second without going to base none is recharged

SHOP_BASE = 1200.0  # within this of their fountain, they are at the shop


def support_item(events: dict, rows) -> list[dict]:
    """Each one's support item as the game carries it: how many ward charges they have left at each moment,
    and how long they walk the map with it empty.

    The charges don't come back with time: they are refilled **on passing through the shop**. A support without charges can't
    place vision until they go back to base, so the time they spend alive and out of base with the item empty is
    time in which their job can't be done: either they have spent well and it's time to go back, or they went back late. That is why
    it goes with the other half, `charges_wasted`: those they had left each time they went back to base on foot (a
    recall with unplaced wards is vision that isn't on the map, and in the shop they were going to be given them anyway).

    For each support: since when they have it (`since`), the seconds alive and out of base with it (`seconds`), those
    they carry it empty (`empty`, and `empty_share`; `spans_empty`, each stretch), the wards they place with it, the times
    they go back to base and the charges they had left then (`returns`), the control wards they place
    (`control_placed`) and the times they pass the sweep (`sweeps`). None in `since` if they never complete the quest.

    `control_bought` counts the control ward purchase events, which is what the official scoreboard counts
    (VISION_WARDS_BOUGHT_IN_GAME, spot on: 942 and 942 in 40 matches). **They come duplicated**: 96% come out in
    pairs at the same instant and the gold only drops once (75 g), so Riot's scoreboard also counts double.
    Counting distinct instants it matches the placed ones (bought = placed + 0-2 in 95% of players). The
    placed ones are exact —they are counted from the ward that is born, and match WARD_PLACED_DETECTOR— and are the ones used."""
    table, bases = _table(events, rows), _bases(rows)
    end = events["game_length"]
    out = []
    for p in events["players"]:
        if p["position"] != "UTILITY":
            continue
        net, c = p["net_id"], p["champion"]
        rise = sorted((e["time"], SUPPORT_ITEM[e["item_id"]]) for e in events["events"]
                      if e["type"] == "BuyItem" and e["net_id"] == net and e["item_id"] in SUPPORT_ITEM)
        places = sorted(e["time"] for e in events["events"]
                      if e["type"] == "CastSpell" and e["net_id"] == net and e["spell"] == "ItemGhostWard")
        control = [e["time"] for e in events["events"]
                   if e["type"] == "BuyItem" and e["net_id"] == net and e["item_id"] == CONTROL]
        pinks = [e["time"] for e in events["events"]
                 if e["type"] == "CastSpell" and e["net_id"] == net and e["spell"] == "JammerDevice"]
        sweeps = sum(1 for e in events["events"] if e["type"] == "CastSpell" and e["net_id"] == net
                       and e["spell"].startswith("TrinketSweeper"))
        row = {"champion": c, "team": p["team"], "since": round(rise[0][0], 1) if rise else None,
                "control_bought": len(control), "control_placed": len(pinks), "sweeps": sweeps,
                "wards": len(places), "seconds": 0, "empty": 0, "empty_share": None, "trips": 0,
                "charges_wasted": 0, "spans_empty": [], "returns": []}
        if rise:
            charges, cap, i, k, inside = 0, 0, 0, 0, True
            open_ = None
            for t in range(int(rise[0][0]), int(end) + 1):
                while k < len(rise) and rise[k][0] <= t:  # on transforming it brings its own; from 3 to 4, none more
                    charges, cap = (rise[k][1] if cap == 0 else charges), rise[k][1]
                    k += 1
                while i < len(places) and places[i] <= t:
                    charges, i = max(0, charges - 1), i + 1
                f = table[c].get(t)
                if not f or not f["x"]:
                    continue
                is_alive = f["alive"] == "True"
                at_base = is_alive and math.dist((float(f["x"]), float(f["z"])), bases[p["team"]]) < SHOP_BASE
                if at_base and not inside:
                    row["trips"] += 1
                    row["charges_wasted"] += charges
                    row["returns"].append([t, charges])
                if at_base or not is_alive:  # dead, they respawn at the fountain: they come out with full charges
                    charges, inside = cap, True
                else:
                    inside = False
                    row["seconds"] += 1
                    row["empty"] += charges == 0
                if is_alive and not at_base and charges == 0:
                    open_ = open_ or [t, t]
                    open_[1] = t
                elif open_:
                    row["spans_empty"].append(open_)
                    open_ = None
            if open_:
                row["spans_empty"].append(open_)
            row["empty_share"] = row["empty"] / row["seconds"] if row["seconds"] else None
        out.append(row)
    return out


def _spent(before, after) -> float | None:
    """Mana spent between the two rows, as a fraction of their maximum mana."""
    cap = _num(before, "mana_max") if before else None
    if not cap or not after:
        return None
    return max(0.0, ((_num(before, "mana") or 0) - (_num(after, "mana") or 0)) / cap)


def _health(row) -> float | None:
    """Health as a fraction, or None if that row doesn't carry it."""
    maximum = _num(row, "health_max") if row else None
    return (_num(row, "health") or 0) / maximum if maximum else None


def trades(events: dict, state: dict, rows, since: float = 120.0, until: float = 840.0,
            gap: float = 4.0, minimum: float = 0.05, after: float = 25.0) -> list[dict]:
    """Each exchange of blows in a lane, with the three things that decide whether it went well.

    A trade isn't judged by damage: it is judged by **what you spend, how you end up and what the wave does
    afterwards**. Hitting 400 by burning two spells and the flash, and being left with the wave coming down on top of you, is
    losing it even if the damage scoreboard says otherwise.

    The hits between the champions of the two teams that play that lane are grouped —in bot all four
    enter— cutting when more than `gap` seconds pass without hitting each other, and the one is kept that moves at least
    `minimum` of someone's maximum health, so a loose auto doesn't count as a trade.

    From each one comes, per side:

    - **what is spent**: abilities, summoner spells and mana, per champion;
    - **how it ends**: each one's health before and after, and who dies;
    - **the wave**: how much the lane's advance moves in the following `after` seconds, signed in
      favour of the blue team. A trade won that leaves the wave coming toward you isn't the same as one
      that leaves you pushing.

    Who won isn't decided: the three things go separately because which weighs more depends on the matchup and the
    moment, and that is among those the model learns."""
    champion_by_net = {p["net_id"]: p["champion"] for p in events["players"]}
    team_of = {p["champion"]: p["team"] for p in events["players"]}
    in_lane_ = collections.defaultdict(list)
    for p in events["players"]:
        if p["position"] in LANES:
            in_lane_[LANES[p["position"]]].append(p["champion"])

    hits = collections.defaultdict(list)
    casts, deaths = collections.defaultdict(list), collections.defaultdict(list)
    for e in events["events"]:
        if e["type"] == "Damage" and e.get("source") in champion_by_net and e["net_id"] in champion_by_net:
            who, suffers = champion_by_net[e["source"]], champion_by_net[e["net_id"]]
            if team_of[who] != team_of[suffers]:
                for lane, own_items in in_lane_.items():
                    if who in own_items and suffers in own_items:
                        hits[lane].append((e["time"], who, suffers, e["amount"]))
        elif e["type"] == "CastSpell" and e["net_id"] in champion_by_net and e["slot"] <= 5:
            casts[champion_by_net[e["net_id"]]].append((e["time"], e["slot"], e["spell"]))
        elif e["type"] == "Death" and e["net_id"] in champion_by_net:
            deaths[champion_by_net[e["net_id"]]].append(e["time"])
    table = {p["champion"]: {int(float(f["time"])): f for f in rows.get(p["champion"], [])}
             for p in events["players"]}

    out = []
    for lane, own_items in hits.items():
        ordered = sorted(own_items)
        for streak in _rafagas([(t, i) for i, (t, *_r) in enumerate(ordered)], gap):
            chunk = [ordered[i] for _t, i in streak]
            t0, t1 = chunk[0][0], chunk[-1][0]
            if not since <= t0 <= until:
                continue
            damage, taken = collections.Counter(), collections.Counter()
            for _t, who, suffers, how_much in chunk:
                damage[who] += how_much
                taken[suffers] += how_much
            caps = {c: max((_num(table[c].get(t), "health_max") or 0) for t in (int(t0), int(t1))) or 1
                     for c in in_lane_[lane]}
            if max(taken[c] / caps[c] for c in taken) < minimum:
                continue  # a loose auto isn't a trade: someone has to lose some health
            sides = {}
            for team in ("100", "200"):
                own_rows = [c for c in in_lane_[lane] if team_of[c] == team]
                sides[team] = {
                    "damage": sum(damage[c] for c in own_rows),
                    "champions": {c: {
                        "damage": damage[c],
                        "health_before": _health(table[c].get(int(t0) - 1)),
                        "health_after": _health(table[c].get(int(t1) + 3)),
                        "mana": _spent(table[c].get(int(t0) - 1), table[c].get(int(t1) + 3)),
                        "abilities": sum(1 for t, s, _n in casts[c] if t0 - 1 <= t <= t1 and s <= 3),
                        "summoners": [SUMMONERS.get(n.lower(), n) for t, s, n in casts[c]
                                        if t0 - 1 <= t <= t1 and s in (4, 5) and n.lower().startswith("summoner")],
                    } for c in own_rows},
                    "died": [c for c in own_rows if any(t1 - 2 <= t <= t1 + 4 for t in deaths[c])]}
            before, then = _advance(state, lane, t1), _advance(state, lane, t1 + after)
            out.append({"lane": lane, "since": t0, "until": t1, "starts": chunk[0][1],
                          "sides": sides,
                          "wave": (then[0] - before[0]) if before and then else None})
    return sorted(out, key=lambda x: x["since"])


def _spot_at_death(events: dict, minions: dict) -> dict[str, tuple[float, float]]:
    """Where each minion dies. The `UnitDeath` only carries the position when a champion kills it: if another
    minion or a turret kills it, it arrives at (0, 0) two times out of three. For those it is taken from its last path, what it has walked at
    its speed since it started (it stays at the end if it already arrived: that is where it fights).

    ponytail: against those that do carry the position, the median error is 233 units (p90 575), because the
    minions push each other and their path changes at every step. To refine, the killer's `MinionAttack`
    carries the exact position of whoever hits."""
    last_ = {}
    for e in events["events"]:
        if e["type"].startswith("WaypointGroup"):
            for u in e["units"]:
                if (d := minions.get(u["net_id"])) and e["time"] <= d["died"]:
                    last_[u["net_id"]] = (e["time"], u["speed"], u["path"])
    out = {}
    for sub, d in minions.items():
        if d["where"]:
            out[sub] = tuple(d["where"])
        elif sub in last_:
            t0, speed, path = last_[sub]
            remaining, (x, z) = speed * (d["died"] - t0), path[0]
            for nx, nz in path[1:]:
                stretch = math.dist((x, z), (nx, nz))
                if remaining <= stretch:
                    x, z = (x + remaining / stretch * (nx - x), z + remaining / stretch * (nz - z)) if stretch else (x, z)
                    break
                remaining -= stretch
                x, z = nx, nz
            out[sub] = (x, z)
    return out


def finishes(events: dict, state: dict, rows, until: float = 840.0, reach: float = 700.0) -> list[dict]:
    """The minions of their lane that each laner takes and those that escape them up to minute 14.

    Escaping them (`missed`) is the enemy minion of their lane that dies with them alive within `reach` without them
    collecting its gold, whoever kills it: they were there and didn't farm it. What dies with them far away, dead or in base
    doesn't count; that is the lost wave, not the last hit. The bottom lane's belongs to the marksman: the support doesn't
    farm. With the support item the gold goes to both, so that one doesn't escape the marksman."""
    lane_of = {"TOP": "top", "MIDDLE": "mid", "BOTTOM": "bot"}
    spot = _spot_at_death(events, state["minions"])
    collect = collections.defaultdict(set)
    for c in events["creeps"]:
        if c["character"] == "LaneMinion":
            collect[c["unit"]].add(c["net_id"])
    out = []
    for p in events["players"]:
        if (lane := lane_of.get(p["position"])) is None:
            continue
        rival = "red" if p["team"] == "100" else "blue"
        where = {int(float(f["time"])): f for f in rows.get(p["champion"], [])}
        hit = missed = 0
        for sub, d in state["minions"].items():
            if d["lane"] != lane or d["side"] != rival or d["died"] > until:
                continue
            if p["net_id"] in collect[sub]:
                hit += 1
            elif sub in spot and (f := where.get(int(d["died"]))) and f["alive"] == "True" and f["x"] and \
                    math.dist((float(f["x"]), float(f["z"])), spot[sub]) <= reach:
                missed += 1
        out.append({"champion": p["champion"], "hits": hit, "missed": missed,
                      "hit_rate": hit / (hit + missed) if hit + missed else None})
    return out


def api_events(timeline: dict | None) -> list[dict]:
    """The Riot timeline's events, whether they come as they come from the file (`info.frames[].events`) or already trimmed
    by `wp_per_second.records` (`events` in one go, which is what the replay analysis receives)."""
    if not timeline:
        return []
    if timeline.get("events") is not None:
        return timeline["events"]
    return [e for f in timeline.get("info", {}).get("frames", []) for e in f["events"]]


def plates(events: dict, timeline: dict | None, until: float = 840.0) -> list[dict]:
    """Each plate that falls before `until`, from the timeline's `TURRET_PLATE_DESTROYED`: when, from which turret and
    who takes it.

    A plate is 160 gold shared among those beside it, so it is the cheapest gold of the laning phase and the one most
    noticed: measured in 10,276 matches of the harvest, each plate of difference in a lane before 14
    is worth 6.5 winrate points in mid, 6.0 in bot and 4.6 in top (from -5 to +5, mid goes from 17.5%
    to 82.5% and top only from 27.1% to 72.9%).

    The three turrets of a lane carry plates (up to 15 per lane, with events up to minute 45), but before
    14 96% of lanes have only one turret touched, the outer, so trimming by time yields
    the tier 1 ones without looking at the position.

    `champion_by_net` is `None` in 34% of them: those finished by a minion (`killerId` 0). The gold is shared the same
    among those nearby, so for the lane the plate counts, not who landed the last hit."""
    order = [p["champion"] for p in events["players"]]
    team = {p["champion"]: p["team"] for p in events["players"]}
    out = []
    for e in api_events(timeline):
        if e.get("type") != "TURRET_PLATE_DESTROYED" or e["timestamp"] / 1000 > until:
            continue
        who = order[e["killerId"] - 1] if e["killerId"] else None
        assert who is None or team[who] != str(e["teamId"]), who  # nobody takes down their own turret's plate
        out.append({"time": round(e["timestamp"] / 1000, 1), "team": str(e["teamId"]),
                      "lane": LANE_TL.get(e.get("laneType"), ""), "champion": who,
                      "x": e["position"]["x"], "z": e["position"]["y"]})
    return out


def gold_in_lane(events: dict, rows, timeline: dict | None = None, until: float = 840.0) -> list[dict]:
    """The gold each laner gets from their lane: minions and plates, against their direct opponent.

    The CS comes from the state table, which matches the timeline exactly. The plates come from
    `TURRET_PLATE_DESTROYED`, which carries who takes it, and the total gold from the table itself.

    `plates` are those they take down; `plates_lane` and `plates_against`, those of the two outer turrets of their
    lane, whoever's: a plate's gold is shared among those beside it and 34% are finished by a
    minion, so to measure the lane all count (`plates`, see there what each is worth)."""
    position = {p["champion"]: p["position"] for p in events["players"]}
    team = {p["champion"]: p["team"] for p in events["players"]}
    rival_of = {a: b for a in position for b in position
                if a != b and position[a] == position[b] and team[a] != team[b]}
    order = [p["champion"] for p in events["players"]]
    other = {"100": "200", "200": "100"}
    own_rows, from_lane = collections.Counter(), collections.Counter()
    for p in plates(events, timeline, until):
        if p["champion"]:
            own_rows[p["champion"]] += 1
        from_lane[(p["team"], p["lane"])] += 1  # those of the lane, whoever takes them down: the gold is shared
    out = []
    for champion in order:
        if position.get(champion) not in LANES:
            continue
        row = next((f for f in reversed(rows.get(champion, [])) if float(f["time"]) <= until), None)
        out.append({"champion": champion, "lane": LANES[position[champion]], "team": team[champion],
                      "rival": rival_of.get(champion), "cs": int(_num(row, "cs") or 0) if row else 0,
                      "plates": own_rows[champion], "gold": round(_num(row, "total_gold") or 0) if row else 0,
                      # those of their lane: the gold that really comes in or goes out of there (34% are taken down by minions)
                      "plates_lane": from_lane[(other[team[champion]], LANES[position[champion]])],
                      "plates_against": from_lane[(team[champion], LANES[position[champion]])]})
    return out


def _out_of_lane(state: dict, lane: str, x: float, z: float, cells: int = 3) -> bool:
    """Not in their lane nor within `cells` cells of it (about 750 units).

    With the corridor and not the map zone: the zone would say the top is still in top when they are in the river
    or in the upper jungle, which is exactly where they go when they leave."""
    cx, cz = int(x // CELL), int(z // CELL)
    return not any(lane in state["corridors"].get((cx + i, cz + j), ())
                   for i in range(-cells, cells + 1) for j in range(-cells, cells + 1))


def departures(events: dict, state: dict, rows, since: float = 120.0, until: float = 840.0,
            minimum: float = 10.0, stuck: float = 4.0, near: float = 1500.0, drag: float = 8.0,
            horizon: float = 30.0, push: float = 0.02) -> list[dict]:
    """Each time a laner leaves their lane: whether they had it won, what they get and what it costs them.

    It is where the advantage you get in lane is carried to the rest of the map, and it changes with the position: the mid
    enables the jungler, the support goes to impact mid or to accompany a play, and the top converts their individual
    advantage into help for the jungler or for the mid. None of those three rules is encoded here:
    **where they go, whom they join and what comes out of it** are noted, and the model learns which
    works for each position.

    From each departure comes:

    - **whether they had it won**: the advance of their own wave in the twenty seconds before leaving, which
      is what distinguishes the gap you build by pushing from a leak. Leaving with the wave coming
      down on you is paid for in CS;
    - **whom they join**: the allies within `near`. That is where it shows whether the mid leaves
      with the jungler or the support goes to mid;
    - **what they get**: an enemy burning a summoner, a kill they hit in, a camp or objective, a
      deep ward, or the pressure of showing themselves: the enemy laner they have in range retreating or going back to base and
      that lane pushing in their favour (`_pressured`: only counts within PRESSURE, which is as far as it is felt).
      It is the breathing room a support gives their mid when they appear there;
    - **what it costs**: the minions that escape them in their own lane while they are away and in the following
      `horizon` seconds.

    The cost goes per team in that lane, which is how `_cs_lost` counts it: in bot, if the support leaves and
    the marksman stays, the CS lost isn't the support's."""
    champion_by_net = {p["net_id"]: p["champion"] for p in events["players"]}
    net_of = {p["champion"]: p["net_id"] for p in events["players"]}
    team_of = {p["champion"]: p["team"] for p in events["players"]}
    owner_of = {p["net_id"]: p["team"] for p in events["players"]}
    summoners, deaths, recalls = collections.defaultdict(list), [], collections.defaultdict(list)
    hit_damage, placements = collections.defaultdict(list), collections.defaultdict(list)
    for e in events["events"]:
        if e["type"] == "Damage" and e.get("source") in champion_by_net and e["net_id"] in champion_by_net:
            hit_damage[(champion_by_net[e["source"]], champion_by_net[e["net_id"]])].append(e["time"])
        elif e["type"] == "CastSpell" and e["net_id"] in champion_by_net and e["slot"] in (4, 5) and _gets_burned(e["spell"]):
            summoners[champion_by_net[e["net_id"]]].append((e["time"], e["spell"]))
        elif e["type"] == "CastSpell" and e["spell"] in WARDS:
            placements[e["net_id"]].append((e["time"], tuple(e["target"])))
        elif e["type"] == "Death" and e["net_id"] in champion_by_net:
            deaths.append((e["time"], champion_by_net[e["net_id"]]))
        elif e["type"] == "AddBuff" and e["buff"].lower() == "recall" and e["net_id"] in champion_by_net:
            recalls[champion_by_net[e["net_id"]]].append(e["time"])
    table = {p["champion"]: {int(float(f["time"])): f for f in rows.get(p["champion"], [])}
             for p in events["players"]}
    bases = _bases(rows)

    def where(champion: str, t: float) -> tuple[float, float] | None:
        f = table[champion].get(int(t))
        return (float(f["x"]), float(f["z"])) if f and f["x"] and f["alive"] == "True" else None

    out = []
    for p in events["players"]:
        if p["position"] not in LANES:
            continue
        champion, lane, team = p["champion"], LANES[p["position"]], p["team"]
        side = "blue" if team == "100" else "red"
        rival_team = "200" if team == "100" else "100"
        windows, open_, last_ = [], None, None
        for t in range(int(since), int(until) + 1):
            me = where(champion, t)
            if not me or math.dist(me, bases[team]) < 2000 or not _out_of_lane(state, lane, *me):
                continue
            if open_ and t - last_ <= stuck:
                open_[1] = t
            else:
                if open_:
                    windows.append(open_)
                open_ = [t, t]
            last_ = t
        if open_:
            windows.append(open_)

        for a, b in (v for v in windows if v[1] - v[0] + 1 >= minimum):
            me = where(champion, (a + b) // 2) or where(champion, a)
            zone = _lane(*me) if me else None
            corridor = _corridor(state, *me) if me else None
            where_to = f"lane {corridor}" if corridor else f"river/jungle {zone}"
            # they had it won if they came from pushing, not only if the wave is out right as they leave
            own_entry = [_advance(state, lane, a - k) for k in (0, 5, 10, 15, 20)]
            won = max(((x[0] - 0.5) * (1 if side == "blue" else -1)) for x in own_entry if x) >= push                 if any(own_entry) else False
            together = sorted({o["champion"] for o in events["players"] if o["team"] == team
                             and o["champion"] != champion
                             for t in range(a, b + 1, 2)
                             if (q := where(o["champion"], t)) and (r := where(champion, t))
                             and math.dist(q, r) <= near})
            wins = []
            burned = {s for other, own_rows in summoners.items() if team_of[other] == rival_team
                        for t, s in own_rows if a <= t <= b + drag
                        and (q := where(other, t)) and (r := where(champion, t)) and math.dist(q, r) <= near}
            if burned:
                wins.append("burns " + ", ".join(sorted(SUMMONERS.get(s.lower(), s) for s in burned)))
            falls_ = sorted({c for t, c in deaths if a <= t <= b + drag and team_of.get(c) == rival_team
                          and any(t - drag <= x <= t for x in hit_damage[(champion, c)])})
            if falls_:
                wins.append("kills " + ", ".join(falls_))
            camps = sorted({c["camp"] for c in events["camps"] if a <= c["time"] <= b + drag
                            and c["killer"] in owner_of and owner_of[c["killer"]] == team
                            and (q := where(champion_by_net[c["killer"]], c["time"])) and me
                            and math.dist(q, me) <= 2 * near})
            if camps:
                wins.append("falls " + ", ".join(camps))
            deepest = [_depth(*w, side) for t, w in placements[net_of[champion]] if a <= t <= b + drag]
            if deepest and max(deepest) > 0:
                wins.append(f"ward at {max(deepest):+.0%} from the river")
            # whom they pressure by showing themselves: the enemy laners of the other lanes who have them in range
            presses = _pressured(table, state, champion,
                                    [r for r in events["players"] if r["team"] == rival_team
                                     and r["position"] in LANES and LANES[r["position"]] != lane],
                                    recalls, a, b, drag)
            for other in dict.fromkeys(c for _r, c, _h in presses):
                before, then = _advance(state, other, a), _advance(state, other, b + drag + 12)
                if before and then and (then[0] - before[0]) * (1 if side == "blue" else -1) >= PUSHES:
                    wins.append(f"the wave of {other} advances in their favour")
            wins += [f"{rival} {does}" for rival, _c, does in presses if does]
            _fall, lost = _cs_lost(state, lane, team, a, b + horizon, owner_of)
            # leaving for another lane and farming its wave recovers what is lost in their own (in the laning phase, the gold
            # of the wave left behind is the price of the one taken): if at least what is left is taken, something is gained
            collected = sum(1 for x in state["minions"].values() if x["lane"] != lane and x["farm"] == net_of[champion]
                           and a <= x["died"] <= b + drag)
            covered = [o["champion"] for o in events["players"] if o["team"] == team and o["champion"] != champion
                        and o["position"] != "UTILITY" and sum(bool((q := where(o["champion"], t)) and _lane(*q) == lane)
                                                                for t in range(a, b + 1, 2)) >= (b - a) / 4]
            if covered:  # a teammate is at the wave while they aren't: what is lost is theirs, not of whoever left
                lost = 0
            if collected >= max(3, lost):
                wins.append(f"farms {collected} minions in another lane")
            out.append({"champion": champion, "position": p["position"], "lane": lane, "team": team,
                          "since": a, "until": b, "where_to": where_to, "zone": zone, "won": won,
                          "together": together, "presses": [r for r, _c, _h in presses],
                          "wins": wins, "cs_lost": lost, "covered": bool(covered)})
    return sorted(out, key=lambda x: x["since"])


SUMMONER_ID = {1: "Cleanse", 3: "Exhaust", 4: "Flash", 6: "Ghost", 7: "Heal", 11: "Smite",
                12: "TP", 14: "Ignite", 21: "Barrier", 32: "Snowball"}


def _last_seen(rows, champion: str, until: float) -> dict[int, tuple[int, tuple[float, float]]]:
    """For each second, when and where they were last seen. None while they haven't been seen."""
    out, sighted = {}, None
    table = {int(float(f["time"])): f for f in rows.get(champion, [])}
    for t in range(int(until) + 1):
        f = table.get(t)
        if f and f["seen"] == "True" and f["alive"] == "True" and f["x"]:
            sighted = (t, (float(f["x"]), float(f["z"])))
        out[t] = sighted
    return out


def sidelanes(events: dict, state: dict, rows, match: dict | None = None, since: float = 840.0,
              minimum: float = 20.0, stuck: float = 5.0, teammate: float = 2500.0,
              base: float = 2500.0, drag: float = 15.0) -> list[dict]:
    """The sidelaner's job from minute 14: pushing the side lane whenever possible without dying.

    Pushing a side lane forces the enemy to go and pick it up, and meanwhile your team plays with one more
    around the objective. The limit isn't how much you can push, it is how much you can push **without dying**,
    and that depends on the information you have and the tools you have left to get out.

    A side-lane turn is a stretch **alone** in the top or bot corridor: without any teammate within
    `teammate` and outside their base. That separates the sidelaner without looking at their position, and in the two matches
    read the sidelaners turn out to be the top and the mid: the marksman and the support are almost never alone
    in a side lane.

    From each turn comes:

    - **how much they push**: how much the lane's advance moves in their favour;
    - **whether they crash the wave** into the enemy turret, which is what really forces a response;
    - **with how much information**: how many enemies could be on top of them without their knowing, with the same
      count as `exposure` —since they last saw them, have they had time to arrive?— applied to
      all five. Zero is pushing with the map under control; four or five is pushing blind;
    - **what tools they have**: the ultimate ready and Teleport ready. They are what turn pushing
      far away into a decision and not a gamble;
    - **whether the enemy responds**: someone from the other team enters that lane;
    - **what it costs them**: the minions they take, and whether they die there.

    It isn't judged: giving up CS to impact the map is right even if suboptimal, and pushing blind with
    the ultimate and Teleport ready isn't the same as pushing blind with nothing. The data go separately."""
    team_of = {p["champion"]: p["team"] for p in events["players"]}
    champion_by_net = {p["net_id"]: p["champion"] for p in events["players"]}
    order = [p["champion"] for p in events["players"]]
    end = min(events["game_length"], max(float(f["time"]) for theirs in rows.values() for f in theirs))
    bases = _bases(rows)
    table = {c: {int(float(f["time"])): f for f in theirs} for c, theirs in rows.items()}
    sighted = {c: _last_seen(rows, c, end) for c in order}
    deaths = collections.defaultdict(list)
    for e in events["events"]:
        if e["type"] == "Death" and e["net_id"] in champion_by_net:
            deaths[champion_by_net[e["net_id"]]].append(e["time"])

    gap = {}  # champion → slot of the state table where they carry Teleport
    for p, player in zip(order, (match or {}).get("info", {}).get("participants", [])):
        for slot, ident in (("d", player.get("summoner1Id")), ("f", player.get("summoner2Id"))):
            if SUMMONER_ID.get(ident) == "TP":
                gap[p] = slot

    turrets = {e["net_id"] for e in events["events"]
                if e["type"] == "SetSpell" and "Turret" in (e.get("name") or "")}
    finish = collections.defaultdict(list)  # (lane, side) → seconds at which the enemy turret finishes
    for e in events["events"]:
        s = state["minions"].get(e["net_id"]) if e["type"] == "UnitDeath" else None
        if s and e["killer"] in turrets:
            finish[(s["lane"], s["side"])].append(s["died"])

    def spot(champion, t):
        f = table[champion].get(int(t))
        return (float(f["x"]), float(f["z"])) if f and f["x"] and f["alive"] == "True" else None

    out = []
    for champion in order:
        team = team_of[champion]
        side = "blue" if team == "100" else "red"
        rivals = [c for c in order if team_of[c] != team]
        windows, open_, last_ = [], None, None
        for t in range(int(since), int(end)):
            me = spot(champion, t)
            lane = _corridor(state, *me) if me else None
            if (not me or lane not in ("top", "bot") or math.dist(me, bases[team]) < base
                    or any((q := spot(o, t)) and math.dist(q, me) < teammate
                           for o in order if team_of[o] == team and o != champion)):
                continue
            if open_ and t - last_ <= stuck and open_[2] == lane:
                open_[1] = t
            else:
                if open_:
                    windows.append(open_)
                open_ = [t, t, lane]
            last_ = t
        if open_:
            windows.append(open_)

        for a, b, lane in (v for v in windows if v[1] - v[0] + 1 >= minimum):
            before, then = _advance(state, lane, a), _advance(state, lane, b)
            push = (then[0] - before[0]) * (1 if side == "blue" else -1) if before and then else None
            clash = sum(1 for t in finish[(lane, side)] if a <= t <= b + drag)
            blind = []
            for t in range(a, b + 1, 5):
                me = spot(champion, t)
                if not me:
                    continue
                blind.append(sum(1 for r in rivals
                                  if not sighted[r][t] or (t - sighted[r][t][0]) >=
                                  math.dist(sighted[r][t][1], me) / (_num(table[r].get(t), "move_speed") or 330)))
            f0 = table[champion].get(a)
            answers = sorted({r for r in rivals for t in range(a, int(b + drag), 3)
                               if (q := spot(r, t)) and _corridor(state, *q) == lane})
            out.append({
                "champion": champion, "team": team, "lane": lane, "since": a, "until": b,
                "push": push, "clash": clash,
                "uncounted": statistics.median(blind) if blind else None,
                "ulti": f0["r_ready"] == "True" if f0 else None,
                "tp": (table[champion].get(a, {}).get(f"{gap[champion]}_ready") == "True"
                       if champion in gap else None),
                "answers": answers,
                "cs": int((_num(table[champion].get(b), "cs") or 0) - (_num(table[champion].get(a), "cs") or 0)),
                "died": any(a <= t <= b + 3 for t in deaths[champion])})
    return sorted(out, key=lambda x: x["since"])


def cost_of_dying(events: dict, rows, since: float = 840.0) -> list[dict]:
    """What each death really costs, which isn't the same depending on the position.

    The marksman is the role for whom dying weighs most because their job is the two things that death cuts at
    once: gathering resources and dealing damage. For the support it weighs much less, and not only because they respawn sooner
    —the respawn time rises with level and goes behind—: the vision they placed stays placed while
    they are dead, and the ward item recovers charges in there, so they come out again with vision.

    It is measured without assuming any of that: for each player, the seconds they spend dead (the respawn
    time is carried by the `Death` packet itself, with the game's rules applied), what they produce per
    living second —gold and damage to champions— and therefore what they stop producing. And the ward charges they
    recover while dead, which is what makes the support's death cheaper."""
    champion_by_net = {p["net_id"]: p["champion"] for p in events["players"]}
    end = min(events["game_length"], max(float(f["time"]) for theirs in rows.values() for f in theirs))
    deaths = collections.defaultdict(list)
    damage = collections.Counter()
    per_item = collections.defaultdict(list)
    for e in events["events"]:
        if e["type"] == "Death" and e["net_id"] in champion_by_net and since <= e["time"] <= end:
            deaths[champion_by_net[e["net_id"]]].append((e["time"], e["respawn_time"]))
        elif e["type"] == "Damage" and e.get("source") in champion_by_net and e["net_id"] in champion_by_net \
                and since <= e["time"] <= end:
            damage[champion_by_net[e["source"]]] += e["amount"]
        elif e["type"] == "CastSpell" and e["spell"] in WARDS:
            per_item[(e["net_id"], e["spell"])].append(e["time"])

    out = []
    for p in events["players"]:
        champion = p["champion"]
        stretch = [f for f in rows.get(champion, []) if since <= float(f["time"]) <= end]
        if not stretch:
            continue
        is_alive = sum(1 for f in stretch if f["alive"] == "True")
        gold = (_num(stretch[-1], "total_gold") or 0) - (_num(stretch[0], "total_gold") or 0)
        dead = sum(r for _t, r in deaths[champion])
        recovers = 0.0
        for t, r in deaths[champion]:
            for item, charges in CHARGES.items():
                if per_item[(p["net_id"], item)]:
                    recovers += (_charges(per_item[(p["net_id"], item)], *charges, t + r)
                                 - _charges(per_item[(p["net_id"], item)], *charges, t))
        out.append({"champion": champion, "position": p["position"], "team": p["team"],
                      "deaths": len(deaths[champion]), "seconds_dead": round(dead),
                      "respawn_mean": round(dead / len(deaths[champion]), 1) if deaths[champion] else 0,
                      "gold_per_second": gold / is_alive if is_alive else 0,
                      "damage_per_second": damage[champion] / is_alive if is_alive else 0,
                      "gold_lost": round(dead * gold / is_alive) if is_alive else 0,
                      "damage_lost": round(dead * damage[champion] / is_alive) if is_alive else 0,
                      "charges_recovered": round(recovers, 1)})
    return out


def overgroup(events: dict, state: dict, rows, timeline: dict | None = None, since: float = 840.0,
              grouped: int = 3, radius: float = 2500.0, picks_up: float = 1500.0,
              stuck: float = 20.0) -> list[dict]:
    """Minions lost on their own under a side-lane turret with the whole team grouped elsewhere.

    It is the over-grouping mistake: all five together around the objective while a side wave
    crashes into their own turret and dies by itself. That CS isn't lost by anyone in particular and so it
    appears in no statistic, but it is gold given away and is paid for in full.

    To mark it, three things must hold at once:

    - **their own turret eats it**, which asks for no geometry —the turret that finishes a minion is
      always that of the team that was meant to eat it— or, if enemy minions kill it, it dies behind
      their turret line (`_tower_line`, which moves when turrets fall);
    - **nobody collects it** from that team, and nobody of theirs is within `picks_up` to collect it;
    - **`grouped` or more of them are within `radius` of each other**, which is what turns "it escaped us" into
      "we were all together elsewhere".

    The gold is estimated with the median of what minions of that same period pay, since the `Gold` packet
    carries the amount. It is a lower estimate: cannons are worth quite a bit more than the median."""
    owner_of = {p["net_id"]: p["team"] for p in events["players"]}
    line = _tower_line(events, state, timeline)
    table = {p["champion"]: {int(float(f["time"])): f for f in rows.get(p["champion"], [])}
             for p in events["players"]}
    own_items = collections.defaultdict(list)
    for p in events["players"]:
        own_items[p["team"]].append(p["champion"])
    collected_ = sorted((e["time"], e["amount"]) for e in events["events"]
                     if e["type"] == "Gold" and e["amount"] > 10)
    turrets = {e["net_id"] for e in events["events"]
                if e["type"] == "SetSpell" and "Turret" in (e.get("name") or "")}

    def spot(champion, t):
        f = table[champion].get(int(t))
        return (float(f["x"]), float(f["z"])) if f and f["x"] and f["alive"] == "True" else None

    def price(t):
        near = [a for x, a in collected_ if abs(x - t) <= 60]
        return statistics.median(near) if near else 20.0

    lost = collections.defaultdict(list)
    for s in state["minions"].values():
        if s["lane"] not in ("top", "bot") or not s["where"] or s["died"] < since:
            continue
        victim = "200" if s["side"] == "blue" else "100"
        if owner_of.get(s["farm"]) == victim:
            continue
        # that their own turret eats it is exact and asks for no geometry: the turret that finishes a minion
        # is always that of the team that was meant to eat it. The rest, behind their turret line.
        border = line(victim, s["lane"], s["died"])
        behind = sum(s["where"]) < border if victim == "100" else sum(s["where"]) > border
        if s["killed_by"] not in turrets and not behind:
            continue
        alive = {c: q for c in own_items[victim] if (q := spot(c, s["died"]))}
        if any(math.dist(q, s["where"]) <= picks_up for q in alive.values()):
            continue
        cluster = max((sum(1 for r in alive.values() if math.dist(q, r) <= radius) for q in alive.values()),
                   default=0)
        if cluster < grouped:
            continue
        lost[(s["lane"], victim)].append((s["died"], cluster, s["where"]))

    out = []
    for (lane, team), own_rows in lost.items():
        ordered_ = sorted(own_rows)
        for streak in _rafagas([(t, i) for i, (t, *_r) in enumerate(ordered_)], stuck):
            chunk = [ordered_[i] for _t, i in streak]
            t0, t1 = chunk[0][0], chunk[-1][0]
            out.append({"lane": lane, "team": team, "since": t0, "until": t1,
                          "minions": len(chunk), "together": max(p for _t, p, _d in chunk),
                          "gold": round(len(chunk) * price(t0))})
    return sorted(out, key=lambda x: x["since"])


def _minion_price(events: dict) -> collections.abc.Callable[[float], float]:
    """What a minion is worth at each moment: the median of what is collected around it.

    The `Gold` packet carries the amount, but two arrive for a minion —the last hit's and a small extra—,
    so those under ten are ignored. For the ones that are lost there is no event, by definition: nobody
    collected. It is a lower estimate, because cannons are worth quite a bit more than the median."""
    collected_ = sorted((e["time"], e["amount"]) for e in events["events"]
                     if e["type"] == "Gold" and e["amount"] > 10)

    def price(t: float, window: float = 60.0) -> float:
        near = [a for x, a in collected_ if abs(x - t) <= window]
        return statistics.median(near) if near else 20.0

    return price


def side_balance(events: dict, state: dict, since: float = 840.0, share: float = 0.5,
                    minimum: int = 3, step: float = 10.0) -> list[dict]:
    """The side lane as a global computation: what it costs to abandon it until someone goes to fix it.

    Losing a wave under tower isn't a loose event. While nobody goes, **they keep being lost**:
    the turret eats the wave, the own minions survive and pile up, and the next one dies
    the same. What has to be measured isn't the wave, it is the **whole episode**, from the first one
    left until the sidelaner appears and picks it up.

    An episode is a run of `minimum` consecutive waves in which a team collects less than `share` of
    the minions it was due in that lane. From each one comes:

    - **what it loses**: minions it was due and didn't collect, and their gold;
    - **what the enemy collects** in that same lane and those same waves, which is the other half of the ledger;
    - **the balance** between the two, which is the advantage that opens in that lane;
    - **what it recovers** in the wave that closes the episode;
    - **the rebound**: how much their own wave manages to pile up while nobody goes. It is what separates the
      two possible endings. If the turret holds, the own minions survive, the wave piles up and the
      sidelaner who appears finds a fat wave to crash: the episode comes out expensive but opens
      an advantage in that lane. If it doesn't pile up, the enemy is entering every wave and the episode is
      just bleeding.

    The wave number comes from `lane_waves`, which groups them by the real departure: dividing the clock by 30
    drifted by twelve waves at minute 35, exactly in the stretch this measures."""
    owner_of = {p["net_id"]: p["team"] for p in events["players"]}
    price = _minion_price(events)
    ledger = collections.defaultdict(lambda: {"dead": 0, "earns": collections.Counter(),
                                             "when": [], "advances": []})
    for s in state["minions"].values():
        if s["lane"] not in ("top", "bot") or s["died"] == float("inf") or s["died"] < since:
            continue
        r = ledger[(s["lane"], s["side"], s["wave"])]
        r["dead"] += 1
        r["earns"][owner_of.get(s["farm"])] += 1
        r["when"].append(s["died"])
        if s["advance"] is not None:
            r["advances"].append(s["advance"])

    out = []
    for lane in ("top", "bot"):
        for team, rival in (("100", "red"), ("200", "blue")):
            other = "200" if team == "100" else "100"
            own_rows = sorted(n for (c, l, n) in ledger if c == lane and l == rival)
            opened = []
            for n in own_rows + [None]:
                r = ledger.get((lane, rival, n)) if n is not None else None
                leaves = r is not None and r["earns"][team] < share * r["dead"]
                if leaves:
                    opened.append(n)
                    continue
                if len(opened) >= minimum:
                    waves = list(opened)
                    chunks = [ledger[(lane, rival, k)] for k in waves]
                    t0 = min(min(x["when"]) for x in chunks)
                    t1 = max(max(x["when"]) for x in chunks)
                    lost = sum(x["dead"] - x["earns"][team] for x in chunks)
                    mine_total = sum(x["earns"][team] for x in chunks)
                    # the other half of the ledger: what the enemy collects of this team's minions
                    own_items = [ledger[(lane, "blue" if team == "100" else "red", k)]
                             for k in waves if (lane, "blue" if team == "100" else "red", k) in ledger]
                    other_collects = sum(x["earns"][other] for x in own_items)
                    recovers = r["earns"][team] if r else 0
                    # the rebound: while nobody goes, the turret defends and the own minions survive.
                    # If the own wave piles up, the episode ends in a fat wave to pick up; if
                    # it doesn't pile up, it is just bleeding
                    mine = "blue" if team == "100" else "red"
                    own = "red" if team == "100" else "blue"
                    piles = max((_alive(state, lane, mine, t) - _alive(state, lane, own, t)
                                   for t in (t0 + step * k for k in range(int((t1 - t0) / step) + 1))),
                                  default=0)
                    out.append({
                        "lane": lane, "team": team, "waves": (waves[0], waves[-1]),
                        "since": t0, "until": t1, "lost": lost, "collected": mine_total,
                        "gold_lost": round(lost * price(t0)),
                        "rival_collects": other_collects,
                        "balance": round((mine_total - other_collects) * price(t0)),
                        "recovers": recovers, "closes": n, "piles": piles,
                        "advance": statistics.median([a for x in chunks for a in x["advances"]] or [0.5])})
                opened = []
    return sorted(out, key=lambda x: x["since"])


EPICS = ("Baron", "Herald", "Voidgrub")  # those of the upper pit; the dragons, the lower one


def _pits(events: dict) -> dict[str, tuple[float, float]]:
    """Where the two pits are, taken from where the epics die. They don't have to be set by hand."""
    points = collections.defaultdict(list)
    for c in events["camps"]:
        if c["camp"] in EPICS:
            points["baron"].append(c["position"])
        elif c["camp"].startswith("Dragon"):
            points["dragon"].append(c["position"])
    return {pit: (statistics.median(p[0] for p in ps), statistics.median(p[1] for p in ps))
            for pit, ps in points.items()}


RIVER_WIDTH = 1600.0  # how far the river strays from its axis; the crab dies at most 1527 from it


def _zone(x: float, z: float, pits: dict, radius: float = 2500.0, width: float = RIVER_WIDTH) -> str:
    """Which map zone a point falls in: one of the two pits, the river, or a jungle sector.

    The sectors are the four quadrants left by the map's two diagonals: the river splits blue from
    red (x+z) and the other splits top from bottom (z against x). It is the same division `camps` already uses to
    say whose each camp is.

    The river goes apart from the sectors even though geometrically it falls between the two, because controlling it is
    something else: it is the pass, not the jungle. Its width is checked against where the crab dies."""
    for pit, center in pits.items():
        if math.dist((x, z), center) <= radius:
            return f"pit of the {pit}"
    half = "/top" if z > x else "/bot"
    if abs(x + z - RIVER) <= width:
        return "river" + half
    return ("blue" if x + z < RIVER else "red") + half


def zones(events: dict, state: dict, rows, since: float = 300.0, alone: float = 2500.0,
          near: float = 1600.0, drag: float = 4.0, stuck: float = 20.0) -> list[dict]:
    """The jungle/support duo's zone control: warding a sector and punishing whoever crosses it alone.

    The Rift has six zones that can be controlled: the four jungle sectors —blue and red, each
    split into the top and the bottom one— and the two pits, which are those of the objectives. None is
    set by hand: the sectors are the quadrants of the map's two diagonals and the pits come from where
    the epics die.

    Controlling a zone isn't being inside it, it is making it costly for the enemy to enter. It is measured by the two things that
    do that:

    - **vision**: seconds with at least one of your wards alive inside, and how many control wards you place
        there, which are also the ones that take vision away from the other;
    - **punishments**: someone from the other team enters **without a numerical advantage** —with no teammate within
      `alone`, which is 2500 so that a team fight doesn't count as a facecheck— and takes damage
      from two or more of yours who were already there. That is punishing a facecheck, and it is what makes
      them enter more carefully next time or not enter.

    And against that, what it costs: your own deaths inside the zone. Defending a zone isn't dying
    for it, so the two columns go together and neither is subtracted from the other."""
    champion_by_net = {p["net_id"]: p["champion"] for p in events["players"]}
    team_of = {p["champion"]: p["team"] for p in events["players"]}
    order = [p["champion"] for p in events["players"]]
    pits = _pits(events)
    end = min(events["game_length"], max(float(f["time"]) for theirs in rows.values() for f in theirs))
    table = {c: {int(float(f["time"])): f for f in theirs} for c, theirs in rows.items()}
    wards = _wards(events)
    hit_damage, deaths = collections.defaultdict(list), collections.defaultdict(list)
    for e in events["events"]:
        if e["type"] == "Damage" and e.get("source") in champion_by_net and e["net_id"] in champion_by_net:
            hit_damage[(champion_by_net[e["source"]], champion_by_net[e["net_id"]])].append(e["time"])
        elif e["type"] == "Death" and e["net_id"] in champion_by_net:
            deaths[champion_by_net[e["net_id"]]].append(e["time"])
    owner_of = {p["net_id"]: p["team"] for p in events["players"]}
    controls = collections.Counter()  # (team, zone) → control wards placed there

    def spot(champion, t):
        f = table[champion].get(int(t))
        return (float(f["x"]), float(f["z"])) if f and f["x"] and f["alive"] == "True" else None

    for e in events["events"]:
        if e["type"] == "CastSpell" and e["spell"] == "JammerDevice" and e["time"] >= since:
            controls[(owner_of.get(e["net_id"]), _zone(*e["target"], pits))] += 1

    sighted = collections.defaultdict(int)      # (team, zone) → seconds with a live ward
    inside = collections.defaultdict(int)     # (team, zone) → seconds with someone inside
    punishments, dies_at, last_ = [], collections.defaultdict(list), {}
    for t in range(int(since), int(end)):
        alive = [(w, e) for t0, t1, w, e, _q in wards if t0 <= t <= t1]
        for w, team in alive:
            sighted[(team, _zone(*w, pits))] += 1
        where = {c: spot(c, t) for c in order}
        for team, zone in {(team_of[c], _zone(*q, pits)) for c, q in where.items() if q}:
            inside[(team, zone)] += 1  # seconds with someone of theirs inside, not a sum of champions
        for victim, q in where.items():
            if not q:
                continue
            own = team_of[victim]
            if any(p and c != victim and team_of[c] == own and math.dist(p, q) <= alone
                   for c, p in where.items()):
                continue  # they aren't alone: it isn't a facecheck without a numerical advantage
            catchers = [c for c, p in where.items() if p and team_of[c] != own and math.dist(p, q) <= near]
            if len(catchers) < 2 or not any(any(t <= x <= t + drag for x in hit_damage[(c, victim)]) for c in catchers):
                continue
            zone = _zone(*q, pits)
            if t - last_.get(victim, -1e9) <= stuck:
                continue  # the same one caught five seconds in a row is the same punishment
            last_[victim] = t
            punishments.append({"time": t, "zone": zone, "victim": victim, "team": team_of[catchers[0]],
                             "catchers": sorted(catchers),
                             "died": any(t <= x <= t + drag + 2 for x in deaths[victim])})
    for c in order:
        for x in deaths[c]:
            q = spot(c, x - 1)
            if q and x >= since:
                dies_at[(team_of[c], _zone(*q, pits))].append(x)

    out = []
    for team in ("100", "200"):
        for zone in sorted({z for _e, z in list(sighted) + list(inside)} | {c["zone"] for c in punishments}):
            own_items = [c for c in punishments if c["team"] == team and c["zone"] == zone]
            who = collections.Counter(c for x in own_items for c in x["catchers"])
            out.append({"team": team, "zone": zone, "ward_seconds": sighted[(team, zone)],
                          "control_wards": controls[(team, zone)],
                          "presence": inside[(team, zone)], "punishments": own_items, "who": who,
                          "deaths": len(dies_at[(team, zone)])})
    return out


def setups(events: dict, state: dict, rows, punishments: list[dict] | None = None,
           before: float = 90.0, merge: float = 60.0) -> list[dict]:
    """How each objective is set up, which starts up to a minute and a half before it falls.

    An objective isn't decided when someone starts it: it is decided in the minute and a half before, placing
    vision in the pit and at the entrances, removing the other's and arriving first. That is why the window goes from
    `before` seconds until it falls, and not from the moment of the hit.

    For each objective come, for the two teams:

    - **when it arrives**: the seconds of lead with which one of theirs appears at the pit. Whoever arrives
      first chooses where the fight is fought from;
    - **the vision**: seconds with their live ward in the window's **area** and control wards placed
      there. The area isn't only the pit: it is the pit, the river of its half and the two jungle sectors of that
      same half, which is where it is entered from. Separately come the seconds inside the pit
      (`in_the_pit`) and in the river (`in_the_river`), because warding the objective, the pass and the jungle beside it
      are not the same thing;
    - **the facechecks punished** inside the window, which is what turns vision into control;
    - **which of the five sets it up**, counting one action per ward placed in the pit and one per facecheck
      punished, and what share of that work comes from the jungle/support duo, who are expected to do it as a
      general rule. It isn't imposed: who did it is measured and compared, because the exceptions are part of
      what has to be seen;
    - and who ends up taking it.

    Voidgrubs fall three at a time, so those that fall less than `merge` seconds apart count as a
    single objective. The pits come from `_pits` and the zones from `_zone`, as in `zones`."""
    owner_of = {p["net_id"]: p["team"] for p in events["players"]}
    team_of = {p["champion"]: p["team"] for p in events["players"]}
    champion_by_net = {p["net_id"]: p["champion"] for p in events["players"]}
    # who is expected to set up the objective: the duo. It isn't imposed, it is compared against what happens
    duo = {p["team"]: {q["champion"] for q in events["players"]
                       if q["team"] == p["team"] and q["position"] in ("JUNGLE", "UTILITY")}
           for p in events["players"]}
    order = [p["champion"] for p in events["players"]]
    pits = _pits(events)
    table = {c: {int(float(f["time"])): f for f in theirs} for c, theirs in rows.items()}
    wards = _wards(events)
    controls = [(e["time"], tuple(e["target"]), champion_by_net.get(e["net_id"])) for e in events["events"]
                 if e["type"] == "CastSpell" and e["spell"] == "JammerDevice"]

    epics = sorted((c["time"], c["camp"], c["killer"], tuple(c["position"])) for c in events["camps"]
                    if c["camp"] in EPICS or c["camp"].startswith("Dragon"))
    groups = []
    for t, camp, killer, where in epics:
        if groups and camp == groups[-1][-1][1] and t - groups[-1][-1][0] <= merge:
            groups[-1].append((t, camp, killer, where))
        else:
            groups.append([(t, camp, killer, where)])

    out = []
    for group in groups:
        falls_, camp, killer, where = group[-1]
        zone = _zone(*where, pits)
        # the setup doesn't happen only in the pit: half the work is at the entrances. The area is the pit
        # and the two jungle sectors of its same half of the map, which come from where the pit itself is
        half = "/top" if where[1] > where[0] else "/bot"
        area = {zone, "river" + half, "blue" + half, "red" + half}
        t0 = falls_ - before
        sides = {}
        for team in ("100", "200"):
            own_items = [c for c in order if team_of[c] == team]
            def warded(where_valid, t):
                return any(a <= t <= b and e == team and _zone(*w, pits) in where_valid
                           for a, b, w, e, _q in wards)
            seconds = range(int(t0), int(falls_) + 1)
            sighted = sum(warded(area, t) for t in seconds)
            in_the_pit = sum(warded({zone}, t) for t in seconds)
            in_the_river = sum(warded({"river" + half}, t) for t in seconds)
            present = [t for t in seconds
                         if any((f := table[c].get(t)) and f["x"] and f["alive"] == "True"
                                and _zone(float(f["x"]), float(f["z"]), pits) == zone for c in own_items)]
            places = collections.Counter(q for a, _b, w, e, q in wards
                                       if t0 <= a <= falls_ and e == team and _zone(*w, pits) in area)
            control = collections.Counter(q for t, w, q in controls
                                          if t0 <= t <= falls_ and q in own_items and _zone(*w, pits) in area)
            punishes = collections.Counter(
                c for x in (punishments or []) if x["team"] == team and x["zone"] in area
                and t0 <= x["time"] <= falls_ for c in x["catchers"])
            arrive = {}
            for c in own_items:
                for t in range(int(t0), int(falls_) + 1):
                    f = table[c].get(t)
                    if (f and f["x"] and f["alive"] == "True"
                            and _zone(float(f["x"]), float(f["z"]), pits) == zone):
                        arrive[c] = round(falls_ - t)
                        break
            work = places + punishes  # the control one is already in `places`: counting it here would duplicate it
            sides[team] = {
                "arrives": round(falls_ - present[0]) if present else None,
                "ward_seconds": sighted, "in_the_pit": in_the_pit, "in_the_river": in_the_river,
                "presence": len(present),
                "control_wards": sum(control.values()), "punishments": sum(punishes.values()),
                "places": dict(places), "arrive": arrive, "work": dict(work),
                # the share of the work the duo does, who are the ones expected to
                "duo": (sum(v for c, v in work.items() if c in duo[team]) / sum(work.values())
                            if work else None)}
        out.append({"objective": camp + (f" x{len(group)}" if len(group) > 1 else ""), "falls": falls_,
                      "zone": zone, "takes_it": owner_of.get(killer), "sides": sides})
    return out


# ── fights, flashes, backs and roams ────────────────────────────────────────────────────────────────────


def _table(events: dict, rows) -> dict[str, dict[int, dict]]:
    """Each champion's row at each second."""
    return {p["champion"]: {int(float(f["time"])): f for f in rows.get(p["champion"], [])} for p in events["players"]}


def _spot(row) -> tuple[float, float] | None:
    return (float(row["x"]), float(row["z"])) if row and row["x"] else None


def _spent_gold(row) -> float:
    """Gold put into items: what was earned minus what they carry."""
    # ponytail: it doesn't discount what was sold; with BuyItem and Data Dragon's prices it would be exact
    return (_num(row, "total_gold") or 0) - (_num(row, "gold") or 0) if row else 0.0


def _loss(table_c: dict[int, dict], seconds) -> float:
    """Health lost in those seconds: what drops from one second to the next while alive. It comes from the table and
    not from `Damage` because those only carry the full champion hit; the minion and turret one is missing
    (60-95% of the official TOTAL_DAMAGE_TAKEN)."""
    total = 0.0
    for s in seconds:
        a, b = table_c.get(s - 1), table_c.get(s)
        if a and b and a["alive"] == b["alive"] == "True" and a["health"] and b["health"]:
            total += max(0.0, float(a["health"]) - float(b["health"]))
    return total


def fights(events: dict, rows, gap: float = 5.0, radius: float = 3000.0, outnumbered: float = 1000.0,
           teamfight: int = 8) -> list[dict]:
    """Each fight between champions: the hits between enemies, joined as long as `gap` seconds don't pass
    without hitting each other and falling within `radius` of the last one, so a split in top isn't added to the dragon fight.

    Whoever hits or is hit takes part. It is a **teamfight** if `teamfight` of the ten take part (8 = 80% of the
    lobby); otherwise, it is a skirmish (a catch, a 2v2…). Each team arrives with what those taking part have spent on
    items, and is **at a disadvantage** if it arrives with `outnumbered` less gold than the other."""
    champion_by_net = {p["net_id"]: p["champion"] for p in events["players"]}
    team_of = {p["champion"]: p["team"] for p in events["players"]}
    table = _table(events, rows)
    open_ones, closed = [], []
    for e in events["events"]:
        if e["type"] != "Damage" or e.get("source") not in champion_by_net or e["net_id"] not in champion_by_net:
            continue
        who, suffers = champion_by_net[e["source"]], champion_by_net[e["net_id"]]
        if team_of[who] == team_of[suffers] or not (where := _spot(table[suffers].get(int(e["time"])))):
            continue
        for p in list(open_ones):
            if e["time"] - p["until"] > gap:
                open_ones.remove(p)
                closed.append(p)
        p = next((p for p in open_ones if math.dist(p["where"], where) <= radius), None)
        if p is None:
            open_ones.append(p := {"since": e["time"], "damage": collections.Counter(), "taken": collections.Counter()})
        p["until"], p["where"] = e["time"], where
        p["damage"][who] += e["amount"]
        p["taken"][suffers] += e["amount"]
    closed += open_ones

    deaths = [(e["time"], champion_by_net[e["net_id"]]) for e in events["events"]
               if e["type"] == "Death" and e["net_id"] in champion_by_net]
    out = []
    for p in sorted(closed, key=lambda p: p["since"]):
        involved = set(p["damage"]) | set(p["taken"])
        t0 = int(p["since"]) - 1
        sides = {eq: sorted(c for c in involved if team_of[c] == eq) for eq in ("100", "200")}
        if not sides["100"] or not sides["200"]:
            continue
        gold = {eq: sum(_spent_gold(table[c].get(t0)) for c in cs) for eq, cs in sides.items()}
        dying = [c for t, c in deaths if c in involved and p["since"] <= t <= p["until"] + 3]
        out.append({
            "since": round(p["since"], 1), "until": round(p["until"], 1), "x": round(p["where"][0]),
            "z": round(p["where"][1]), "take_part": len(involved), "teamfight": int(len(involved) >= teamfight),
            **{f"champions_{eq}": len(cs) for eq, cs in sides.items()},
            **{f"gold_{eq}": round(o) for eq, o in gold.items()},
            "lower": ("100" if gold["100"] < gold["200"] - outnumbered
                         else "200" if gold["200"] < gold["100"] - outnumbered else ""),
            **{f"deaths_{eq}": sum(team_of[c] == eq for c in dying) for eq in ("100", "200")},
            "who": sorted(involved), "damage": dict(p["damage"]), "taken": dict(p["taken"])})
    return out


# (first appearance, comes back after falling), in seconds. Without baron: in soloq it isn't set up like the dragon, it comes out of
# a catch, so reaching it without flash isn't having spent it badly.
SPAWNS = {"Dragon": (300.0, 300.0)}


def _timers(events: dict) -> list[tuple[float, float, str]]:
    """(spawns, falls, which) of each `SPAWNS` objective, counting the timer: the first at its minute and the next
    when due after the previous falls. The one still alive at the end of the match falls at infinity."""
    # ponytail: the elder dragon (after the soul) comes back at 6 min and here it counts as one more of 5
    out = []
    for name, (first, goes_back) in SPAWNS.items():
        falls = sorted(c["time"] for c in events["camps"] if c["camp"].startswith(name))
        spawns_at = first
        for falls_ in [*falls, math.inf]:
            out.append((spawns_at, falls_, name))
            spawns_at = falls_ + goes_back
    return out


def flashes(events: dict, rows, fight_list: list[dict], before: float = 45.0, after: float = 10.0,
            near: float = 3000.0, since: float = 840.0, kill: float = 5.0) -> list[dict]:
    """Each flash, with what it was used for:

    - **objective**: past the laning phase (`since`), in the `before` seconds before a dragon or baron (or
      `after` after it falls) and within `near` of the pit;
    - **teamfight** or **skirmish**: inside a fight in which whoever flashes takes part;
    - **outside a fight**: everything else (escaping a gank without hits, repositioning…).

    It is **suboptimal** if spent in a skirmish or outside a fight (the catch: an assassin forces it from you, or an
    overextend) and the next dragon appears before the flash is back: 4 min remain and it comes back in
    3:30, fine; 2 remain and it comes back in 5, bad. If it is already alive, 0 remain (see `_timers`). Only past the laning
    phase (`since`): before, almost every flash arrives without coming back for the dragon, which comes out every 5 min like the flash. Spending it in a teamfight or on the objective itself is fine even if the next (a dragon
    right after the baron) catches you without flash: that is what it's for. And it is **offensive** if in the following `kill` seconds
    an enemy dies whom whoever flashes hits after the flash."""
    champion_by_net = {p["net_id"]: p for p in events["players"]}
    objectives = [(c["time"], c["position"], c["camp"]) for c in events["camps"]
                 if c["time"] >= since and (c["camp"] == "Baron" or c["camp"].startswith("Dragon"))]
    deaths = [(e["time"], champion_by_net[e["net_id"]]) for e in events["events"]
               if e["type"] == "Death" and e["net_id"] in champion_by_net]
    hits = [(e["time"], champion_by_net[e["source"]]["champion"], champion_by_net[e["net_id"]]["champion"])
              for e in events["events"]
              if e["type"] == "Damage" and e.get("source") in champion_by_net and e["net_id"] in champion_by_net]
    out = []
    for e in events["events"]:
        if e["type"] != "CastSpell" or e["net_id"] not in champion_by_net or "flash" not in e["spell"].lower():
            continue
        p, t = champion_by_net[e["net_id"]], e["time"]
        fight = next((f for f in fight_list if f["since"] - 3 <= t <= f["until"] + 1 and p["champion"] in f["who"]), None)
        if any(o - before <= t <= o + after and math.dist(e["origin"], spot) <= near for o, spot, _n in objectives):
            use = "objective"
        elif fight:
            use = "teamfight" if fight["teamfight"] else "skirmish"
        else:
            use = "out of fight"
        victims = {v["champion"] for tm, v in deaths if t < tm <= t + kill and v["team"] != p["team"]}
        offensive = any(t <= tg <= t + kill and source == p["champion"] and a in victims for tg, source, a in hits)
        next_ = min(((max(spawns_at - t, 0.0), n) for spawns_at, falls_, n in _timers(events) if falls_ > t), default=None)
        no_flash = bool(next_) and next_[0] < e["cooldown"]
        out.append({"champion": p["champion"], "position": p["position"], "team": p["team"], "time": round(t, 1),
                      "use": use, "offensive": int(offensive), "take_part": fight["take_part"] if fight else 0,
                      "next_objective": next_[1] if next_ else "",
                      "seconds_to_objective": round(next_[0]) if next_ else "",
                      "arrives_no_flash": int(no_flash), "cooldown": round(e["cooldown"]),
                      "suboptimal": int(no_flash and t >= since and use in ("skirmish", "out of fight"))})
    return out


def health_before_back(events: dict, rows, how_many: int = 2, since: float = 90.0,
                        recall_list: list[dict] | None = None) -> list[dict]:
    """How much health each player loses before their first and second back (see `_loss`). They go back to base with
    a completed recall or by dying; those before `since` (shopping before the first wave) aren't backs."""
    champion_by_net = {p["net_id"]: p["champion"] for p in events["players"]}
    table = _table(events, rows)
    goes_back = collections.defaultdict(list)
    for r in recalls(events, rows) if recall_list is None else recall_list:
        if not r["cancelled"]:
            goes_back[r["champion"]].append(r["time"])
    for e in events["events"]:
        if e["type"] == "Death" and e["net_id"] in champion_by_net:
            goes_back[champion_by_net[e["net_id"]]].append(e["time"])
    out = []
    for p in events["players"]:
        c, marks = p["champion"], [0.0, *sorted(t for t in goes_back[p["champion"]] if t >= since)][: how_many + 1]
        row = {"champion": c}
        for i, (a, b) in enumerate(itertools.pairwise(marks), 1):
            row[f"back{i}_time"] = round(b)
            row[f"back{i}_health_lost"] = round(_loss(table[c], range(int(a) + 1, int(b) + 1)))
        out.append(row)
    return out


def with_the_marksman(table, base: tuple[float, float], adc: str, sup: str, since: float, until: float,
                   far: float, close: float) -> tuple[list[tuple[int, int]], list[int]]:
    """The seconds of [since, until) with the marksman and the support alive, and the marksman in bot and out of their base:
    ((second, 0) in which the support is more than `far` from them, seconds in which they are within
    `close`). It is what `roams` looks at, and where the moments in which the support stays come from."""
    goes, is_ = [], []
    for s in range(int(since), int(until)):
        a, b = table[adc].get(s), table[sup].get(s)
        pa, pb = _spot(a), _spot(b)
        if not (pa and pb and a["alive"] == "True" and b["alive"] == "True"):
            continue
        if _lane(*pa) != "bot" or math.dist(pa, base) < 3000:
            continue
        if math.dist(pa, pb) > far:
            goes.append((s, 0))
        elif math.dist(pa, pb) <= close:
            is_.append(s)
    return goes, is_


def roams(events: dict, rows, since: float = 120.0, until: float = 840.0, far: float = 3000.0,
          close: float = 1500.0, minimum: int = 15, gap: int = 2) -> tuple[list[dict], list[dict]]:
    """What happens to the marksman while their support leaves the lane, against what happens with them beside.

    In the laning phase, each second the marksman is alive in bot and out of their base; the support **roams** if
    alive more than `far` from them, and **accompanies** if within `close`. A roam is a run of at
    least `minimum` seconds (forgiving `gap`). For each roam: the health the marksman loses, whether they die, and the
    resources they spend (summoner spells and R). Returns (one row per roam, the totals per marksman with
    the same numbers when accompanied), to compare per minute: without the comparison there is no datum. The health
    lost is that of `_loss`."""
    table, bases = _table(events, rows), _bases(rows)
    champion_by_net = {p["net_id"]: p["champion"] for p in events["players"]}
    died, spends = collections.defaultdict(list), collections.defaultdict(list)
    for e in events["events"]:
        if e.get("net_id") not in champion_by_net:
            continue
        c = champion_by_net[e["net_id"]]
        if e["type"] == "Death":
            died[c].append(e["time"])
        elif e["type"] == "CastSpell" and e["slot"] in (3, 4, 5):
            spends[c].append((e["time"], "r" if e["slot"] == 3 else "summoners"))

    def count(c, seconds):
        s = set(seconds)
        return {"health_lost": round(_loss(table[c], seconds)),
                "deaths": sum(int(t) in s for t in died[c]),
                "summoners": sum(int(t) in s and k == "summoners" for t, k in spends[c]),
                "r": sum(int(t) in s and k == "r" for t, k in spends[c])}

    by_roam, by_marksman = [], []
    for team in ("100", "200"):
        position = {p["position"]: p["champion"] for p in events["players"] if p["team"] == team}
        adc, sup = position.get("BOTTOM"), position.get("UTILITY")
        if not adc or not sup:
            continue
        goes, is_ = with_the_marksman(table, bases[team], adc, sup, since, until, far, close)
        roam_s = []
        for streak in _rafagas(goes, gap):
            t0, t1 = streak[0][0], streak[-1][0]
            if t1 - t0 + 1 < minimum:
                continue
            seconds = range(t0, t1 + 1)
            roam_s += seconds
            mid = _spot(table[sup].get((t0 + t1) // 2))
            by_roam.append({"team": team, "marksman": adc, "support": sup, "time": t0, "lasts": t1 - t0 + 1,
                             "to_where": _lane(*mid) if mid else "", **count(adc, seconds)})
        alone, with_ = count(adc, roam_s), count(adc, is_)
        by_marksman.append({"champion": adc, "seconds": len(roam_s), **alone,
                            **{f"accompanied_{k}": v for k, v in with_.items()}, "accompanied_seconds": len(is_)})
    return by_roam, by_marksman


# ── the jungle: camps that go in pairs and plays ──────────────────────────────────────────────────────

PAIRS = {"Raptors": "Krugs", "Krugs": "Raptors", "Wolves": "Gromp", "Gromp": "Wolves"}  # the two small ones of a sector
CAMP_GOLD = {"Gromp": 80.0, "Wolves": 85.0, "Raptors": 75.0, "Krugs": 109.0}  # 16.19, measured (idle_jungle)
PASSIVE_GOLD = 2.04  # gold per second that falls by itself: what is missing between `total_gold` and the sum of the Gold events
GOLD_PER_XP = 0.35  # what a point of XP weighs against one of gold in the value model before 15 (value.py)
# What an objective is worth in gold, which it doesn't give in gold: its WP points (value.md: dragon 12, herald 4, grubs 3.8
# all three) at about 100 gold per point, which is what gold weighs in that model before 15
OBJECTIVE_GOLD = {"Dragon": 1200.0, "Herald": 400.0, "Voidgrub": 130.0}


def _monsters(events: dict) -> dict[tuple[str, str], tuple[list[float], list[float]]]:
    """When each small camp of each jungle spawns and falls: {(camp, side): (spawns, falls)}.
    It spawns when its big monster is born (`SpawnNeutral`; the "Mini" ones are born with it or on splitting) and falls with `camps`."""
    out: dict[tuple[str, str], tuple[list[float], list[float]]] = {}
    for e in events["events"]:
        if e["type"] != "SpawnNeutral" or "mini" in (name := (e.get("character") or "").lower()):
            continue
        camp = next((c for c in SMALL if name.startswith(MAIN[c])), None)
        if camp and any(e["position"]):
            out.setdefault((camp, "blue" if sum(e["position"]) < RIVER else "red"), ([], []))[0].append(e["time"])
    for c in events["camps"]:
        if c["camp"] in SMALL and (c["camp"], c["side"]) in out:
            out[(c["camp"], c["side"])][1].append(c["time"])
    return {k: (sorted(leaves), sorted(falls_)) for k, (leaves, falls_) in out.items()}


def _alive_between(health: tuple[list[float], list[float]], since: float, until: float) -> float:
    """Seconds of [since, until] in which the camp is alive (it has spawned and hasn't been cleared)."""
    leaves, falls_ = health
    total = 0.0
    for s in leaves:
        end = next((k for k in falls_ if k > s), math.inf)
        total += max(0.0, min(end, until) - max(s, since))
    return total


def camp_pairs(events: dict, rows, fight_list: list[dict] | None = None, until: float = 840.0,
            window: float = 45.0, margin: float = 20.0) -> dict[str, dict]:
    """The small camps of a sector are cleared in the same pass: Raptors with Krugs and Wolves with Gromp.

    If one is cleared and the other stays alive, from there on they spawn out of sync, and each pass through that
    sector finds half a sector: either you wait for the other, or you go back for it. That is why, in the laning phase, doing
    the Raptors and not having done the Krugs `window` seconds later is a mistake even if they are cleared afterwards.

    For each clear of one of their small camps made by the jungler before `until`:

    - **paired**: their team clears the other within `window` seconds, before or after;
    - **broken**: the other was alive (or spawning within `margin` seconds) and after `window` seconds it is still there. With what
      they did instead of clearing it (`did`: dying, going back to base, a fight, an objective, another camp or
      none of that) and how long they took to come back for it (`wait`, None if they don't before `until`);
    - **stolen**: the enemy takes the other one in that window; it isn't a routing mistake, it's a theft (`idle_jungle`);
    - **unpaired**: the other wasn't there nor was about to spawn. The mistake isn't this one: it's whatever unpaired them.

    Measured in the 5,143 matches of 16.19 (16,377 broken pairs before 14): **1.9 per match are broken in Gold and
    1.4 in Challenger**, and what changes with the league is the reason. Almost half are due to a fight in all leagues
    (43-48%) and those aren't a routing mistake; those that go down are going to another camp (20% in Gold, 10% in
    Challenger) and staying without doing anything (4.9% against 2.9%), and those that go up are dying (15.8% against 19.5%) and
    going back to base (11.1% against 15.0%)."""
    net_of = {p["champion"]: p["net_id"] for p in events["players"]}
    team_of = {p["net_id"]: p["team"] for p in events["players"]}
    junglers = {p["team"]: p["champion"] for p in events["players"] if p["position"] == "JUNGLE"}
    healths = _monsters(events)
    deaths, recalls = collections.defaultdict(list), collections.defaultdict(list)
    for e in events["events"]:
        if e["type"] == "Death":
            deaths[e["net_id"]].append(e["time"])
        elif e["type"] == "AddBuff" and e["buff"].lower() == "recall":
            recalls[e["net_id"]].append(e["time"])
    out = {}
    for side, team in (("blue", "100"), ("red", "200")):
        jungler = junglers.get(team)
        if not jungler:
            continue
        net = net_of[jungler]
        own_ones = sorted((c["time"], c["camp"], c.get("killer")) for c in events["camps"]
                         if c["camp"] in SMALL and c["side"] == side)
        count, broken = collections.Counter(), []
        for t, camp, who in own_ones:
            if who != net or t > until:
                continue
            other = PAIRS[camp]
            count["clears"] += 1
            near = [q for tt, c, q in own_ones if c == other and abs(tt - t) <= window]
            if any(team_of.get(q) == team for q in near):
                count["paired"] += 1
            elif near:
                count["stolen"] += 1
            elif (other, side) in healths and _alive_between(healths[(other, side)], t, t + margin) > 0:
                goes_back = next((tt for tt, c, q in own_ones if c == other and tt > t and team_of.get(q) == team), None)
                did = ("died" if any(t < m <= t + window for m in deaths[net]) else
                        "goes back to base" if any(t < r <= t + window for r in recalls[net]) else
                        "fight" if any(jungler in f["who"] and t - 5 <= f["since"] <= t + window
                                       for f in fight_list or []) else
                        "objective" if any(c["camp"].startswith(("Dragon", "Voidgrub", "Herald"))
                                          and t < c["time"] <= t + window and team_of.get(c.get("killer")) == team
                                          for c in events["camps"]) else
                        "other camp" if any(c.get("killer") == net and t < c["time"] <= t + window
                                                 for c in events["camps"]) else "nothing")
                count["broken"] += 1
                broken.append({"t": round(t, 1), "camp": camp, "duo": other, "did": did,
                              "wait": round(goes_back - t, 1) if goes_back is not None and goes_back <= until else None})
            else:
                count["unpaired"] += 1
        out[jungler] = {"team": team, "clears": count["clears"], "paired": count["paired"],
                         "broken": count["broken"], "stolen": count["stolen"],
                         "unpaired": count["unpaired"], "detail": broken}
    return out


def plays(events: dict, state: dict, rows, fight_list: list[dict], show: list[dict], idle: dict,
            since: float = 120.0, until: float = 840.0, arrival: float = 25.0, tail: float = 40.0,
            merge: float = 20.0, near: float = 2000.0, goes_back: float = 90.0, gank: float = 8.0) -> list[dict]:
    """Each of the jungler's plays in the laning phase, with what they stopped farming by making it and what those who took part
    got out of it, from both teams: whether the play paid for the camps left alive.

    A **play** is a stretch in which the jungler stops farming to play with others: a fight they enter
    (`fights`), a gank even if it doesn't get to hit (a `show_up` window with an enemy laner in range for
    `gank` seconds or more) or an objective that falls with them beside it. Those following less than `merge` seconds apart
    are the same one. It goes from `start` (when they left the last camp, at most `arrival` seconds before the
    first contact) to `end` (`tail` seconds after the last: how long it takes for a kill to be cashed in plates,
    waves and enemy camps).

    **What it costs** is their live small camps meanwhile, as in `idle_jungle`: each second a
    camp stays alive delays all its following clears, so the cost is the part of a
    clear that is lost (seconds alive over its period), not the whole camp, which is cleared later. It is
    counted until they clear something again (at most `goes_back` seconds after the play: if they die in it, the
    camps stay stalled while they respawn and arrive). `gold_camps` is what was on the map.

    **What is got** belongs to all those involved, each against what they would have done without the play:

    - a **laner**, against their own gold and XP pace in the laning phase (`total_gold` and `xp`, which carry
      everything: kills, plates, waves). Whoever moves to help and loses their wave comes out negative, whoever dies
      too (they don't collect while dead), and whoever takes a kill or some plates, positive. Only the laner
      for whom the play changes something enters: they die, collect a takedown or leave their lane to go (within
      `near` of the jungler). Nothing is noted for whoever keeps farming with the jungler around: their gold in that stretch
      against their pace is the cannon that falls to them or doesn't, and that is noise, not play. They are counted until
      they start going back to base (after a fight you go back to shop, and in base you don't collect: that isn't part of the
      play). For the **support** only what they collect from takedowns and turrets counts in gold: their gold doesn't come from farming and goes
      in lumps (the item), so against their pace only XP is measured;
    - a **jungler**, what they get from the play (kills and assists, turrets and plates, epics and the enemy's
      camps) minus the cost of their camps. What they farm of their own in that stretch isn't part of the play: neither their
      gold, nor the XP of the seconds in which they collect one of their monsters or a minion.

    `invaded` marks the play they didn't choose: a fight, with no gank or objective, inside their own jungle (they
    are invaded). It is measured the same, but it isn't "leaving the camps to do something else".

    `net_gold` and `net_xp` are their team's minus the enemy's, and `value`, the two together in gold (a point of XP
    weighs GOLD_PER_XP) plus the objectives that fall in the play (`objectives`, at OBJECTIVE_GOLD: a dragon gives no gold, but it is
    worth something). `verdict`: "good" from +100 up, "bad" from -75 down (a gank that gets nothing with two
    live camps already costs that) and "even" in between.

    Measured in the 5,143 matches of 16.19 (72,762 plays before 14, without the `invaded`): **the jungler makes 6.6-7.1
    per match in all leagues and almost all with live camps**; what changes with the league isn't how many nor what
    share goes well (good 52% in Gold and 55% in Challenger) but **how much farming is given up to make them**: 84 g of
    delayed clears per play in Gold against 59 g in Challenger. The median of live camps at the start of a
    play is 184 g, and the mean value of a play, +226 g in Gold and +272 g in Challenger. By type: objectives
    almost always pay (85% good, +1,058 g on average), ganks and fights come out level (51-53% good,
    +220 g). A play with no takedowns, no deaths and no objective (18%) is worth -59 g on average: exactly what
    the camps cost."""
    champion_by_net = {p["net_id"]: p["champion"] for p in events["players"]}
    team_of = {p["champion"]: p["team"] for p in events["players"]}
    position = {p["champion"]: p["position"] for p in events["players"]}
    junglers = {p["team"]: p["champion"] for p in events["players"] if p["position"] == "JUNGLE"}
    table = _table(events, rows)
    healths = _monsters(events)
    game_end = events["game_length"]
    spawned_at = {e["net_id"]: e for e in events["events"] if e["type"] == "SpawnNeutral"}
    turrets = {e["net_id"] for e in events["events"] if e["type"] == "SetSpell" and "Turret" in (e.get("name") or "")}
    falls_ = collections.defaultdict(list)  # victim → when they die
    goes_back_to_base = collections.defaultdict(list)  # champion → when each recall starts
    for e in events["events"]:
        if e["type"] == "Death" and e["net_id"] in champion_by_net:
            falls_[champion_by_net[e["net_id"]]].append(e["time"])
        elif e["type"] == "AddBuff" and e["buff"].lower() == "recall" and e["net_id"] in champion_by_net:
            goes_back_to_base[champion_by_net[e["net_id"]]].append(e["time"])
    pits = _pits(events)
    payouts = collections.defaultdict(list)  # champion → (second, from what, how much)
    for e in events["events"]:
        if e["type"] != "Gold" or e["net_id"] not in champion_by_net or not e["amount"]:
            continue
        who, source = champion_by_net[e["net_id"]], e["unit"]
        if source in champion_by_net:  # the support item also gives gold on hitting a champion: that isn't a takedown
            kind = "kills" if any(abs(e["time"] - m) <= 1.5 for m in falls_[champion_by_net[source]]) else "farm"
        elif source in turrets or source == "0x0":
            kind = "towers"
        elif source in spawned_at:
            name = (spawned_at[source].get("character") or "").lower()
            own_side = (sum(spawned_at[source]["position"]) < RIVER) == (team_of[who] == "100")
            kind = ("epics" if name.startswith(("sru_dragon", "sru_baron", "sru_riftherald", "sru_horde")) else
                    "farm" if own_side or name.startswith("sru_crab") else "invade")
        else:
            kind = "farm"  # minions, wards and what each champion summons
        payouts[who].append((e["time"], kind, e["amount"]))

    def row(c: str, t: float) -> dict | None:
        for d in (0, -1, 1, -2, 2, -3, 3):
            if (f := table[c].get(int(t) + d)) and f.get("total_gold"):
                return f
        return None

    def spot(c: str, t: float) -> tuple[float, float] | None:
        f = table[c].get(int(t))
        return (float(f["x"]), float(f["z"])) if f and f["x"] and f["alive"] == "True" else None

    def rise(c: str, column: str, a: float, b: float) -> float:
        goes, vb = (_num(f, column) if (f := row(c, t)) else None for t in (a, b))
        # the uninitialised memory the decoder sometimes lets through (a gold of 1e27) isn't a rise
        return vb - goes if goes is not None and vb is not None and abs(vb - goes) < 1e5 else 0.0

    cap = min(until, game_end - 5)
    pace = {c: (rise(c, "total_gold", since, cap) / max(1.0, cap - since),
                 rise(c, "xp", since, cap) / max(1.0, cap - since)) for c in team_of}
    cleared_at = collections.defaultdict(list)  # champion → when each camp is cleared, of whichever side
    for c in events["camps"]:
        if c.get("killer") in champion_by_net:
            cleared_at[champion_by_net[c["killer"]]].append(c["time"])
    lane_of = {c: LANES[p] for c, p in position.items() if p in LANES}

    def xp_of_play(c: str, a: float, b: float) -> float:
        """The XP a jungler gains in (a, b] outside the seconds in which they collect something from their farm."""
        farm = {int(t) + d for t, kind, _o in payouts[c] if kind == "farm" and a - 1 <= t <= b + 1 for d in (0, 1)}
        return sum(max(0.0, rise(c, "xp", s - 1, s)) for s in range(int(a) + 1, int(b) + 1) if s not in farm)

    def cost(jungler: str, a: float, b: float) -> tuple[float, float, float, list[str]]:
        """(gold and XP lost through the delay, gold of the camps that were alive, which ones) in [a, b]."""
        side = "blue" if team_of[jungler] == "100" else "red"
        own = idle.get(jungler) or {}
        period = own.get("period") or 135.0
        value = {d["camp"]: (d["gold_camp"] or CAMP_GOLD[d["camp"]], d["xp_camp"])
                 for d in own.get("detail", [])}
        gold = xp = face = 0.0
        alive = []
        for camp in SMALL:
            seconds = _alive_between(healths[(camp, side)], a, b) if (camp, side) in healths else 0.0
            if seconds <= 0:
                continue
            o, x = value.get(camp, (CAMP_GOLD[camp], 0.0))
            gold, xp, face = gold + seconds / period * o, xp + seconds / period * x, face + o
            alive.append(camp)
        return gold, xp, face, alive

    out = []
    for team, jungler in junglers.items():
        rival_team = "200" if team == "100" else "100"
        contacts = [(f["since"], f["until"], "fight", set(f["who"])) for f in fight_list
                     if jungler in f["who"] and since <= f["since"] <= until]
        for j in show:
            if j["jungler"] == jungler:
                contacts += [(float(v["since"]), float(v["until"]), "gank", set(v["near"])) for v in j["windows"]
                              if v["near"] and v["until"] - v["since"] + 1 >= gank]
        for c in events["camps"]:
            if (c["camp"].startswith(("Dragon", "Voidgrub", "Herald")) and since <= c["time"] <= until
                    and team_of.get(champion_by_net.get(c.get("killer"), "")) == team and any(c["position"])
                    and (q := spot(jungler, c["time"])) and math.dist(q, c["position"]) <= 3000):
                contacts.append((c["time"] - 15.0, c["time"], "objective", set()))
        groups: list[list] = []
        for a, b, kind, whom in sorted(contacts, key=lambda x: x[0]):
            if groups and a - groups[-1][1] <= merge:
                groups[-1][1] = max(groups[-1][1], b)
                groups[-1][2].add(kind)
                groups[-1][3] |= whom
            else:
                groups.append([a, b, {kind}, set(whom)])
        for k, (a, b, kinds, whom) in enumerate(groups):
            before = [t for t in cleared_at[jungler] if t <= a]
            start = min(a, max(a - arrival, before[-1] if before else 0.0, groups[k - 1][1] + tail if k else 0.0))
            end = min(b + tail, game_end - 1, groups[k + 1][0] if k + 1 < len(groups) else math.inf)
            end = max(end, b)
            after = [t for t in cleared_at[jungler] if t > b]
            camps_end = max(b, min(after[0] if after else math.inf, b + goes_back, game_end - 1))
            # those involved: the junglers, and the laner who dies, collects a takedown or leaves their lane to go
            for c in team_of:
                if sum(1 for t in range(int(a), int(b) + 1) if (p := spot(c, t)) and (q := spot(jungler, t))
                       and math.dist(p, q) <= near) >= 3:
                    whom.add(c)
            whom = {c for c in whom if position[c] == "JUNGLE"
                       or any(a - 2 <= m <= end for m in falls_[c])
                       or any(kind == "kills" and start < t <= end for t, kind, _o in payouts[c])
                       or sum(1 for t in range(int(a), int(b) + 1) if (p := spot(c, t))
                              and _out_of_lane(state, lane_of[c], *p)) >= 5} | {jungler}
            lasts = max(1.0, end - start)
            accounts, net = {}, {"gold": 0.0, "xp": 0.0}
            gold_c, xp_c, face, alive = cost(jungler, start, camps_end)
            for c in sorted(whom):
                own_items: collections.Counter = collections.Counter()
                for t, kind, how_much in payouts[c]:
                    if start < t <= end:
                        own_items[kind] += how_much
                total = rise(c, "total_gold", start, end)
                if position[c] == "JUNGLE":
                    plates = max(0.0, total - sum(own_items.values()) - PASSIVE_GOLD * lasts)
                    gold = own_items["kills"] + own_items["towers"] + own_items["epics"] + own_items["invade"] + plates
                    xp = xp_of_play(c, start, end)
                    if c == jungler:
                        gold, xp = gold - gold_c, xp - xp_c
                    else:  # the enemy jungler also leaves their own to play it
                        o2, x2, _face, _v = cost(c, start, end)
                        gold, xp = gold - o2, xp - x2
                else:  # a laner, until they start going back to base
                    until_ = min([end, *(t for t in goes_back_to_base[c] if b < t < end)])
                    span = max(1.0, until_ - start)
                    gold = (own_items["kills"] + own_items["towers"] if position[c] == "UTILITY" else
                           rise(c, "total_gold", start, until_) - pace[c][0] * span)
                    xp = rise(c, "xp", start, until_) - pace[c][1] * span
                sign = 1.0 if team_of[c] == team else -1.0
                net["gold"] += sign * gold
                net["xp"] += sign * xp
                accounts[c] = {"team": team_of[c], "gold": round(gold), "xp": round(xp), "kills": round(own_items["kills"]),
                              "died": sum(a - 2 <= m <= end for m in falls_[c])}
            fall = [(c["camp"].split(" ")[0], team_of[champion_by_net[c["killer"]]]) for c in events["camps"]
                    if start < c["time"] <= end and c["camp"].split(" ")[0] in OBJECTIVE_GOLD and c.get("killer") in champion_by_net
                    and any(c["position"]) and (q := spot(jungler, c["time"]) or spot(jungler, a))
                    and math.dist(q, c["position"]) <= 4000]
            objectives = sum(OBJECTIVE_GOLD[n] * (1 if eq == team else -1) for n, eq in fall)
            value = net["gold"] + GOLD_PER_XP * net["xp"] + objectives
            spot_ = spot(jungler, a) or spot(jungler, b)
            # in their own jungle: on their side of the river and outside the lanes (`_zone` and `_corridor`)
            own_ = bool(spot_) and _corridor(state, *spot_) is None and \
                _zone(*spot_, pits).startswith("blue" if team == "100" else "red")
            out.append({"jungler": jungler, "team": team, "since": round(a, 1), "until": round(b, 1),
                          "x": round(spot_[0]) if spot_ else None, "z": round(spot_[1]) if spot_ else None,
                          "invaded": own_ and kinds == {"fight"},
                          "start": round(start, 1), "end": round(end, 1), "kinds": sorted(kinds),
                          "camps": alive, "gold_camps": round(face), "gold_cost": round(gold_c),
                          "xp_cost": round(xp_c), "involved": accounts,
                          "kills": sum(v["died"] for v in accounts.values() if v["team"] == rival_team),
                          "deaths": sum(v["died"] for v in accounts.values() if v["team"] == team),
                          "objectives": [n for n, eq in fall if eq == team],
                          "objectives_rival": [n for n, eq in fall if eq != team],
                          "net_gold": round(net["gold"]), "net_xp": round(net["xp"]), "value": round(value),
                          "verdict": "good" if value >= 100 else "bad" if value <= -75 else "even"})
    return sorted(out, key=lambda x: x["since"])


def main() -> None:
    state_path, match, timeline = (Path(a) for a in sys.argv[1:4])
    rows = read_state(state_path)
    if match.name != "-":  # the WP model asks for the match-v5 and its timeline, which only the API gives
        # per match; the game concepts below come from the replay and ask for nothing
        items = moment_list(json.loads(match.read_text(encoding="utf-8")), json.loads(timeline.read_text(encoding="utf-8")))
        print(f"{len(items)} moments with cost (WPA < -1)")
        for start, stretch in sorted(by_stretch(items).items()):
            print(f"\n=== the 3 most expensive from minute {start:.0f} onwards ({len(stretch)} in the stretch) ===")
            for wpa, champion, e in stretch[:3]:
                because = ", ".join(f"{d['factor']} {d['wpa']:+.1f}" for d in e["drivers"][:2])
                print(f"min {_clock(e['time']):>5} · {champion:11} {e['kind']:10} "
                      f"against {e['target']:14} WPA {wpa:+6.1f} · WP {e['wp_before']:.0f}→{e['wp_after']:.0f} · {because}")
                killer = e["target"] if e["kind"] == "DEATH" else None
                for key, value in context(rows, champion, e["time"], killer).items():
                    print(f"        {key:24} {value}")

        state = GameState(json.loads(match.read_text(encoding="utf-8")), json.loads(timeline.read_text(encoding="utf-8")))
        curve = wp_curve(state)
        at_minute = [f"min {m}: {100 / (1 + math.exp(-curve[m * 60][1])):.0f}%" for m in (5, 15, 25, 35) if m * 60 < len(curve)]
        print(f"\nblue team WP curve, {len(curve)} points · " + " · ".join(at_minute))
        print("\n=== the 5 stretches of 30 s in which a team lost value with nothing happening ===")
        winners = gains(rows)
        for points, t0, t1, gold, xp in silences(rows, state, items)[:5]:
            loses = "red" if points > 0 else "blue"
            print(f"min {_clock(t0):>5} → {_clock(t1):>5} · "
                  f"team {loses} loses {abs(points):4.1f} WP points · "
                  f"blue-red gold {gold:+.0f} · blue-red xp {xp:+.0f}")
            for champion, now, pace in culprits(rows, winners, t0, loses):
                row = next((f for f in rows[champion] if float(f["time"]) == t0), {})
                where = f"({row.get('x')}, {row.get('z')})" if row.get("x") else "—"
                situation = "dead" if row.get("alive") == "False" else f"{row.get('ally_dist') or '—'} from the ally"
                print(f"        {champion:11} gains {now:+5.1f} when their pace is {pace:+5.1f} · {situation} · in {where}")
            for champion, now, pace in culprits(rows, winners, t0, "blue" if loses == "red" else "red", 1, True):
                print(f"        {champion:11} takes it: {now:+5.1f} against their pace of {pace:+5.1f}")

        # Check: the per-second curve has to give at each minute the same as the one wpa_report produces,
        # which is the same model read per minute. If it deviates, the features are being built wrong.
        blue = next(p for p in json.loads(match.read_text(encoding="utf-8"))["info"]["participants"] if p["teamId"] == 100)
        report = wpa_report(json.loads(match.read_text(encoding="utf-8")),
                             json.loads(timeline.read_text(encoding="utf-8")), blue["puuid"], MODEL)
        ours = [100 / (1 + math.exp(-curve[min(m * 60, len(curve) - 1)][1])) for m in range(len(report.wp_curve))]
        error = max(abs(a - b) for a, b in zip(ours, report.wp_curve))
        print(f"\nper-second curve against wpa_report's: {len(report.wp_curve)} minutes, "
              f"max error {error:.2f} points")
        assert error < 1.0

    if len(sys.argv) > 4:  # the decoder's events JSON is the one that carries the camps
        with open_file(Path(sys.argv[4])) as fh:
            events = drop_revived(json.load(fh))
        print("\n=== small camps alive: what not clearing your jungle costs (up to minute 14) ===")
        for jungler, r in idle_jungle(events, rows, until=840).items():
            assert 120 <= r["period"] <= 160, r["period"]  # the respawn of the small ones hovers around 135 s
            print(f"{jungler:11} (team {r['team']}) · measured respawn {r['period']:.0f} s · "
                  f"{r['delay'] / 60:.1f} min of living camps = {r['clears_lost']:.1f} lost "
                  f"clears = {r['gold']:.0f} gold and {r['xp']:.0f} xp = {r['points']:.1f} WP points")
            for d in sorted(r["detail"], key=lambda x: -x["delay"]):
                print(f"        {d['camp']:8} {d['clears']:2} clears · {d['delay'] / 60:4.1f} min alive · "
                      f"{d['lost']:4.1f} lost clears · first respawn: {d['first_delay']:3.0f} s late")

        data = initial_push(events, rows)
        print("\n=== push of the first two waves (+1 pushes blue, -1 red) and the jungler's path ===")
        print("        " + " · ".join(f"{k}: {v:+.2f}" for k, v in data["push"].items()))
        print("        " + " · ".join(f"{j} ends the first clear in {side}" for j, side in data["paths"].items()))
        if match.name != "-":  # prio.csv stores each jungler's puuid, which is only in the match-v5
            prio = Path(__file__).with_name("prio.csv")
            save_prio(state_path.stem.replace(".state", ""), data, events,
                         json.loads(match.read_text(encoding="utf-8")), prio)
            print(f"        saved in {prio.name}: one row per jungler, to learn what prio each path asks for")

        print("\n=== strong side and weak side: resources in lane from minute 2 to 10 ===")
        lines = resources_in_lane(events, rows)
        by_champion = {r["champion"]: r for r in lines}
        for r in sorted(lines, key=lambda x: (x["lane"], x["team"])):
            balance = r["damage_done"] - r["damage_received"]
            other = by_champion.get(r["rival"], {})
            notice = ""
            if (r["side"] == "weak" and len(r["summoners"]) > len(other.get("summoners", []))
                    and (r["health_mean"] or 1) < (other.get("health_mean") or 0)):
                notice = " ← the weak one arrives with fewer resources than the rival"
            elif r["side"] == "strong" and balance < 0:
                notice = " ← the strong one loses the exchange"
            summoners = ", ".join(f"{int(t) // 60}:{int(t) % 60:02d}" for t in r["summoners"]) or "none"
            print(f"{r['champion']:11} {r['lane']:8} side {r['side']:6} against {r['rival']:11} · "
                  f"damage {r['damage_done']:5.0f} against {r['damage_received']:5.0f} ({balance:+5.0f}) · "
                  f"mean health {(r['health_mean'] or 0):.0%} (minimum {(r['health_minimum'] or 0):.0%}) · "
                  f"mean mana {(r['mana_mean'] or 0):.0%} · summoners: {summoners}{notice}")

        print("\n=== full clear: how long it takes to clear their jungle against the ladder's mean ===")
        for jungler, r in fullclear(events, Path(__file__).with_name("fullclear.csv")).items():
            clock = f"{_clock(r['ends'])}"
            if not r["whole"]:
                judgement = (f"suboptimal, not bad: clear of {r['camps']} camps, leaves "
                          f"{', '.join(r['skipped'])} (the cost shows in the living camps)")
            elif r["difference"] is None:
                judgement = "no mean for this champion in fullclear.csv"
            else:
                mean = f"{_clock(r['mean'])}"
                judgement = (f"{abs(r['difference']):.0f} s {'faster' if r['difference'] < 0 else 'slower'} "
                          f"than the mean of {mean}")
            print(f"{jungler:11} ends at {clock} · {judgement} · {' → '.join(r['order'])}")

        print("\n=== jungler recalls: gold on them and free windows ===")
        for jungler, r in jungler_recalls(events, rows).items():
            crossings = ", ".join(f"{_clock(t)} buys {d:.0f} s later" if d else
                               f"{_clock(t)} without buying" for t, d in r["crossings"])
            print(f"{jungler:11} (team {r['team']}) · max gold on them {r['max_gold']} at "
                  f"{_clock(r['when_max'])} · {r['seconds_above']} s with more "
                  f"than 1500 outside base · crossings: {crossings or '—'}")
            for a, b in r["free_windows"][:3]:
                print(f"        free window wasted {_clock(a)} → "
                      f"{_clock(b)} ({b - a:.0f} s without camps or fights)")

        print("\n=== shop before the second clear ===")
        for jungler, r in recall_before_second_clear(events, rows).items():
            starts = f"{_clock(r['starts_second'])}" if r["starts_second"] else "never"
            verdict = "well" if r["purchases"] else "CONCEPT ERROR: did not go through the shop"
            print(f"{jungler:11} first camp {r['first_camp']:8} · returns at {_clock(r['respawn'])} · starts the second clear at {starts} · "
                  f"{r['purchases']} purchases and {r['recalls']} recalls in between · "
                  f"{r['gold_unspent']} gold unspent · {verdict}")

        waves = lane_waves(events)
        assert sorted(waves["barracks"].values()) == [(side, lane) for side in ("blue", "red")
                                                     for lane in ("bot", "mid", "top")]
        assert [n for n in range(1, 13) if waves["waves"][("mid", "blue", n)]["cannon"]] == [3, 6, 9, 12]
        # only the minions still alive when the match ends are left without a killer
        assert sum(s["killed_by"] is None for s in waves["minions"].values()) < 0.1 * len(waves["minions"])
        # the corridor is drawn by the minions, so it has to collect them
        fall = [s for s in waves["minions"].values() if s["where"]]
        assert sum(_corridor(waves, *s["where"]) == s["lane"] for s in fall) > 0.95 * len(fall)
        # and the charges model can't contradict any ward that was really placed
        placed_times = collections.defaultdict(list)
        for e in events["events"]:
            if e["type"] == "CastSpell" and e["spell"] in CHARGES:
                assert _charges(placed_times[(e["net_id"], e["spell"])], *CHARGES[e["spell"]], e["time"]) >= 1
                placed_times[(e["net_id"], e["spell"])].append(e["time"])

        print("\n=== lane backs: which wave they left and what it cost (up to minute 14) ===")
        for b in backs(events, rows, waves):
            notice = " ← leaves the wave" if b["kind"] == "without clearing the wave" else ""
            print(f"{b['champion']:11} {b['lane']:4} goes back at {_clock(b['time'])} "
                  f"with wave {b['wave']:2d} cleared · {b['kind']:21} · loses "
                  f"{b['cs_lost']:2d} of the {b['cs_in_play']:2d} minions of the next minute{notice}")

        print("\n=== frozen waves: who holds it and what it costs the opponent ===")
        towers = _towers(events, waves)
        for c in freezes(events, waves, rows):
            print(f"{', '.join(c['who']):11} {c['lane']:4} freezes from {_clock(c['since'])} to {_clock(c['until'])} "
                  f"({c['until'] - c['since']:.0f} s) · advance {c['advance']:.2f} (their tower is at "
                  f"{towers[(c['lane'], c['side'])]:.2f}) · {c['difference']:.0f} minions "
                  f"fewer · the rival loses {c['rival_cs_lost']} of {c['rival_cs']}")

        print("\n=== stacks: what is done with the clash window and who reaches the bounce ===")
        clashes = stacks(events, waves, rows)
        assert all(c["waves"] == list(range(c["waves"][0], c["waves"][-1] + 1)) for c in clashes if c["stack"])
        for c in clashes:
            what = ("STACK of waves " + " and ".join(str(o) for o in c["waves"])) if c["stack"] else "loose wave"
            late = [n for n, arrives in c["arrive"].items() if not arrives]
            bounce = (f"bounces at {_clock(c['bounce'])}"
                      + (f", and {' and '.join(late)} {'is' if len(late) == 1 else 'are'} not there"
                         if late else ", and they arrive")) if c["bounce"] else "without bounce"
            print(f"{c['lane']:4} {c['side']:5} clashes from {_clock(c['time'])} to "
                  f"{_clock(c['ends'])} with {c['minions']:2d} minions · {what:26} · "
                  + ", ".join(f"{n} {v}" for n, v in c["do"].items())
                  + f" · {bounce} · loses {c['cs_lost']} CS"
                  + (" ← the stack plays itself" if c["stack"] and late else ""))

        print("\n=== accumulations: who builds a slow push and how it ends ===")
        for a in accumulations(events, waves, rows):
            final = []
            if a["clash"]:
                final.append(f"clashes at {_clock(a['clash'])}")
            if a["freezes"]:  # freezing is eating it slowly: the two labels would be the same thing
                final.append(f"held by {' and '.join(a['freezes'][0])} from "
                             f"{_clock(a['freezes'][1])}")
            elif a["come"]:
                final.append(f"{a['come'][0]} eats it ({a['come'][1]} of {a['minions']} minions)")
            print(f"{a['lane']:4} {a['side']:5} piles up from {_clock(a['since'])} to "
                  f"{_clock(a['until'])} up to {a['peak']:+d} minions · "
                  + (" · ".join(final) or "falls apart without reaching anything")
                  + ("" if a["clash"] else " ← the slow push does not reach the tower"))

        print("\n=== what each one does with the prio of their crash ===")
        used = payoff(events, waves, rows, clashes)
        alive = [u for u in used if not u["dead"]]
        # if it turns out nobody takes advantage of any crash, what's broken is the table, not the players
        assert sum(bool(u["uses"]) for u in alive) > len(alive) / 2
        for u in used:
            judgement = ("" if u["uses"] else "  ← dead, there was no prio to spend" if u["dead"]
                      else f"  ← SUBOPTIMAL: gives it no use ({u['hidden']} s in the fog, "
                           + ("and with a ward to place it)" if u["could_ward"] else "without a ward to place)"))
            print(f"{u['champion']:11} {u['lane']:4} crash at {_clock(u['time'])}"
                  f"{' (stack)' if u['stack'] else '        '} · "
                  + (", ".join(u["uses"]) or "nothing") + judgement)
        bad = [u for u in alive if not u["uses"]]
        print(f"        {len(alive) - len(bad)} of {len(alive)} crashes with a use · {len(bad)} suboptimal")

        print("\n=== blind in the rival's field: not knowing where the enemy jungler is ===")
        for r in sorted(exposure(events, waves, rows),
                        key=lambda x: -(x.get("half_rival_blind", 0) + x.get("overextend_blind", 0))):
            blind = r.get("half_rival_blind", 0) + r.get("overextend_blind", 0)
            deaths = ", ".join(f"{_clock(t)}" for t in r["blind_deaths"])
            print(f"{r['champion']:11} {r['lane']:4} against {r['rival_jungler']:11} · "
                  f"{r.get('half_rival', 0) + r.get('overextend', 0):3d} s in rival field, {blind:3d} blind "
                  f"({r.get('half_rival_no_river', 0) + r.get('overextend_no_river', 0):3d} without river, "
                  f"{r.get('half_rival_with_the_wave', 0) + r.get('overextend_with_the_wave', 0):3d} with the wave "
                  f"ahead) · blind overextend {r.get('overextend_blind', 0):2d} s · "
                  f"the jungler was on top of them {r.get('half_rival_and_was', 0) + r.get('overextend_and_was', 0):2d} s"
                  + (f" · dies there at {deaths}" if deaths else ""))

        print("\n=== the jungler unseen, and what showing up gets ===")
        for j in show_up(events, waves, rows):
            is_alive = j["invisible"] + j["visible"]
            # the jungler lives hidden: if this flips, what's broken is the `seen` column
            assert j["invisible"] > j["visible"], j["jungler"]
            in_lane = [v for v in j["windows"] if v["near"]]
            bucket = [v for v in in_lane if not v["wins"]]
            print(f"{j['jungler']:11} (team {j['team']}) · invisible {j['invisible']} of {is_alive} s "
                  f"({j['invisible'] / is_alive:.0%}), longest streak {j['streak_invisible']} s · "
                  f"seen {len(j['windows'])} times, {len(in_lane)} in a lane and {len(bucket)} of those taking nothing")
            for v in j["windows"]:
                standing = ", ".join(v["standing"])
                print(f"        {_clock(v['since'])}–{_clock(v['until'])} ({v['until'] - v['since'] + 1:2d} s) "
                      + (f"through {v['lane']:4} (within reach of {', '.join(v['near'])})" if v["near"] else "far from everyone")
                      + " · " + (" · ".join(v["wins"]) or "takes nothing")
                      + (f" · and with {standing} idle" if standing else "")
                      + ("  ← shown for nothing" if v["near"] and not v["wins"] else ""))

        print("\n=== vision: what information each ward produces ===")
        timeline_data = json.loads(timeline.read_text(encoding="utf-8")) if timeline.name != "-" else None
        line = _tower_line(events, waves, timeline_data)
        # the two lines, one on each side of the river, in the three lanes
        assert all(line("100", c, 0) < RIVER < line("200", c, 0) for c in ("top", "mid", "bot"))
        for v in sorted(vision(events, waves, rows, timeline_data), key=lambda x: (x["team"], x["position"])):
            if not v["wards"]:
                continue
            print(f"{v['champion']:11} {v['position']:8} · {len(v['wards']):2d} wards, {v['useful']:2d} show "
                  f"someone ({v['seconds_of_info']:3d} s of information, {v['to_jungler']} see the rival "
                  f"jungler) · {len(v['backs_with_charges'])} backs with the ward bar full")
            for d in v["wards"]:
                if not d["past_the_lane"]:
                    continue  # up to the enemy's line it is normal warding: it only goes in the summary
                judgement = ("with prio" if d["with_prio"] else
                          "no prio, suboptimal but it does not count: it is the support" if v["exempt"] else
                          "NO PRIO, had not earned it")
                print(f"        {_clock(d['when']):>5} {d['kind']:8} past the rival's line, "
                      f"{d['depth']:+4.0%} of the river · " + judgement
                      + f" · lives {d['lives']:3.0f} s · "
                      + ("shows " + ", ".join(d["reveals"]) if d["reveals"] else "shows nobody"))

        print("\n=== lane gold at minute 14: minions and plates ===")
        by_champion = {r["champion"]: r for r in gold_in_lane(events, rows, timeline_data)}
        for r in sorted(by_champion.values(), key=lambda x: (x["lane"], x["team"])):
            other = by_champion.get(r["rival"], {})
            print(f"{r['champion']:11} {r['lane']:4} · {r['cs']:3d} cs and {r['plates']} plates = "
                  f"{r['gold']:5d} gold · against {r['rival']:11} "
                  f"{r['cs'] - other.get('cs', 0):+4d} cs, {r['gold'] - other.get('gold', 0):+5d} gold")

        print("\n=== trades: what each one spends, how it ends and what the wave does ===")
        changes = trades(events, waves, rows)
        for lane in ("top", "mid", "bot"):
            own_items = [t for t in changes if t["lane"] == lane]
            spends = collections.Counter()
            for t in own_items:
                for side in t["sides"].values():
                    for c, d in side["champions"].items():
                        spends[c] += len(d["summoners"])
            print(f"{lane:4} · {len(own_items):2d} trades · burned summoners: "
                  + (", ".join(f"{c} {n}" for c, n in spends.items() if n) or "none"))
            for t in own_items:
                notable = [c for side in t["sides"].values() for c, d in side["champions"].items()
                           if d["summoners"]] + [c for side in t["sides"].values() for c in side["died"]]
                if not notable:
                    continue
                pieces = []
                for side in t["sides"].values():
                    for c, d in side["champions"].items():
                        if not d["damage"] and not d["abilities"]:
                            continue
                        pieces.append(f"{c} {(d['health_before'] or 0):.0%}→{(d['health_after'] or 0):.0%} "
                                      f"({d['damage']:.0f} damage, {d['abilities']} spells"
                                      + (", " + "+".join(d["summoners"]) if d["summoners"] else "") + ")")
                died = [c for side in t["sides"].values() for c in side["died"]]
                print(f"        {_clock(t['since'])}–{_clock(t['until'])} · " + " · ".join(pieces)
                      + (f" · the wave moves {t['wave']:+.2f} toward red" if t["wave"] else "")
                      + (" · DIES " + ", ".join(died) if died else ""))

        print("\n=== lane departures: where each lane's advantage goes ===")
        all_ = departures(events, waves, rows)
        # a laner spends more time in their lane than out: if this flips, what's broken is the corridor
        for champion, own_rows in itertools.groupby(sorted(all_, key=lambda s: s["champion"]),
                                                 key=lambda s: s["champion"]):
            assert sum(s["until"] - s["since"] for s in own_rows) < 360, champion
        for s in all_:
            print(f"{s['champion']:11} {s['position']:8} {_clock(s['since'])}–{_clock(s['until'])} "
                  f"({s['until'] - s['since'] + 1:3d} s) → {s['where_to']:16} · "
                  + ("with the wave pushed" if s["won"] else "WITHOUT the wave, it is an escape")
                  + " · with " + (", ".join(s["together"]) or "nobody") + " · "
                  + (" · ".join(s["wins"]) or "takes nothing")
                  + f" · {s['cs_lost']} minions escape"
                  + ("  ← leaves without having earned it and without getting anything" if not s["won"] and not s["wins"] else ""))

        # sidelanes uses the match only to set each one's position; without it it infers it from the lane
        game = json.loads(match.read_text(encoding="utf-8")) if match.name != "-" else None
        print("\n=== side lanes from minute 14: push what you can without dying ===")
        turns = sidelanes(events, waves, rows, game)
        assert all(0 <= t["uncounted"] <= 5 for t in turns if t["uncounted"] is not None)
        for champion, own_items in itertools.groupby(sorted(turns, key=lambda t: t["champion"]),
                                                 key=lambda t: t["champion"]):
            own_items = list(own_items)
            if len(own_items) < 2:
                continue
            print(f"{champion:11} · {len(own_items):2d} turns, {sum(t['until'] - t['since'] for t in own_items):4d} s "
                  f"alone in a sidelane · {sum(t['clash'] for t in own_items):3d} minions to the rival tower · "
                  f"{statistics.median(t['uncounted'] for t in own_items):.0f}/5 rivals unaccounted for (median) "
                  f"· {sum(t['died'] for t in own_items)} deaths there")
            for t in own_items:
                if t["uncounted"] < 4 and not t["died"] and t["clash"] < 6:
                    continue  # normal turns only count in the summary
                ready = ", ".join(x for x, v in (("ulti", t["ulti"]), ("Teleport", t["tp"])) if v)
                print(f"        {_clock(t['since'])}–{_clock(t['until'])} {t['lane']:3} · "
                      f"{t['uncounted']:.0f}/5 uncontrolled · with {ready or 'nothing'} ready · "
                      f"{t['clash']} minions to the tower · +{t['cs']} cs · "
                      + (f"answers {', '.join(t['answers'])}" if t["answers"] else "nobody answers")
                      + ("  ← DIES there" if t["died"] else ""))

        print("\n=== what dying costs, by position (from minute 14 to the end) ===")
        for r in sorted(cost_of_dying(events, rows), key=lambda x: -x["gold_lost"]):
            assert not r["deaths"] or 25 <= r["respawn_mean"] <= 80, r
            print(f"{r['champion']:11} {r['position']:8} · {r['deaths']:2d} deaths and {r['seconds_dead']:3d} s "
                  f"dead (respawns in {r['respawn_mean']:4.1f} s) · produces {r['gold_per_second'] * 60:5.0f} "
                  f"gold and {r['damage_per_second'] * 60:5.0f} damage per minute · stops making "
                  f"{r['gold_lost']:5d} gold and {r['damage_lost']:6d} damage"
                  + (f" · recovers {r['charges_recovered']:.1f} ward charges meanwhile"
                     if r["charges_recovered"] >= 1 else ""))

        print("\n=== overgrouping: minions that die on their own under a side lane's turret ===")
        # the turret that finishes a minion is always the other team's: nobody eats their own
        turrets = {e["net_id"] for e in events["events"]
                    if e["type"] == "SetSpell" and "Turret" in (e.get("name") or "")}
        owner_of = {p["net_id"]: p["team"] for p in events["players"]}
        assert all(owner_of.get(s["farm"]) in (None, "200" if s["side"] == "blue" else "100")
                   for s in waves["minions"].values() if s["killed_by"] in turrets)
        thrown = collections.Counter()
        for o in overgroup(events, waves, rows, timeline_data):
            thrown[o["team"]] += o["gold"]
            print(f"{o['lane']:4} team {o['team']} · {_clock(o['since'])}–{_clock(o['until'])} · "
                  f"{o['minions']:2d} minions dead under their tower with nobody collecting them "
                  f"(about {o['gold']:3d} gold) · and {o['together']} of them grouped elsewhere")
        for team, gold in sorted(thrown.items()):
            print(f"        team {team}: about {gold} gold thrown away for not going to collect the sidelane")

        print("\n=== the side lane as a global computation: what it costs to leave it until someone goes ===")
        # nobody collects their own minions: if this breaks, side and team have been crossed
        assert not [s for s in waves["minions"].values() if s["farm"]
                    and owner_of.get(s["farm"]) == ("100" if s["side"] == "blue" else "200")]
        costs = collections.Counter()
        for b in side_balance(events, waves):
            costs[b["team"]] += b["gold_lost"]
            closes = (f"collects it on wave {b['closes']} with {b['recovers']} minions"
                      if b["closes"] else "nobody collects it until the end")
            print(f"{b['lane']:4} team {b['team']} · waves {b['waves'][0]}–{b['waves'][1]} "
                  f"({_clock(b['since'])}–{_clock(b['until'])}) · leaves {b['lost']:2d} minions "
                  f"uncollected, about {b['gold_lost']:4d} gold · the rival takes {b['rival_collects']:2d} "
                  f"of that lane · balance {b['balance']:+5d} · their wave reaches {b['piles']:+3d} "
                  f"minions · {closes}")
        for team, gold in sorted(costs.items()):
            print(f"        team {team}: about {gold} gold in sidelanes left")

        print("\n=== zone control: vision and punishments per sector ===")
        pits = _pits(events)
        assert len(pits) == 2 and math.dist(*pits.values()) > 7000, pits  # both, and one in each river
        # the river's width is measured with the crab: if any falls outside, it falls short
        assert all(_zone(*c["position"], pits).startswith(("river", "pit"))
                   for c in events["camps"] if c["camp"] == "Scuttle")
        sectors = zones(events, waves, rows)
        assert not [c for r in sectors for c in r["punishments"] if c["victim"] in c["catchers"]]
        for r in sorted(sectors, key=lambda x: (x["zone"], x["team"])):
            if not (r["ward_seconds"] or r["punishments"]):
                continue
            who = ", ".join(f"{c} {n}" for c, n in r["who"].most_common(3))
            print(f"{r['zone']:16} team {r['team']} · {r['ward_seconds']:4d} s with a living ward inside "
                  f"({r['control_wards']} control) · {r['presence']:4d} s with one of theirs · "
                  f"{len(r['punishments']):2d} punished facechecks"
                  + (f" ({who})" if who else "") + f" · {r['deaths']} deaths of theirs there")
        for c in sorted([c for r in sectors for c in r["punishments"]], key=lambda x: x["time"]):
            if not c["died"]:
                continue
            print(f"        {_clock(c['time'])} {c['zone']:16} · {', '.join(c['catchers'])} catch "
                  f"{c['victim']}, who enters alone, and kill them")

        print("\n=== preparation of each objective: the minute and a half before ===")
        punished = [c for r in sectors for c in r["punishments"]]
        for o in setups(events, waves, rows, punished):
            assert all(x["in_the_pit"] <= x["ward_seconds"] <= 91 and x["presence"] <= 91
                       for x in o["sides"].values()), o  # the pit is part of the area, never more
            print(f"{_clock(o['falls']):>5} {o['objective']:16} · team {o['takes_it']} takes it")
            for team, x in sorted(o["sides"].items()):
                who = ", ".join(f"{c} {n}" for c, n in sorted(x["work"].items(), key=lambda y: -y[1]))
                print(f"        team {team}{'  ←' if o['takes_it'] == team else '   '} "
                      + (f"arrives {x['arrives']:2d} s at the pit" if x["arrives"] is not None else "NO ARRIVAL    ")
                      + f" · {x['ward_seconds']:2d} s of vision in the area ({x['in_the_pit']} in the pit, "
                      + f"{x['in_the_river']} in the river), {x['control_wards']} control"
                      + (f", {x['punishments']} punishments" if x["punishments"] else "")
                      + " · prepared by " + (who or "nobody")
                      + (f" · the duo puts in {x['duo']:.0%}" if x["duo"] is not None else "")
                      + ("  ← the duo does not show up" if x["duo"] == 0 else ""))


if __name__ == "__main__":
    main()
