"""Win probability (WP) second by second, with the game state given by the replay.

    python research/replays/wp_per_second.py <harvest folder> <matches.jsonl.gz> <output folder>
                                          [--processes 3]

The app's model (`ygg_core.metrics.wpa`) sees the match as the API's timeline gives it: one frame per
minute with gold and XP, and the events (kills, turrets, objectives). With that it values kills and
objectives well, but not what happens in between —a roam, a flash, a fight that doesn't end in a kill—, because it doesn't see
where anyone is nor what they arrive with. The replay does: each second, the position, health, mana, spells and
who sees whom. This builds a per-second WP from that and compares it with the app's over the same
seconds of the same matches.

Two steps; the first is only done if `wp_per_second.npz` is missing from the output folder:

1. **Extract**: one state every `STEP` seconds of each match, seen from the blue team, with two vectors:
   the app's 17 features computed by the app itself with the timeline (`GameState.features`), and the new one
   (`ALL_FEATURES`, see `one_game`). The league comes from `matches.jsonl.gz`, which is also where the timeline comes from:
   turrets don't appear in the replay (they send no `UnitDeath`), so turrets, inhibitors and epics are the
   timeline's events, which are already exact to the millisecond and go on the same clock as the replay.
2. **Fit and evaluate**: one logistic regression per stretch of the match, like the app's (`analyse.logistic_fit`),
   validated with 5 folds **per match** and stratified by league. The final model blends neighbouring stretches
   according to the minute (`logits`, `smooth`); how much the league weighs is measured (`scales`) but doesn't enter it, because
   out of fold it doesn't improve (neither as a scale nor multiplying each feature). It prints in markdown the
   tables from which `wp-per-second.md` comes and stores the coefficients in `model.json`. A gradient boosting
   (scikit-learn, tried separately) doesn't improve on the logistic regression: see the report.

`states` is the first step for an already-read match and with whatever step is wanted: `value.py` uses it every
second, with what each champion puts into each feature (`_own`), to value situations and split them.

Without a mirror, unlike `export_wpa_model.py`: training with each state and its reflection is the same as
training without an intercept, and the intercept here serves a purpose, it is blue side's advantage. What the
reflection doesn't change is that a symmetric feature (equal for both teams: the minute, the league, how long until the dragon)
need not favour a side: what it can do is change how much the others weigh. That is why the timers enter
multiplying other features, and the league is tried by multiplying each feature or scaling the log-odds.
"""

from __future__ import annotations

import collections
import csv
import gzip
import json
import math
import re
import sys
import zlib
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import moments as M
import numpy as np
from leagues import LEAGUES
from ygg_core.metrics.wpa import FEATURES, PHASES, GameState
from ygg_core.metrics.wpa_model import MODEL
from ygg_core.timeline.objectives import OBJECTIVE_PIT_POSITIONS, OBJECTIVE_RADIUS

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ladder"))
from analyse import auc, logistic_fit
from export_wpa_model import as_riot, fit_non_negative

STEP = 10  # one state every 10 s: consecutive ones of the same match say almost the same thing
# The decoder only writes a value when it changes, and until the minute the total gold is blank in three of every
# four rows (at 90 s, in none). Nothing has happened before either: the first wave arrives at 65 s.
FROM = 90
FOLDS = 5

# When each objective spawns, in replay seconds (the same clock as the timeline): measured in the harvest with
# its `SpawnNeutral`, not set by hand, and checked in each match on extraction (`_timer_offset`). The dragon
# spawns at 294 and comes back 293.5 s after falling; from the soul the one that spawns is the elder, 353.5 s after
# the previous falls; the baron spawns at 1180 and comes back 340 s later.
DRAGON, ANCESTRAL, BARON = (294.0, 293.5), 353.5, (1180.0, 340.0)
WARNING = 60.0  # from a minute before it spawns, it is already played for
DRAGON_PIT, BARON_PIT = OBJECTIVE_PIT_POSITIONS["DRAGON"], OBJECTIVE_PIT_POSITIONS["BARON_NASHOR"]

# The app's 16 features without the minute (the stretch already carries it), with gold, XP, kills and dead measured in the
# replay at that second; the objectives are the same events it uses.
MACRO = FEATURES[:-1]
NEW_FEATURES = ("levels", "unspent_k", "respawn", "rival_side", "seen", "wards", "health", "mana",
          "summoners", "ults", "dead_dragon", "dead_elder", "dead_baron",
          "pit_dragon", "pit_baron", "fight", "health_in_fight")
