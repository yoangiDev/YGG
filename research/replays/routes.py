"""The jungler's routes: which camp they start with and what they do after each camp, and how much each route is worth in
the state in which they choose it, learned from all the decoded matches.

    python research/replays/routes.py rows <output> [--processes 2] [--time-limit 150] [--timelines <dir>]   # one row per decision
    python research/replays/routes.py merge <output>
    python research/replays/routes.py analyse <output> --wp <wp_per_second.npz> --model <value/model.json>  # sklearn
    python research/replays/routes.py game <output> <EUW1-123> <champion>         # a jungler's tree, decision by decision

Each time the jungler kills a camp (their own, the enemy's, the crab or an epic) up to 14:00 there is a decision, and
another at the start of the match (the first camp). For each one:

- **the state**, what they knew at that second: the map from `openings.state` (camps of each half, alive and those that
  spawn in 30 s; the crab; the upcoming objective; each lane with the enemies' health and flash, their own health and
  ultimates, where the wave is and the gold; where and how long ago the enemy jungler was seen) plus their own:
  level, health, mana, unspent gold, smite, the camp they just killed and how long they've been away from base;
- **where the enemy jungler is** relative to the lanes (`_rival`): in which lane their team has seen them in the
  last `SEEN` s (known), in which they really are and in which they are going to gank in the next `GANKS` s (not
  known: it only serves to split the tables, it enters no model);
- **the route**, the first thing they do in the following `FIRST` seconds: another camp of theirs (and which), invade, the
  crab, an objective, gank a lane (fight an enemy in their lane, or plant themselves in it with the enemy
  beside), **counter-gank** (the same gank, to a lane where the enemy jungler already was), fight in the jungle or the
  river, go back to base, or none of that;
- **what came out** at 90 s, 3 min and 5 min (`HORIZONS`): their gold, their team's kills and deaths and the objectives
  (`openings.result`, at 90 s), whether they die and the gold and experience against the enemy jungler (at all three); and, in
  `analyse`, the change in their team's WP at each horizon with the curve from `wp_per_second.npz`. At 90 s going back to
  base always comes out expensive: the time it loses is seen, not what it buys.

In `analyse`, for each moment (the first camp, the second…) it is seen what junglers do in each state and
how much each route yields **above what was expected in that state**: a model learns, without the route, what usually
happens in the 90 s following a state like that, and a route's value is the mean of what came out minus that. That way a
gank to a lane that was already winning doesn't take the credit for the lane.

`rows` and `merge` run with what is in the repo; `analyse` and `game` are in `routes_model.py` and use scikit-learn, in
a separate environment.
"""

from __future__ import annotations

import argparse
import bisect
import csv
import gzip
import json
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
YGG = HERE.parents[1]
FIRST = 75  # seconds in which it is looked at what they do after the camp
UNTIL = 840.0  # up to 14:00
START = 55.0  # when the camps spawn if the match doesn't say (in 16.19 and 16.20, at 0:55)
GROUP = 60.0  # the grubs fall three at a time: those that fall within this of the next are a single decision
PRESENCE = 4  # consecutive seconds in a lane, with their opponent within NEAR, to count as a gank without a fight
NEAR = 1500.0
SMITE = "11"  # the summoner spell's id
LANES = {"top": ("TOP",), "mid": ("MIDDLE",), "bot": ("BOTTOM", "UTILITY")}
HORIZONS = (90, 180, 300)  # seconds in which what came out is looked at
SEEN = 10  # if their team saw the enemy jungler in a lane less than this ago, they know they're there
GANKS = 30  # seconds in which it is looked at whether the enemy jungler plants themselves in a lane, beside one of their own
BEFORE_COUNTER = 20  # a gank is a counter-gank if the enemy jungler was already in that lane since this long before arriving
TOGETHER = 3000.0  # and within this of where they arrive