ALL_FEATURES = MACRO + NEW_FEATURES
GROUPS = {  # to measure what each new thing contributes by removing it
    "fine economy (levels, unspent gold)": ("levels", "unspent_k"),
    "respawn time": ("respawn",),
    "position (rival field, pits)": ("rival_side", "pit_dragon", "pit_baron"),
    "vision (seen, wards)": ("seen", "wards"),
    "resources (health, mana, summoners, ults)": ("health", "mana", "summoners", "ults"),
    "timers by dead": ("dead_dragon", "dead_elder", "dead_baron"),
    "fight in progress": ("fight", "health_in_fight"),
}
# At this distance from an enemy one is fighting or about to: the range of almost any ability.
# ponytail: a fixed radius; the fine way would be each champion's range, which Data Dragon asks for
FIGHT = 1200.0
TIMELINE = ("CHAMPION_KILL", "BUILDING_KILL", "ELITE_MONSTER_KILL", "TURRET_PLATE_DESTROYED")  # what GameState reads


# ── Extraction ────────────────────────────────────────────────────────────────


def _n(v: str) -> float:
    return float(v) if v else 0.0


# How far each value of a champion can go. Very occasionally the emulator reads uninitialised memory and
# a gold of 1e27 comes out (5 values in 1.8 million rows): a single one is enough for the logistic regression not to
# converge. Those are replaced by that champion's last good one, from the previous second.
LIMITS = {"total_gold": 1e5, "gold": 1e5, "xp": 1e5, "level": 30}


def _seconds(path: Path, step: int = STEP) -> dict[int, list[dict[str, str]]]:
    """The state rows for the seconds looked at (one out of every `step`). `read_state` loads the whole
    table: 20,000 dictionaries per match to use one in every `STEP`."""
    out = collections.defaultdict(list)
    good_: dict[tuple[str, str], str] = {}
    with M.open_file(path) as fh:
        reader = csv.reader(fh)
        header = next(reader)
        for raw in reader:
            row = dict(zip(header, raw, strict=True))
            for col, cap in LIMITS.items():
                if row[col] and not 0 <= float(row[col]) <= cap:
                    row[col] = good_.get((row["net_id"], col), "")
                elif row[col]:
                    good_[(row["net_id"], col)] = row[col]
            t = int(float(row["time"]))
            if t >= FROM and t % step == 0:
                out[t].append(row)
    return out


def _spawns_in(objectives, t: float) -> tuple[float, bool, float]:
    """(seconds until the next dragon, whether that one is the elder, seconds until the next baron). 0 means
    it is alive. It comes from the objectives already fallen and the rules of `DRAGON`, `ANCESTRAL` and `BARON`: past only."""
    dragon, soul, baron = DRAGON[0], False, BARON[0]
    for o in objectives:
        if o.time >= t * 1000:
            break
        if o.kind.startswith("DRAGON") or o.kind == "ELDER":
            soul = soul or o.kind == "DRAGON_4"
            dragon = o.time / 1000 + (ANCESTRAL if soul else DRAGON[1])
        elif o.kind == "BARON_NASHOR":
            baron = o.time / 1000 + BARON[1]
    return max(0.0, dragon - t), soul, max(0.0, baron - t)


def _timer_offset(events: dict, objectives) -> list[float]:
    """Seconds between what `_spawns_in` says and when each dragon and baron really spawns (its `SpawnNeutral`)."""
    out = []
    for e in events["events"]:
        name = e.get("character", "").lower() if e["type"] == "SpawnNeutral" else ""
        if "dragon" in name or "baron" in name:
            dragon, _soul, baron = _spawns_in(objectives, e["time"] - 1)
            out.append(e["time"] - 1 + (dragon if "dragon" in name else baron) - e["time"])
    return out


def _champion(f: dict[str, str], t: float, end: dict[str, float]) -> collections.Counter:
    """A champion's state at that second (their row of the table); `_teams` sums it per team."""
    s, side = collections.Counter(), "blue" if f["team"] == "100" else "red"
    s["gold"] += _n(f["total_gold"])
    s["xp"] += _n(f["xp"])
    level = _n(f["level"]) or 1.0  # blank until the first level-up: a third of the rows at 2 min
    s["level"] += level
    s["unspent"] += _n(f["gold"])
    for what, maximum in (("health", "health_max"), ("mana", "mana_max")):
        s[what + "_k"] += _n(f[maximum]) > 0  # carries that resource, alive or dead: to split the mean (`_own`)
    if f["alive"] != "True":
        s["respawn"] += max(0.0, end.get(f["net_id"], t) - t)
        return s
    x, z = _n(f["x"]), _n(f["z"])
    s["alive"] += 1
    s["rival_side"] += M._depth(x, z, side) > M.RIVER_WIDTH / M.RIVER  # past the river, not in it
    s["seen"] += f["seen"] == "True"  # visible to the other team
    s["summoners"] += (f["d_ready"] == "True") + (f["f_ready"] == "True")
    s["ults"] += level >= 6 and f["r_ready"] == "True"
    s["pit_dragon"] += math.dist((x, z), DRAGON_PIT) <= OBJECTIVE_RADIUS
    s["pit_baron"] += math.dist((x, z), BARON_PIT) <= OBJECTIVE_RADIUS
    # health and mana as a share of the maximum; outside [0, 1] it is uninitialised memory (see leagues.FRACTIONS)
    share = {}
    for what, current, maximum in (("health", "health", "health_max"), ("mana", "mana", "mana_max")):
        if _n(f[maximum]) > 0:
            share[what] = min(1.0, max(0.0, _n(f[current]) / _n(f[maximum])))
            s[what] += share[what]
            s[what + "_n"] += 1
    if f["enemy_dist"] and _n(f["enemy_dist"]) <= FIGHT:  # the nearest living enemy, in range
        s["fight"] += 1
        s["health_in_fight"] += share.get("health", 1.0)
    return s


def _teams(by: dict[str, collections.Counter], team: dict[str, str]) -> dict[str, collections.Counter]:
    """Each team's state at that second, summed over its five champions."""
    total = {"100": collections.Counter(), "200": collections.Counter()}
    for c, s in by.items():
        total[team[c]].update(s)
    return total


def _share(s: collections.Counter, eq: collections.Counter, what: str) -> float:
    """A champion's share in their team's mean (`what`: health or mana, among the living): theirs if they are
    alive and the team mean if they are dead, among those who carry that resource. The mean is summed, and what
    moves it when someone dies (removing from the count one with low health raises it) belongs to the one who dies, not the others."""
    if not s[what + "_k"] or not eq[what + "_k"]:
        return 0.0
    mean = eq[what] / eq[what + "_n"] if eq[what + "_n"] else 1.0
    return (s[what] if s[what + "_n"] else mean) / eq[what + "_k"]


def _own(s: collections.Counter, falls: int, wards: int, eq: collections.Counter, w_dragon: float,
          w_baron: float, soul: bool) -> list[float]:
    """What a champion puts into each `ALL_FEATURES` feature, in favour of their team (`eq`, their team's, for
    health and mana, which are means: `_share`). Blue's vector is the sum of its five minus that of the
    red ones, except what comes from the timeline (here 0) and the mana of a team in which nobody carries it (there the
    mean is 1): it is what allows splitting a WP change among the champions, because the model is linear."""
    v = s["alive"]
    return [s["gold"] / 1000, s["xp"] / 1000, -falls, v, *[0.0] * (len(MACRO) - 4),
            s["level"], s["unspent"] / 1000, -s["respawn"] / 10, s["rival_side"], -s["seen"], wards,
            _share(s, eq, "health"), _share(s, eq, "mana"),
            s["summoners"], s["ults"], v * w_dragon * (not soul), v * w_dragon * soul, v * w_baron,
            s["pit_dragon"] * w_dragon, s["pit_baron"] * w_baron, s["fight"], s["health_in_fight"]]


def one_game(pair: tuple[dict, str, str]) -> dict:
    """A match's states: (seconds, new features, the app's features) and who wins.

    The new features, all blue's minus red's (or in blue's favour):

    - `levels` and `unspent_k`: the sum of levels, which weighs in steps (the R at 6) and not like XP, and the
      unspent gold, which is in the total gold but is not yet strength;
    - `respawn`: the tens of seconds remaining for red's dead minus blue's, from the replay's exact `Death`
      (the app's model estimates them with the wiki formula);
    - `rival_side`: living past the river toward the enemy base, which is pressure (or exposure);
    - `seen`: enemies in view minus their own in the enemy's view, the information at that moment, and
      `wards`: each team's live wards (`moments._wards`);
    - `health` and `mana`: the mean of the living as a share of the maximum; `summoners` and `ults`: those of the
      living that are ready (the R from level 6);
    - the timers: how long until the dragon and the baron is the same for both, so it only enters weighing
      something else: `dead_dragon`, `dead_elder` and `dead_baron` are the extra living (`dead`) when the
      objective is alive or spawns in less than `WARNING` s (with a weight rising from 0 to 1 over that minute), and
      `pit_dragon` and `pit_baron`, the extra living within 2500 of the pit, with the same weight;
    - the fight in progress: `fight`, how many of each team have a living enemy within `FIGHT` (who arrives
      with more people), and `health_in_fight`, the summed health (share of maximum) of those, which is who is winning
      before anyone falls."""
    record, state_path, events_path = pair
    with M.open_file(Path(events_path)) as fh:
        events = M.drop_revived(json.load(fh))
    return {"game": record["match_id"], "league": record["tier"],
            **states(record, events, _seconds(Path(state_path)))}