def _import_deps() -> None:
    sys.path[:0] = [str(HERE), str(YGG / "packages" / "ygg-core" / "src")]


# ---------------------------------------------------------------- on the PC: one row per decision

def _lane(corridors: dict, where: tuple[float, float] | None) -> str | None:
    """The lane through whose corridor that point passes (`moments.lane_waves`), or None if it is in the jungle or river."""
    import moments as M

    if not where:
        return None
    lanes = corridors.get((int(where[0] // M.CELL), int(where[1] // M.CELL)))
    return next(iter(lanes)) if lanes else None


def _rival(map_, team: str, t: float, corridors: dict) -> dict:
    """The enemy jungler and the lanes at second `t`: in which their team has seen them less than SEEN s ago (known),
    in which they really are and in which they plant themselves beside one of their own in the following GANKS s (the enemy's
    gank; what the player doesn't know, to split the tables)."""
    import openings as A

    rival = map_.junglers.get("200" if team == "100" else "100")
    out = {"rival_lane_seen": "", "rival_lane_real": "", "rival_ganks": ""}
    if not rival:
        return out
    if A._health(map_.row(rival, t)) is not None:
        out["rival_lane_real"] = _lane(corridors, map_.spot(rival, t)) or ""
    for s in range(int(t), int(t) - SEEN, -1):
        fr = map_.table.get(rival, {}).get(s)
        if fr and fr.get("seen") == "True" and fr.get("x"):
            out["rival_lane_seen"] = _lane(corridors, (float(fr["x"]), float(fr["z"]))) or ""
            break
    own_items = {h: [p["champion"] for p in map_.players if p["team"] == team and p["position"] in ps]
             for h, ps in LANES.items()}
    for s in range(int(t), int(t) + GANKS + 1):
        if A._health(map_.row(rival, s)) is None or not (where := map_.spot(rival, s)):
            continue
        h = _lane(corridors, where)
        if h and any((q := map_.spot(c, s)) and A._health(map_.row(c, s)) is not None and math.dist(where, q) <= NEAR
                     for c in own_items[h]):
            out["rival_ganks"] = h
            break
    return out


def _counter_gank(map_, jungler: str, lane: str, t: float, corridors: dict) -> bool:
    """Was the enemy jungler already in that lane, near where theirs arrives, in the BEFORE_COUNTER s before?"""
    import openings as A

    rival = map_.junglers.get("200" if map_.team_of[jungler] == "100" else "100")
    arrives = map_.spot(jungler, t)
    if not rival or not arrives:
        return False
    for s in range(int(t) - BEFORE_COUNTER, int(t) + 1):
        where = map_.spot(rival, s)
        if where and A._health(map_.row(rival, s)) is not None and _lane(corridors, where) == lane \
                and math.dist(where, arrives) <= TOGETHER:
            return True
    return False


def _route(map_, jungler: str, t0: float, made: list[float], corridors: dict) -> dict:
    """The first thing the jungler does in (t0, t0 + FIRST]."""
    import openings as A

    team = map_.team_of[jungler]
    own_side = "blue" if team == "100" else "red"
    net = map_.net[jungler]
    candidates = []
    for c in map_.events["camps"]:
        if t0 < c["time"] <= t0 + FIRST and c.get("killer") == net and any(c["position"]):
            name = c["camp"].split(" ")[0]
            if name == "Scuttle":
                candidates.append((c["time"], "crab", A.half(*c["position"], margin=0)))
            elif name not in A.GOLD:
                candidates.append((c["time"], "objective", name))
            elif map_._key(name, *c["position"])[2] == own_side:
                candidates.append((c["time"], "camp", name))
            else:
                candidates.append((c["time"], "invade", name))
    r = next((x for x in made if t0 < x <= t0 + FIRST), None)
    if r is not None:
        candidates.append((r, "base", ""))
    for e in map_.events["events"]:
        if e["type"] != "Damage" or not t0 < e["time"] <= t0 + FIRST:
            continue
        a, b = e["net_id"], e.get("source")
        if a not in map_.champion_of or b not in map_.champion_of or net not in (a, b):
            continue
        if map_.team_of[map_.champion_of[a]] == map_.team_of[map_.champion_of[b]]:
            continue
        where = map_.spot(jungler, e["time"])
        lane = _lane(corridors, where)
        candidates.append((e["time"], "gank" if lane else "fight", lane or (A.half(*where) if where else "mid")))
        break
    # the gank that doesn't get to fight: planting in the lane, with that lane's enemy nearby, for a few consecutive seconds
    rivals = {h: [p["champion"] for p in map_.players if p["team"] != team and p["position"] in ps]
               for h, ps in LANES.items()}
    streak, source, at = 0, None, None
    for s in range(int(t0) + 1, int(t0 + FIRST) + 1):
        where = map_.spot(jungler, s)
        lane = _lane(corridors, where)
        near = bool(lane) and any((q := map_.spot(rv, s)) and A._health(map_.row(rv, s)) is not None
                                     and math.dist(where, q) <= NEAR for rv in rivals[lane])
        if not near:
            streak, source, at = 0, None, None
        elif lane == at:
            streak += 1
        else:
            streak, source, at = 1, s, lane
        if streak >= PRESENCE:
            candidates.append((source, "gank", lane))
            break
    if not candidates:
        return {"route": "nothing", "detail": "", "route_t": ""}
    t, route, detail = min(candidates)
    if route == "gank" and _counter_gank(map_, jungler, detail, t, corridors):
        route = "counter_gank"
    return {"route": route, "detail": detail, "route_t": round(t - t0, 1)}


def _own(map_, jungler: str, t: float, smite: str | None, last_base: float) -> dict:
    """The jungler's own in that second."""
    import openings as A

    f = map_.row(jungler, t)
    health = A._health(f)
    mana, max_m = A._num(f, "mana"), A._num(f, "mana_max")
    spot = map_.spot(jungler, t)
    return {"level": A._num(f, "level") or "", "health": "" if health is None else round(health, 3),
            "mana": round(mana / max_m, 3) if mana is not None and max_m else "",
            "gold_unspent": round(A._num(f, "gold") or 0), "gold_total": round(A._num(f, "total_gold") or 0),
            "smite_ready": int(bool(f and smite and f.get(smite) == "True")),
            "half_now": A.half(*spot) if spot else "", "outside_of_base": round(t - last_base)}


def _against(map_, jungler: str, rival: str, t: float, end: float) -> dict:
    """How it changes against the enemy jungler from `t` to `end`: gold and experience difference, and whether they die before `end`
    (for the first camp, `end` is 3:45, when the first clear ends). And the same at 3 and 5 min
    (`gold_vs_rival_180`, `dies_300`…), blank if the match ends earlier."""
    import openings as A

    def diff(col: str, s: float) -> float | None:
        a, b = A._num(map_.row(jungler, s), col), A._num(map_.row(rival, s), col) if rival else None
        return None if a is None or b is None else a - b

    out = {"horizon": round(end - t)}
    for h in (None, *HORIZONS[1:]):
        until, suffix = (end, "change") if h is None else (t + h, str(h))
        for col, name in (("total_gold", "gold"), ("xp", "xp")):
            a, b = diff(col, t), diff(col, until)
            out[f"{name}_vs_rival_{suffix}"] = "" if a is None or b is None else round(b - a)
        died = int(any(t < m <= until and c == jungler for m, c in map_.deaths))
        continues = map_.row(jungler, until) is not None or died
        out["dies_in_horizon" if h is None else f"dies_{h}"] = died if continues else ""
    return out


def rows_of_game(events_path: Path, state_path: Path, game: str, league: str | None, source: str) -> list[dict]:
    """The decisions of a match's two junglers, from what is decoded."""
    _import_deps()
    import moments as M

    with M.open_file(events_path) as fh:
        ev = M.drop_revived(json.load(fh))
    rows = M.read_state(state_path)
    return _rows(ev, rows, M.lane_waves(ev), game, league, source)


def rows_from_timeline(route: Path) -> list[dict]:
    """The same, from the match's timeline (`timeline.py`): the decoded output isn't needed."""
    _import_deps()
    import timeline

    L = timeline.load(route)
    ev, rows, waves = timeline.rehydrate(L)
    return _rows(ev, rows, waves, L.meta["game"], L.meta["league"] or None, L.meta["source"])


def _rows(ev: dict, rows, waves: dict, game: str, league: str | None, source: str) -> list[dict]:
    _import_deps()
    import openings as A
    import moments as M

    map_ = A.GameMap(ev, rows, waves, None)
    corridors = waves["corridors"]
    wins = {p["team"]: int(s.get("WIN") == "Win") for p, s in zip(ev["players"], ev.get("stats") or [])}
    smites = {p["champion"]: ("d_ready" if s.get("SUMMONER_SPELL_1") == SMITE else
                              "f_ready" if s.get("SUMMONER_SPELL_2") == SMITE else None)
              for p, s in zip(ev["players"], ev.get("stats") or [])}
    recalls = M.recalls(ev, rows)
    out = []
    for team, jungler in map_.junglers.items():
        net = map_.net[jungler]
        made = sorted(r["time"] for r in recalls if r["champion"] == jungler and not r["cancelled"])
        bases = [0.0] + [t for t in made] + [t for t, c in map_.deaths if c == jungler]
        bases.sort()
        rival = map_.junglers.get("200" if team == "100" else "100", "")
        common = {"game": game, "league": league or "", "source": source, "team": team, "jungler": jungler,
                 "rival_jungler": rival, "wins": wins.get(team, "")}
        # 0: the first camp, decided when they spawn (the state, at that second)
        leave = [t for (name, _h, _l), m in map_.monsters.items() if name in A.GOLD for t in m["leaves"][:1]]
        start = min(leave) if leave else START
        camps = sorted(((c["time"], c) for c in ev["camps"] if c.get("killer") == net and any(c["position"])),
                       key=lambda x: x[0])
        # of the grubs that fall in a row, only the last: between one and the next nothing is decided
        camps = [(t, c) for i, (t, c) in enumerate(camps)
                 if not (c["camp"].startswith("Voidgrub") and any(c2["camp"].startswith("Voidgrub") and t < t2 <= t + GROUP
                                                                    for t2, c2 in camps[i + 1:]))]
        first = camps[0] if camps else None
        if first:
            c = first[1]
            name = c["camp"].split(" ")[0]
            own_side = "blue" if team == "100" else "red"
            route = {"route": "crab" if name == "Scuttle" else
                    ("camp" if map_._key(name, *c["position"])[2] == own_side else "invade")
                    if name in A.GOLD else "objective", "detail": name, "route_t": round(first[0] - start, 1)}
            out.append(common | {"decision": 0, "t": round(start, 1), "after": "start"} | A.state(map_, team, start)
                         | _rival(map_, team, start, corridors)
                         | _own(map_, jungler, start, smites.get(jungler), 0.0) | route
                         | A.result(map_, jungler, start) | _against(map_, jungler, rival, start, 225.0))
        # after each camp: what they do next
        for k, (t, c) in enumerate(camps, 1):
            if t > UNTIL:
                break
            last = bases[bisect.bisect_right(bases, t) - 1]
            out.append(common | {"decision": k, "t": round(t, 1), "after": c["camp"].split(" ")[0]}
                         | A.state(map_, team, t) | _rival(map_, team, t, corridors)
                         | _own(map_, jungler, t, smites.get(jungler), last)
                         | _route(map_, jungler, t, made, corridors) | A.result(map_, jungler, t)
                         | _against(map_, jungler, rival, t, t + 90))
    return out


def _one(args: tuple) -> tuple[str, int, str]:
    pid, evs, st, source, league, dest = args
    try:
        rows = rows_from_timeline(evs) if st is None else rows_of_game(evs, st, pid, league, source)
    except Exception as e:  # a strange match doesn't stop the others
        return pid, 0, f"{type(e).__name__}: {e}"
    if rows:
        columns = list(dict.fromkeys(k for f in rows for k in f))
        tmp = dest / f"{pid}.csv.gz.tmp"
        with gzip.open(tmp, "wt", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=columns)
            w.writeheader()
            w.writerows(rows)
        tmp.replace(dest / f"{pid}.csv.gz")
    return pid, len(rows), ""


def cmd_rows(output: Path, processes: int, time_limit: float | None, timelines: Path | None = None) -> None:
    """Resumable, like `policy.py rows`: each match leaves its file and the next round skips those done.
    With `timelines`, from the timelines in that folder (`timeline.py extract`) instead of what is decoded."""
    _import_deps()
    import policy as P

    dest = output / "games"
    dest.mkdir(parents=True, exist_ok=True)
    cache = YGG / "research" / "ladder" / "data" / "policy" / "leagues.json"
    league = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else P.leagues()
    failed = set()
    if (output / "errors.log").exists():
        failed = {x.split("\t")[0] for x in (output / "errors.log").read_text(encoding="utf-8").splitlines()}
    all_ = P.sources() if timelines is None else [(f.stem, f, None, None) for f in sorted(timelines.glob("*.npz"))]
    queue = [(pid, evs, st, src, league.get(pid), dest) for pid, evs, st, src in all_
            if not (dest / f"{pid}.csv.gz").exists() and pid not in failed]
    total = len(queue)
    print(f"{len(all_)} games · {total} pending · {processes} processes", flush=True)
    t0, done, rows = time.time(), 0, 0
    with ProcessPoolExecutor(processes) as pool, (output / "errors.log").open("a", encoding="utf-8") as err:
        running = set()
        while queue or running:
            while queue and len(running) < 2 * processes and (time_limit is None or time.time() - t0 < time_limit):
                running.add(pool.submit(_one, queue.pop(0)))
            if not running:
                break
            done_ = next(as_completed(running))
            running.discard(done_)
            pid, n, notice = done_.result()
            done, rows = done + 1, rows + n
            if notice:
                err.write(f"{pid}\t{notice}\n")
                err.flush()
    print(f"done {done} · {rows:,d} decisions · {total - done} left · {time.time() - t0:.0f} s", flush=True)


def cmd_join(output: Path) -> None:
    import pandas as pd

    parts = [pd.read_csv(f, low_memory=False) for f in sorted((output / "games").glob("*.csv.gz"))]
    df = pd.concat(parts, ignore_index=True)
    df.to_csv(output / "decisions.csv.gz", index=False)
    print(f"{len(parts)} games · {len(df):,d} decisions · {df.shape[1]} columns")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("command", choices=["rows", "merge", "analyse", "game"])
    ap.add_argument("output", type=Path)
    ap.add_argument("rest", nargs="*")
    ap.add_argument("--processes", type=int, default=2)
    ap.add_argument("--time-limit", type=float, default=None)
    ap.add_argument("--wp", type=Path, default=None)
    ap.add_argument("--model", type=Path, default=None)
    ap.add_argument("--timelines", type=Path, default=None)
    a = ap.parse_args()
    if a.command in ("analyse", "game"):
        import routes_model as R  # the scikit-learn part, separate so that the PC part doesn't need it

        if a.command == "analyse":
            R.analyse(a.output, a.wp, a.model)
        else:
            R.game(a.output, *a.rest)
        return
    if a.command == "rows":
        cmd_rows(a.output, a.processes, a.time_limit, a.timelines)
    else:
        cmd_join(a.output)


if __name__ == "__main__":
    main()