def states(record: dict, events: dict, rows: dict[int, list[dict[str, str]]], own_items: bool = False) -> dict:
    """`one_game`'s with the match already read: `rows` are those of `_seconds`, with whatever step is wanted.
    With `own_items`, also what each champion puts into each feature (`_own`), in the order of `events["players"]`."""
    blue_wins = next(e["win"] for e in record["teams"] if e["teamId"] == 100)
    from_replay = any(s.get("WIN") == "Win" for p, s in zip(events["players"], events["stats"], strict=True)
                     if p["team"] == "100")
    if blue_wins != from_replay:
        raise ValueError("the timeline and the replay don't give the same winner")
    state = GameState(*as_riot(record))
    team = {p["net_id"]: p["team"] for p in events["players"]}
    champion = {p["net_id"]: p["champion"] for p in events["players"]}
    team_of = {p["champion"]: p["team"] for p in events["players"]}
    deaths = sorted((e["time"], e["net_id"], e["time"] + e["respawn_time"]) for e in events["events"]
                     if e["type"] == "Death" and e["net_id"] in team)
    wards = [(t0, t1, eq, who) for t0, t1, _where, eq, who in M._wards(events)]

    ts, xs, apps, by_champion = [], [], [], []
    end, kills, falls, i = {}, collections.Counter(), collections.Counter(), 0
    for t in sorted(rows):
        if len(rows[t]) != 10:
            continue
        while i < len(deaths) and deaths[i][0] < t:
            _t, net, until = deaths[i]
            end[net] = until
            kills[team[net]] += 1
            falls[champion[net]] += 1
            i += 1
        by = {f["champion"]: _champion(f, t, end) for f in rows[t]}
        s = _teams(by, team_of)
        az, rj = s["100"], s["200"]

        def diff(k: str, az=az, rj=rj) -> float:
            return az[k] - rj[k]

        def mean(k: str, az=az, rj=rj) -> float:
            return (az[k] / az[k + "_n"] if az[k + "_n"] else 1.0) - (rj[k] / rj[k + "_n"] if rj[k + "_n"] else 1.0)

        app = state.features(t * 1000, MODEL.event_gold)
        dragon, soul, baron = _spawns_in(state.objectives, t)
        w_dragon, w_baron = (min(1.0, max(0.0, 1 - s_ / WARNING)) for s_ in (dragon, baron))
        dead = diff("alive")  # as in the app: red's dead minus blue's dead
        xs.append([diff("gold") / 1000, diff("xp") / 1000, kills["200"] - kills["100"], dead, *app[4:16],
                   diff("level"), diff("unspent") / 1000, (rj["respawn"] - az["respawn"]) / 10,
                   diff("rival_side"), rj["seen"] - az["seen"],
                   sum(1 if eq == "100" else -1 for t0, t1, eq, _q in wards if t0 <= t < t1),
                   mean("health"), mean("mana"), diff("summoners"), diff("ults"),
                   dead * w_dragon * (not soul), dead * w_dragon * soul, dead * w_baron,
                   diff("pit_dragon") * w_dragon, diff("pit_baron") * w_baron,
                   diff("fight"), diff("health_in_fight")])
        if own_items:
            placements = collections.Counter(q for t0, t1, _eq, q in wards if t0 <= t < t1)
            by_champion.append([_own(by[p["champion"]], falls[p["champion"]], placements[p["champion"]],
                                      s[p["team"]], w_dragon, w_baron, soul) for p in events["players"]])
        apps.append(app)
        ts.append(t)
    out = {"wins": float(blue_wins), "t": np.array(ts, np.int32), "x": np.array(xs, np.float32),
             "app": np.array(apps, np.float32), "offset": _timer_offset(events, state.objectives)}
    if own_items:
        out["own_items"] = np.array(by_champion, np.float32).reshape(len(ts), len(events["players"]), len(ALL_FEATURES))
    return out


def task(pair: tuple[dict, str, str]) -> dict:
    try:
        return one_game(pair)
    except Exception as e:  # a strange match can't stop five thousand
        return {"game": pair[0]["match_id"], "error": f"{type(e).__name__}: {e}"}


def records(games: Path, which_ones: set[str]) -> dict[str, dict]:
    """The timeline and league of the matches in `which_ones` (with the replay's name, EUW1-123), trimmed to what
    `GameState` reads before sending it to the processes: whole it is 250 MB compressed."""
    out = {}
    with gzip.open(games, "rt", encoding="utf-8") as fh:
        for line in fh:
            game = re.search(r'"match_id":\s*"([^"]+)"', line[:80]).group(1).replace("_", "-")
            if game not in which_ones:
                continue
            r = json.loads(line)
            if r.get("remake"):
                continue
            r["events"] = [e for e in r["events"] if e["type"] in TIMELINE]
            r["participants"] = [{k: p.get(k) for k in ("participantId", "teamId", "puuid", "championName")}
                                 for p in r["participants"]]
            out[game] = r
    return out


def extract(harvest: Path, games: Path, dest: Path, processes: int) -> None:
    """The harvested matches with their timeline and league → `dest` (.npz)."""
    replays = {p.name.split(".")[0]: p for p in harvest.glob("*.state.csv.gz")
               if (harvest / p.name.replace(".state.csv.gz", ".events.json.gz")).exists()}
    pairs = [(r, str(replays[p]), str(harvest / f"{p}.events.json.gz"))
             for p, r in records(games, set(replays)).items()]
    print(f"{len(replays)} replays · {len(pairs)} with timeline and league · {processes} processes", flush=True)

    parts, bad_ones, offsets = [], [], []
    with ProcessPoolExecutor(processes) as pool:
        for i, r in enumerate(pool.map(task, pairs, chunksize=4), 1):
            if "error" in r:
                bad_ones.append(r)
                print(f"  ERROR {r['game']}: {r['error']}", flush=True)
            elif len(r["t"]):
                parts.append(r)
                offsets += r["offset"]
            if i % 250 == 0 or i == len(pairs):
                print(f"  {i}/{len(pairs)} · {sum(len(p['t']) for p in parts):,d} states", flush=True)
    offsets = np.abs(np.array(offsets))
    print(f"timers: {np.mean(offsets <= 2):.1%} of {len(offsets):,d} dragon and baron spawns within ≤ 2 s of the "
          f"rule (median {np.median(offsets):.1f} s)")
    if bad_ones:
        print(f"{len(bad_ones)} games left out: " + ", ".join(r["game"] for r in bad_ones[:8]))
    np.savez_compressed(
        dest, ids=np.array([p["game"] for p in parts]), leagues=np.array([p["league"] for p in parts]),
        wins=np.array([p["wins"] for p in parts]),
        game=np.concatenate([np.full(len(p["t"]), k, np.int32) for k, p in enumerate(parts)]),
        t=np.concatenate([p["t"] for p in parts]), x=np.concatenate([p["x"] for p in parts]),
        app=np.concatenate([p["app"] for p in parts]))


# ── Model and evaluation ──────────────────────────────────────────────────────

CENTRES = (5.0, 12.5, 17.5, 22.5, 27.5, 32.5, 40.0)  # the centre of each PHASES stretch, for `smooth`


def folds(ids: np.ndarray, leagues: np.ndarray) -> np.ndarray:
    """Each match's fold: within each league, in crc32 order, one out of every five to each fold. That way
    the same match is never in training and test at once, and the five carry the same leagues."""
    out = np.zeros(len(ids), int)
    for league in set(leagues):
        own_rows = sorted((zlib.crc32(str(p).encode()), k) for k, p in enumerate(ids) if leagues[k] == league)
        for j, (_crc, k) in enumerate(own_rows):
            out[k] = j % FOLDS
    return out


def logits(weights: list[np.ndarray], x: np.ndarray, minute: np.ndarray, smooth: bool) -> np.ndarray:
    """Blue's log-odds with one logistic regression per stretch. Hard is that of its stretch, like the app; `smooth` blends
    the two neighbouring stretches' according to the minute, so the WP doesn't jump on changing stretch: a per-second
    curve that jumps at 10:00 would charge that jump to whatever happens at 10:00."""
    z = np.column_stack([w[0] + x @ w[1:] for w in weights])
    if not smooth:
        return z[np.arange(len(x)), np.searchsorted(PHASES, minute, side="right") - 1]
    a = np.interp(minute, CENTRES, np.arange(len(CENTRES)))
    lo = np.floor(a).astype(int)
    hi = np.minimum(lo + 1, len(CENTRES) - 1)
    r = np.arange(len(x))
    return (1 - (a - lo)) * z[r, lo] + (a - lo) * z[r, hi]


def fit(x: np.ndarray, y: np.ndarray, phase: np.ndarray, use: np.ndarray | bool = True,
           non_negative: list[int] | None = None) -> list[np.ndarray]:
    """One logistic regression per stretch with the states of `use` (with a mask and not x[use]: a copy of the whole of x
    is hundreds of MB). With `non_negative`, those columns can't weigh against (`fit_non_negative`)."""
    if non_negative is not None:
        return [fit_non_negative(x[use & (phase == p)], y[use & (phase == p)], non_negative)
                for p in range(len(PHASES))]
    return [logistic_fit(x[use & (phase == p)], y[use & (phase == p)], iterations=15) for p in range(len(PHASES))]


def scales(z: np.ndarray, y: np.ndarray, league: np.ndarray) -> np.ndarray:
    """(intercept, slope) of each league: the logistic regression of the result on the model's log-odds. The league is
    the same for both teams, so it can't favour either; what it can do is change how much a
    lead decides, and that is the slope (above 1, the same lead is overturned less)."""
    return np.array([logistic_fit(z[league == g][:, None], y[league == g]) for g in range(len(LEAGUES))])


def out_of_fold(x, y, phase, fold, minute, smooth=False, league=None, non_negative=None) -> np.ndarray:
    """Each state's log-odds with the model trained without its match.

    With `league`, rescaled with the `scales` of the training matches, taken from **their** out-of-fold log-odds
    (the other four folds among themselves). With the in-fold log-odds, the one the model gives the matches it was
    fitted on, the scale came out too confident and worsened five leagues out of seven."""
    z = np.zeros(len(y))
    for k in range(FOLDS):
        test = fold == k
        z[test] = logits(fit(x, y, phase, ~test, non_negative), x[test], minute[test], smooth)
        if league is not None:
            inside = np.zeros(len(y))
            for j in set(range(FOLDS)) - {k}:
                other = fold == j
                inside[other] = logits(fit(x, y, phase, ~test & ~other), x[other], minute[other], smooth)
            e = scales(inside[~test], y[~test], league[~test])
            z[test] = e[league[test], 0] + e[league[test], 1] * z[test]
    return z


def interval(d: np.ndarray, game: np.ndarray, times: int = 200) -> tuple[float, float]:
    """90% interval of the mean of `d` resampling whole matches: the states of one match
    share a result, so they aren't 842,000 independent data points but 5,144."""
    total, n = np.bincount(game, d), np.bincount(game)
    rng = np.random.default_rng(0)
    means = [total[r].sum() / n[r].sum() for r in (rng.integers(len(n), size=len(n)) for _ in range(times))]
    return float(np.percentile(means, 5)), float(np.percentile(means, 95))


def of_the_app(app: np.ndarray, minute: np.ndarray) -> np.ndarray:
    """The app's model as it is (wpa_model.MODEL), with its 17 timeline features."""
    return logits([np.array(c) for c in MODEL.coefficients], app, minute, smooth=False).clip(-30, 30)


def metrics(z: np.ndarray, y: np.ndarray) -> dict[str, float]:
    """Log-loss, Brier, AUC and calibration error (the mean of |predicted - real| across the ten deciles of predicted
    WP, weighted by how many fall in each), in points."""
    z = z.clip(-30, 30)  # as in the app: beyond that the WP is already 0 or 1
    p = 1 / (1 + np.exp(-z))
    deciles = np.minimum((p * 10).astype(int), 9)
    ece = sum(abs(p[deciles == d].mean() - y[deciles == d].mean()) * (deciles == d).sum()
              for d in range(10) if (deciles == d).any()) / len(y)
    return {"log_loss": float(np.mean(np.logaddexp(0, z) - y * z)), "brier": float(np.mean((p - y) ** 2)),
            "auc": auc(p, y), "ece": 100 * float(ece)}


def row(name: str, m: dict[str, float], base: dict[str, float] | None = None) -> str:
    extra = f" | {100 * (m['log_loss'] - base['log_loss']) / base['log_loss']:+.1f} %" if base else " | —"
    return (f"| {name} | {m['log_loss']:.4f} | {m['brier']:.4f} | {m['auc']:.3f} | {m['ece']:.2f}{extra} |")


def stretch(p: int) -> str:
    return f"{PHASES[p]}-{PHASES[p + 1]}" if p + 1 < len(PHASES) else f"{PHASES[p]}+"


def evaluate(data: Path, output: Path) -> None:
    d = np.load(data)
    game, t = d["game"], d["t"]
    x, app = d["x"].astype(float), d["app"].astype(float)
    y = d["wins"][game]
    league = np.array([LEAGUES.index(v) for v in d["leagues"]])[game]
    minute = t / 60
    phase = np.searchsorted(PHASES, minute, side="right") - 1
    fold = folds(d["ids"], d["leagues"])[game]
    with_league = np.column_stack([x, x * (league - 3)[:, None]])  # Gold = -3 … Challenger = +3
    print(f"# WP per second · {len(d['ids'])} games · {len(y):,d} states (one every {STEP} s) · "
          + ", ".join(f"{v} {n}" for v, n in sorted(collections.Counter(d["leagues"]).items(),
                                                     key=lambda kv: LEAGUES.index(kv[0]))))
    print(f"\nBlue wins {d['wins'].mean():.1%} of the games.\n")

    APP, FINAL, SCALE = "app (MODEL as it is, timeline)", "full, smooth", "full, smooth + scale per league"
    variants = {
        APP: of_the_app(app, minute),
        "app retrained (its 17 features)": out_of_fold(app, y, phase, fold, minute),
        "replay macro (16 features)": out_of_fold(x[:, :len(MACRO)], y, phase, fold, minute),
        "full": out_of_fold(x, y, phase, fold, minute),
        "full, smooth": out_of_fold(x, y, phase, fold, minute, smooth=True),
        "full + each feature by the league": out_of_fold(with_league, y, phase, fold, minute),
        SCALE: out_of_fold(x, y, phase, fold, minute, smooth=True, league=league),
    }
    del with_league
    base = metrics(variants[APP], y)
    head = ("| model | log-loss | Brier | AUC | calibration (pp) | log-loss against the app | difference "
            "[90%] |\n|---|---|---|---|---|---|---|")
    print("## All games, out of fold\n\n" + head)
    app_loss = np.logaddexp(0, variants[APP]) - y * variants[APP]
    for name, z in variants.items():
        z = z.clip(-30, 30)
        a, b = interval(np.logaddexp(0, z) - y * z - app_loss, game)
        print(row(name, metrics(z, y), base) + f" [{a:+.4f}, {b:+.4f}] |")

    chosen_ones = (APP, "app retrained (its 17 features)", "full", FINAL)
    for title, group, label in (("stretch of the match (minutes)", phase, stretch), ("league", league, LEAGUES.__getitem__)):
        print(f"\n## By {title}: log-loss (AUC)\n")
        print("| | states | " + " | ".join(chosen_ones) + " | improvement |\n|---|---|" + "---|" * (len(chosen_ones) + 1))
        for g in sorted(set(group)):
            m = group == g
            ms = [metrics(variants[e][m], y[m]) for e in chosen_ones]
            cells = " | ".join(f"{r['log_loss']:.3f} ({r['auc']:.3f})" for r in ms)
            print(f"| {label(g)} | {m.sum():,d} | {cells} | "
                  f"{100 * (ms[-1]['log_loss'] - ms[0]['log_loss']) / ms[0]['log_loss']:+.1f} % |")

    print("\n## Calibration by deciles (all games)\n")
    print("| predicted WP | app: states | predicts → won | final: states | predicts → won |")
    print("|---|---|---|---|---|")
    ps = [1 / (1 + np.exp(-variants[k].clip(-30, 30))) for k in (APP, FINAL)]
    for dec in range(10):
        cells = []
        for p in ps:
            m = np.minimum((p * 10).astype(int), 9) == dec
            cells += [f"{m.sum():,d}", f"{100 * p[m].mean():.1f} → {100 * y[m].mean():.1f} %" if m.any() else "—"]
        print(f"| {10 * dec}-{10 * dec + 10} % | " + " | ".join(cells) + " |")

    print("\n## Does the WP move before anything happens?\n")
    print("Pairs of consecutive states (10 s) of the same game. \"Quiet\" means nothing changes of what the")
    print("timeline sees (kills and objectives). Anticipation is how much the WP moves, towards the team that is going to make")
    print("the kill, in the quiet 10 s just before it: what a fight is worth before it ends in a kill.\n")
    print("| model | mean change in quiet 10 s | anticipation before a kill | in the 10 s of the kill |")
    print("|---|---|---|---|")
    consecutive = (game[1:] == game[:-1]) & (np.diff(t) == STEP)
    kill = np.diff(x[:, ALL_FEATURES.index("kills")])
    quiet = consecutive & (kill == 0) & (np.abs(np.diff(x[:, 4:len(MACRO)], axis=0)).sum(axis=1) == 0)
    before = quiet[:-1] & consecutive[1:] & (kill[1:] != 0)  # a quiet step and right after, a kill
    for name in (APP, "full", FINAL, SCALE):
        dp = 100 * np.diff(1 / (1 + np.exp(-variants[name].clip(-30, 30))))
        print(f"| {name} | {np.abs(dp[quiet]).mean():.2f} pp | "
              f"{np.mean(np.sign(kill[1:][before]) * dp[:-1][before]):+.2f} pp | "
              f"{np.mean(np.sign(kill[consecutive & (kill != 0)]) * dp[consecutive & (kill != 0)]):+.2f} pp |")
    print(f"\n{quiet.sum():,d} quiet pairs; {before.sum():,d} just before a kill.")

    print("\n## How much the league matters\n")
    print("Slope of the result's logistic regression on the log-odds of the model without league (full, smooth, out of")
    print("fold), by league, with its 90% interval resampling games: above 1, the same leads")
    print("decide the game more than on average; below, they are overturned more.\n")
    print("| league | slope | log-loss without → with the scale |\n|---|---|---|")
    rng = np.random.default_rng(0)
    final_logits = variants[FINAL]
    for g in range(len(LEAGUES)):
        own_items = np.flatnonzero(league == g)
        per_game = np.split(own_items, np.flatnonzero(np.diff(game[own_items])) + 1)  # consecutive in the .npz
        resamples = [logistic_fit(final_logits[r][:, None], y[r])[1] for r in (
            np.concatenate([per_game[i] for i in rng.integers(len(per_game), size=len(per_game))])
            for _ in range(100))]
        m = league == g
        print(f"| {LEAGUES[g]} | {logistic_fit(final_logits[m][:, None], y[m])[1]:.2f} "
              f"[{np.percentile(resamples, 5):.2f}, {np.percentile(resamples, 95):.2f}] | "
              f"{metrics(final_logits[m], y[m])['log_loss']:.4f} → {metrics(variants[SCALE][m], y[m])['log_loss']:.4f} |")

    print("\n## What each group of new features contributes (removing it from the full one, without league)\n")
    ll = metrics(variants["full"], y)["log_loss"]
    loss = np.logaddexp(0, variants["full"]) - y * variants["full"]
    print("| without… | log-loss | how much worse | difference [90%] |\n|---|---|---|---|")
    for name, remove in GROUPS.items():
        cols = [k for k, r in enumerate(ALL_FEATURES) if r not in remove]
        z = out_of_fold(x[:, cols], y, phase, fold, minute)
        m = metrics(z, y)
        a, b = interval(np.logaddexp(0, z) - y * z - loss, game)
        print(f"| {name} | {m['log_loss']:.4f} | {100 * (m['log_loss'] - ll) / ll:+.2f} % | [{a:+.4f}, {b:+.4f}] |")

    weights = fit(x, y, phase)
    scale_ = scales(final_logits, y, league)  # from the out-of-fold log-odds, as in the league table
    print("\n## Weights of the final model, standardized (log-odds per standard deviation of the feature in the stretch)\n")
    print("From highest to lowest mean weight.\n")
    print("| feature | " + " | ".join(stretch(p) for p in range(len(PHASES))) + " |\n|---|" + "---|" * len(PHASES))
    dev = [x[phase == p].std(axis=0) for p in range(len(PHASES))]
    order = np.argsort(-np.mean([np.abs(w[1:] * s) for w, s in zip(weights, dev, strict=True)], axis=0))
    print("| intercepto | " + " | ".join(f"{w[0]:+.2f}" for w in weights) + " |")
    for j in order:
        print(f"| {ALL_FEATURES[j]} | " + " | ".join(f"{w[1 + j] * s[j]:+.2f}" for w, s in zip(weights, dev, strict=True)) + " |")

    model = {"features": ALL_FEATURES, "phases": PHASES, "centres": CENTRES, "step": STEP,
              "coefficients": [[round(float(v), 6) for v in w] for w in weights],
              # (intercept, slope) on the log-odds: measured, but not applied, since out of fold it doesn't improve
              "slope_per_league": {LEAGUES[g]: [round(float(v), 4) for v in e] for g, e in enumerate(scale_)},
              "timers": {"dragon": DRAGON, "ancestral": ANCESTRAL, "baron": BARON, "notice": WARNING},
              "fight": FIGHT}
    (output / "model.json").write_text(json.dumps(model, indent=1), encoding="utf-8")
    print(f"\nwrote {output / 'model.json'}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # redirected to a file, Windows would write in cp1252
    # the blending of stretches: at the centre of a stretch its model rules and halfway, the mean of the two
    spans = [np.array([float(p), 0.0]) for p in range(len(PHASES))]
    assert list(logits(spans, np.zeros((2, 1)), np.array([12.5, 15.0]), smooth=True)) == [1.0, 1.5]
    harvest, games, output = (Path(a) for a in sys.argv[1:4])
    processes = int(sys.argv[sys.argv.index("--processes") + 1]) if "--processes" in sys.argv else 3
    output.mkdir(parents=True, exist_ok=True)
    data = output / "wp_per_second.npz"
    if not data.exists():
        extract(harvest, games, data, processes)
    evaluate(data, output)


if __name__ == "__main__":
    main()
