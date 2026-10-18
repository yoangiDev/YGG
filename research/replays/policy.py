"""The recall policy: what people do in each game state, learned from all the decoded
matches and with no hand-written rules.

    python research/replays/policy.py rows <output> [--processes 2] [--time-limit 150] [--timelines <dir>]  # the state every STEP s
    python research/replays/policy.py merge <output>                  # each match's rows into a few files
    python research/replays/policy.py exam <output>                 # recalls and deaths of the matches with a review
    python research/replays/policy.py train <output>                # P(recall | state), validated by match
    python research/replays/policy.py cross <output>                  # its disagreements against the author's reviews
    python research/replays/policy.py exam <output> --game EUW1-123 --champion Aphelios   # a new match
    python research/replays/policy.py player <output> --game EUW1-123                      # and its analysis

What comes out and what it means, in `recall-policy.md`.

`coach.py` judges each back with rules taken from the reviews (the wave, the gold, the jungler's window). Here there is no
rule: for each champion alive and away from their base, every STEP seconds, what they knew at that instant is stored —unspent
gold, health, mana, spells, where the wave is in the lane they're in and whether it crashes into the enemy turret,
who is alive, how long since the enemy jungler was seen, how long until the dragon— and whether a recall began (of
those that end in the base) in the following STEP seconds. With that a model learns each league's policy: in
this state, how many go back to base. The coach can mark a disagreement when the player departs from what the
high league would do, without anyone having told them when to go back.

Only what the player could know enters: enemies count where they are seen (`seen`), not where they are, and the
wave is measured with the minions that have already fallen, not those about to fall.

All decoded matches enter, whatever the patch: the ladder harvest (16.18 and 16.19, with its
league) and the ones users have uploaded (uploaded replays, no league). The mechanics this looks at (waves, gold, timers) do not
change from one patch to the next. The matches of the author's reviews (`REVIEWS`) don't enter the training: they are the
exam.

`rows` and `merge` run with what is in the repo (Python 3.10+). `train` and `cross` use scikit-learn, which is in no
pyproject on purpose (as in wp-per-second.md): they are run in a separate environment.
"""

from __future__ import annotations

import argparse
import bisect
import csv
import gzip
import json
import math
import re
import statistics
import sys
import time
import zlib
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
YGG = HERE.parents[1]
DECODER = YGG.parent / "lol-replay-decoder" / "data"
LADDER_GAMES = YGG / "research" / "ladder" / "data" / "harvest-16.19" / "matches.jsonl.gz"

LEAGUES = ("GOLD", "PLATINUM", "EMERALD", "DIAMOND", "MASTER", "GRANDMASTER", "CHALLENGER")
POSITIONS = ("TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY")
LANE_OF = {"TOP": "top", "MIDDLE": "mid", "BOTTOM": "bot", "UTILITY": "bot"}
STEP = 10  # every how many seconds each champion is looked at
FROM = 90  # before that nobody goes back to base by decision
AT_BASE = 2500  # within this of the centre of their base, they are inside (fountain and platform)
CHANNEL = 8.0  # how long a recall lasts: while it channels, the decision has already been made
WAVE_WINDOW = 15.0  # the wave is placed with the minions fallen in the last 15 s
NEGATIVES = 4  # of the ladder's rows without a recall, one in every NEGATIVES is kept, and weighs NEGATIVES
# the timers of wp-per-second.md, taken from the harvest: 100% of appearances within <= 2 s of the rule
DRAGON, DRAGON_RESPAWN, ANCESTRAL, BARON, BARON_RESPAWN = 294.0, 293.5, 353.5, 1180.0, 340.0

# the matches with an author's review (research/coaching): they are never trained on
REVIEWS = {"EUW1-8007142093": "Kaisa", "EUW1-8008878706": "Qiyana", "EUW1-8007681353": "Draven",
           "EUW1-8008728214": "Kaisa", "EUW1-8008826796": "Aphelios", "EUW1-8009746420": "Kennen",
           "EUW1-8010550033": "Chogath"}

KEY = ["game", "league", "source", "champion", "position", "team", "t", "weight", "y", "wins"]
ALL_FEATURES = ["minute", "position_i", "league_i", "gold", "gold_total", "level", "health", "mana", "inv_d", "inv_f", "ulti",
          "dist_base", "depth", "in_their_lane", "in_corridor", "wave_pos", "wave_vs_rival_tower",
          "wave_vs_own_tower", "my_minions", "their_minions", "rival_visible_dist", "rivals_visible_near",
          "ally_dist", "allies_alive", "rivals_alive", "rival_lane_dead", "jungler_rival_hidden", "dragon_in",
          "baron_in", "gold_team", "lane_gold", "time_away"]


# ---------------------------------------------------------------- each match's state (on the PC)

def _f(v: str | None) -> float | None:
    if v in (None, "", "nan"):
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _per_second(rows: list[dict], until: int) -> list[dict]:
    """A champion's row for each second, with the gaps filled with the last value: the decoder only writes
    a value when it changes (total gold comes out blank before the minute and the position, while they don't walk)."""
    numeric = ("x", "z", "gold", "total_gold", "level", "health", "health_max", "mana", "mana_max", "ally_dist")
    last_: dict[str, object] = {}
    out: list[dict] = [{} for _ in range(until + 1)]
    by_t = {int(float(f["time"])): f for f in rows}
    for s in range(until + 1):
        f = by_t.get(s)
        if f is not None:
            for k in numeric:
                v = _f(f.get(k))
                if v is not None:
                    last_[k] = v
            for k in ("alive", "seen", "d_ready", "f_ready", "r_ready"):
                if f.get(k) not in (None, ""):
                    last_[k] = f[k] == "True"
        out[s] = dict(last_)
    return out


def _count_per_second(intervals: list[tuple[float, float]], until: int) -> list[int]:
    """How many intervals [t0, t1) contain each second."""
    delta = [0] * (until + 2)
    for t0, t1 in intervals:  # a minion alive when the match ends dies at infinity
        a, b = max(0, math.ceil(min(t0, until + 1))), math.ceil(min(t1, until + 1))
        if a < b:
            delta[a] += 1
            delta[b] -= 1
    out, n = [], 0
    for s in range(until + 1):
        n += delta[s]
        out.append(n)
    return out


def rows_of_game(events_path: Path, state_path: Path, game: str, league: str | None, source: str,
                     all_: bool) -> list[dict]:
    """One row per champion alive and away from their base every STEP s: what they knew and whether a recall began."""
    import moments as M  # in the child process, with sys.path already set

    with M.open_file(events_path) as fh:
        ev = M.drop_revived(json.load(fh))
    rows = M.read_state(state_path)
    return _rows(ev, rows, M.lane_waves(ev), game, league, source, all_)


def rows_from_timeline(path: Path) -> list[dict]:
    """The same, from the match's timeline (`timeline.py`): the decoded output isn't needed."""
    import timeline

    L = timeline.load(path)
    ev, rows, waves = timeline.rehydrate(L)
    source = L.meta["source"]
    return _rows(ev, rows, waves, L.meta["game"], L.meta["league"] or None, source, all_=(source != "ladder"))


def _rows(ev: dict, rows, waves: dict, game: str, league: str | None, source: str, all_: bool) -> list[dict]:
    import moments as M

    towers = M._towers(ev, waves)
    bases = M._bases(rows)
    recalls = M.recalls(ev, rows)
    until = int(ev["game_length"])
    players = ev["players"]
    team_of = {p["net_id"]: p["team"] for p in players}
    wins = {}
    for p, s in zip(players, ev.get("stats") or []):
        wins[p["team"]] = 1 if s.get("WIN") == "Win" else 0

    table = {p["champion"]: _per_second(rows.get(p["champion"], []), until) for p in players}

    # the wave: where each lane's minions fall (sorted) and how many minions of each side live each second
    falls = {}
    for lane, items in waves["falls"].items():
        items = sorted(items)
        falls[lane] = ([c[0] for c in items], [c[1] for c in items])
    alive = {k: _count_per_second(v, until) for k, v in waves["healths"].items()}
    corridors = waves["corridors"]

    def wave_pos(lane: str, t: float) -> float | None:
        times, advances = falls.get(lane, ([], []))
        a, b = bisect.bisect_left(times, t - WAVE_WINDOW), bisect.bisect_right(times, t)
        return statistics.median(advances[a:b]) if b - a >= 3 else None

    # recalls: those that end in the base are the decision; while any channels, nothing is decided
    made: dict[str, list[float]] = {}
    channels: dict[str, list[float]] = {}
    for r in recalls:
        channels.setdefault(r["champion"], []).append(r["time"])
        if not r["cancelled"]:
            made.setdefault(r["champion"], []).append(r["time"])
    for v in (*made.values(), *channels.values()):
        v.sort()

    # deaths with their respawn, to know how long until the lane opponent comes back
    deaths: dict[str, list[tuple[float, float]]] = {}
    for e in ev["events"]:
        if e["type"] == "Death" and e["net_id"] in team_of:
            deaths.setdefault(e["net_id"], []).append((e["time"], e["time"] + e["respawn_time"]))

    # timers: dragon (with the elder after a soul) and baron
    killer_eq = team_of
    dragons = sorted((c["time"], killer_eq.get(c["killer"])) for c in ev["camps"]
                      if c["camp"].startswith("Dragon") and "elder" not in c["camp"].lower())
    count, soul_at = {"100": 0, "200": 0}, None
    for t, eq in dragons:
        if eq in count:
            count[eq] += 1
            if count[eq] == 4 and soul_at is None:
                soul_at = t
    elders = sorted(c["time"] for c in ev["camps"] if "elder" in c["camp"].lower())
    t_dragons = [t for t, _ in dragons]

    def dragon_in(t: float) -> float:
        if soul_at is not None and t >= soul_at:
            latest = [soul_at, *[a for a in elders if a <= t]]
            return max(0.0, latest[-1] + ANCESTRAL - t)
        i = bisect.bisect_right(t_dragons, t)
        return max(0.0, (DRAGON if i == 0 else t_dragons[i - 1] + DRAGON_RESPAWN) - t)

    barons = sorted(c["time"] for c in ev["camps"] if c["camp"] == "Baron")

    def baron_in(t: float) -> float:
        i = bisect.bisect_right(barons, t)
        return max(0.0, (BARON if i == 0 else barons[i - 1] + BARON_RESPAWN) - t)

    # how long since each team's jungler was last seen, from the other
    hidden: dict[str, list[float | None]] = {}
    for p in players:
        if p["position"] != "JUNGLE":
            continue
        sighted, series = None, []
        for s, f in enumerate(table[p["champion"]]):
            if f.get("seen") and f.get("alive") and "x" in f:
                sighted = s
            series.append(None if sighted is None else s - sighted)
        hidden[p["team"]] = series

    # the last time each one was in their base (or dead: they respawn in it)
    at_base_since: dict[str, list[float]] = {}
    for p in players:
        bx, bz = bases[p["team"]]
        last, series = 0, []
        for s, f in enumerate(table[p["champion"]]):
            if not f.get("alive", True) or ("x" in f and math.dist((f["x"], f["z"]), (bx, bz)) < AT_BASE):
                last = s
            series.append(s - last)
        at_base_since[p["champion"]] = series

    out = []
    for p in players:
        me, eq = p["champion"], p["team"]
        rivals = [r for r in players if r["team"] != eq]
        allies = [a for a in players if a["team"] == eq and a["champion"] != me]
        lane_rival = next((r for r in rivals if r["position"] == p["position"]), None)
        side = "blue" if eq == "100" else "red"
        other = "red" if side == "blue" else "blue"
        bx, bz = bases[eq]
        ex, ez = bases["200" if eq == "100" else "100"]
        diagonal = (ex + ez) - (bx + bz)
        my_made, my_channels = made.get(me, []), channels.get(me, [])
        for t in range(FROM, until - STEP, STEP):
            f = table[me][t]
            if not f.get("alive") or "x" not in f:
                continue
            x, z = f["x"], f["z"]
            dist_base = math.dist((x, z), (bx, bz))
            if dist_base < AT_BASE:
                continue
            i = bisect.bisect_left(my_channels, t - CHANNEL)
            if i < len(my_channels) and my_channels[i] < t:  # channelling a recall that already started
                continue
            j = bisect.bisect_left(my_made, t)
            y = int(j < len(my_made) and my_made[j] < t + STEP)
            weight = 1
            if not all_ and not y:
                if zlib.crc32(f"{game}{me}{t}".encode()) % NEGATIVES:
                    continue
                weight = NEGATIVES

            lane = M._lane(x, z)
            pos = wave_pos(lane, t)
            rival_tower = towers[(lane, other)]
            own_tower = towers[(lane, side)]
            if side == "red":  # everything from the side of whoever decides: 0 their barracks, 1 the enemy's
                pos = None if pos is None else 1 - pos
                rival_tower, own_tower = 1 - rival_tower, 1 - own_tower

            visible = []
            for r in rivals:
                g = table[r["champion"]][t]
                if g.get("alive") and g.get("seen") and "x" in g:
                    visible.append(math.dist((x, z), (g["x"], g["z"])))
            rival_alive = sum(1 for r in rivals if table[r["champion"]][t].get("alive"))
            ally_alive = sum(1 for a in allies if table[a["champion"]][t].get("alive"))
            rival_missing = 0.0
            if lane_rival is not None:
                for t0, t1 in deaths.get(lane_rival["net_id"], []):
                    if t0 <= t < t1:
                        rival_missing = t1 - t
            team_gold = sum(table[a["champion"]][t].get("total_gold", 0.0) for a in players if a["team"] == eq)
            rival_gold = sum(table[r["champion"]][t].get("total_gold", 0.0) for r in rivals)
            lane_gold = None
            if lane_rival is not None:
                lane_gold = f.get("total_gold", 0.0) - table[lane_rival["champion"]][t].get("total_gold", 0.0)
            jr = hidden.get("200" if eq == "100" else "100")
            mana = None
            if f.get("mana_max"):
                mana = f.get("mana", 0.0) / f["mana_max"]
            row = {
                "game": game, "league": league or "", "source": source, "champion": me, "position": p["position"],
                "team": eq, "t": t, "weight": weight, "y": y, "wins": wins.get(eq, ""),
                "minute": round(t / 60, 2),
                "position_i": POSITIONS.index(p["position"]) if p["position"] in POSITIONS else "",
                "league_i": LEAGUES.index(league) if league in LEAGUES else "",
                "gold": round(f.get("gold", 0.0)), "gold_total": round(f.get("total_gold", 0.0)),
                "level": int(f.get("level", 1)),
                "health": round(f["health"] / f["health_max"], 3) if f.get("health_max") else "",
                "mana": "" if mana is None else round(mana, 3),
                "inv_d": int(bool(f.get("d_ready"))), "inv_f": int(bool(f.get("f_ready"))),
                "ulti": int(bool(f.get("r_ready"))),
                "dist_base": round(dist_base), "depth": round(((x + z) - (bx + bz)) / diagonal, 3),
                "in_their_lane": int(LANE_OF.get(p["position"]) == lane),
                "in_corridor": int((int(x // M.CELL), int(z // M.CELL)) in corridors),
                "wave_pos": "" if pos is None else round(pos, 3),
                "wave_vs_rival_tower": "" if pos is None else round(pos - rival_tower, 3),
                "wave_vs_own_tower": "" if pos is None else round(pos - own_tower, 3),
                "my_minions": alive.get((lane, side), [0] * (until + 1))[t],
                "their_minions": alive.get((lane, other), [0] * (until + 1))[t],
                "rival_visible_dist": round(min(visible)) if visible else "",
                "rivals_visible_near": sum(1 for d in visible if d < 2500),
                "ally_dist": round(f["ally_dist"]) if f.get("ally_dist") is not None else "",
                "allies_alive": ally_alive, "rivals_alive": rival_alive,
                "rival_lane_dead": round(rival_missing, 1),
                "jungler_rival_hidden": "" if jr is None or jr[t] is None else min(jr[t], 300),
                "dragon_in": round(min(dragon_in(t), 360.0)), "baron_in": round(min(baron_in(t), 1200.0)),
                "gold_team": round((team_gold - rival_gold) / 1000, 2),
                "lane_gold": "" if lane_gold is None else round(lane_gold / 1000, 2),
                "time_away": at_base_since[me][t],
            }
            out.append(row)
    return out


def sources() -> list[tuple[str, Path, Path, str]]:
    """(match, events, state, source) of all the decoded matches, with none repeated.

    From the ladder, the events of the first harvest (they weigh half and carry what is used) and the state table of the
    second, which has the game's own visibility alongside."""
    seen_: dict[str, tuple[str, Path, Path, str]] = {}
    c1, c2 = DECODER / "cosecha", DECODER / "cosecha2"
    for st in sorted(c2.glob("*.state.csv.gz")):
        pid = st.name.split(".")[0]
        evs = c1 / f"{pid}.events.json.gz"
        if not evs.exists():
            evs = c2 / f"{pid}.events.json.gz"
        if evs.exists():
            seen_[pid] = (pid, evs, st, "ladder")
    for folder in sorted((DECODER / "premium").glob("cosecha*")):
        for st in sorted(folder.glob("*.state.csv.gz")):
            pid = st.name.split(".")[0]
            evs = folder / f"{pid}.events.json.gz"
            if pid not in seen_ and evs.exists():
                seen_[pid] = (pid, evs, st, "premium")
    for st in sorted(DECODER.glob("*.state.csv")):  # the first matches, loose and uncompressed
        pid = st.name.split(".")[0]
        evs = DECODER / f"{pid}.events.json"
        if pid not in seen_ and evs.exists():
            seen_[pid] = (pid, evs, st, "loose")
    return list(seen_.values())


def leagues() -> dict[str, str]:
    """The league of each ladder match, without loading the 250 MB of timelines."""
    out = {}
    if LADDER_GAMES.exists():
        with gzip.open(LADDER_GAMES, "rt", encoding="utf-8") as fh:
            for line in fh:
                m = re.search(r'"match_id":\s*"([^"]+)"', line[:80])
                t = re.search(r'"tier":\s*"([A-Z]+)"', line[-200:])
                if m and t:
                    out[m.group(1).replace("_", "-")] = t.group(1)
    return out


def _one(args: tuple) -> tuple[str, int, str]:
    pid, evs, st, source, league, dest = args
    sys.path[:0] = [str(HERE), str(YGG / "packages" / "ygg-core" / "src")]
    try:
        rows = rows_from_timeline(evs) if st is None else rows_of_game(evs, st, pid, league, source,
                                                                         all_=(source != "ladder"))
    except Exception as e:  # a broken match doesn't stop the harvest
        return pid, 0, f"{type(e).__name__}: {e}"
    tmp = dest / f"{pid}.csv.gz.tmp"
    with gzip.open(tmp, "wt", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=KEY + ALL_FEATURES)
        w.writeheader()
        w.writerows(rows)
    tmp.replace(dest / f"{pid}.csv.gz")
    return pid, len(rows), ""


def cmd_rows(output: Path, processes: int, limit: int | None, time_limit: float | None,
              timelines: Path | None = None) -> None:
    """Resumable: each match leaves its file and the next round skips those done. With `time_limit`, it stops
    sending matches after that many seconds (for chunks of a session with a deadline). With `timelines`, from the timelines
    in that folder (`timeline.py extract`) instead of what is decoded."""
    dest = output / "games"
    dest.mkdir(parents=True, exist_ok=True)
    cache = output / "leagues.json"
    if cache.exists():
        league = json.loads(cache.read_text(encoding="utf-8"))
    elif timelines is None:
        league = leagues()
        cache.write_text(json.dumps(league), encoding="utf-8")
    else:
        league = {}  # each timeline brings its league
    if timelines is None:
        all_ = sources()
    else:  # each one's source goes in its timeline and is read on rehydrating
        all_ = [(f.stem, f, None, "") for f in sorted(timelines.glob("*.npz"))]
    failed = set()
    if (output / "errors.log").exists():
        failed = {line.split("\t")[0] for line in (output / "errors.log").read_text(encoding="utf-8").splitlines()}
    pending = [(pid, evs, st, src, league.get(pid), dest) for pid, evs, st, src in all_
                  if not (dest / f"{pid}.csv.gz").exists() and pid not in failed]
    if limit:
        pending = pending[:limit]
    print(f"{len(all_)} games ({sum(1 for x in all_ if x[3] == 'ladder')} from the ladder, "
          f"{sum(1 for x in all_ if x[3] != 'ladder')} uploads or loose) · {len(pending)} pending · "
          f"{processes} processes", flush=True)
    t0, done, rows = time.time(), 0, 0
    with ProcessPoolExecutor(processes) as pool, (output / "errors.log").open("a", encoding="utf-8") as err:
        queue = list(pending)
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
            if done % 50 == 0:
                print(f"{done}/{len(pending)} · {rows:,d} rows · {time.time() - t0:.0f} s", flush=True)
    print(f"done {done} · {len(pending) - done} left · {time.time() - t0:.0f} s", flush=True)


def cmd_join(output: Path, parts: int) -> None:
    """The rows of all the matches into `parts` files (to take them to the training environment)."""
    files = sorted((output / "games").glob("*.csv.gz"))
    opened_ones = [gzip.open(output / f"rows-{i}.csv.gz", "wt", encoding="utf-8", newline="") for i in range(parts)]
    for fh in opened_ones:
        fh.write(",".join(KEY + ALL_FEATURES) + "\n")
    for i, f in enumerate(files):
        with gzip.open(f, "rt", encoding="utf-8") as src:
            next(src)
            opened_ones[i % parts].write(src.read())
    for fh in opened_ones:
        fh.close()
    print(f"{len(files)} games in {parts} files")


def cmd_exam(output: Path, game: str | None = None, champion: str | None = None) -> None:
    """From the matches with a review: the recalls (also the cancelled ones) and the deaths of the reviewed player, to
    count in `cross` what happened after each disagreement. With `game` and `champion`, the same for that match and that
    player, in `<match>.player.json` (for `player`)."""
    sys.path[:0] = [str(HERE), str(YGG / "packages" / "ygg-core" / "src")]
    import moments as M

    whom = {game: champion} if game else REVIEWS
    out = {}
    for pid, evs, st, _src in sources():
        if pid not in whom:
            continue
        with M.open_file(evs) as fh:
            ev = M.drop_revived(json.load(fh))
        rows = M.read_state(st)
        me = next(p for p in ev["players"] if p["champion"] == whom[pid])
        out[pid] = {"champion": me["champion"], "position": me["position"], "team": me["team"],
                      "recalls": [r for r in M.recalls(ev, rows) if r["champion"] == me["champion"]],
                      "deaths": [round(e["time"], 1) for e in ev["events"]
                                  if e["type"] == "Death" and e["net_id"] == me["net_id"]]}
    if game:
        (output / f"{game}.player.json").write_text(json.dumps(out[game], indent=1), encoding="utf-8")
        print(f"{game}: {out[game]['champion']}, {len(out[game]['recalls'])} recalls, "
              f"{len(out[game]['deaths'])} deaths")
        return
    (output / "exam.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"{len(out)} exam games")


# ---------------------------------------------------------------- the model (in an environment with scikit-learn)

# what the author says about each recall in their reviews (research/coaching, the three hand-written ones): the minute and whether it
# was time to go back to base then. "done": went back and it was fine; "lost": it was time to go back and they didn't (or cancelled it).
AUTHOR = [
    ("EUW1-8007142093", "03:41", "done", "Recall after pushing the wave, without going for the plate"),
    ("EUW1-8007142093", "06:58", "done", "Recall after crashing the wave"),
    ("EUW1-8007142093", "10:13", "lost", "Overstay on the recall timer: keeps heading to the tower and dies"),
    ("EUW1-8007142093", "13:29", "done", "Recall after collecting the wave with 1,570 gold"),
    ("EUW1-8008878706", "01:50", "done", "Recall after the third camp of the first clear"),
    ("EUW1-8008878706", "06:41", "lost", "Walks to Krugs with 1,350 gold instead of going back"),
    ("EUW1-8008878706", "08:36", "lost", "Keeps clearing with 1,370 gold: it was time to go back (in the fog)"),
    ("EUW1-8008878706", "09:12", "done", "Recall after Raptors with 1,745 gold (late because of the previous one)"),
    ("EUW1-8008878706", "10:32", "done", "Recall after finishing the grubs and the fight, to open to the dragon"),
    ("EUW1-8008878706", "14:34", "lost", "Cancels the recall for a stimulus, with the herald at 26 s"),
    ("EUW1-8008878706", "14:56", "done", "Recall at last (it was time at 14:34)"),
    ("EUW1-8007681353", "02:18", "done", "Cheater recall after crashing the third wave"),
]
HIGH = (4, 5, 6)  # Master, Grandmaster and Challenger: the "high league" policy is the mean of the three
WINDOW = 3  # rows (30 s): "in this state, how many of the high league go back in the next 30 s"


def _seconds(clock: str) -> int:
    m, s = clock.split(":")
    return int(m) * 60 + int(s)


def _clock(t: float) -> str:
    return f"{int(t // 60)}:{int(t % 60):02d}"


def _read(output: Path):
    import pandas as pd

    tables = [pd.read_csv(f, low_memory=False) for f in sorted(output.glob("rows-*.csv.gz"))]
    df = pd.concat(tables, ignore_index=True)
    df["exam"] = df["game"].isin(REVIEWS)
    return df


def _model():
    from sklearn.ensemble import HistGradientBoostingClassifier

    return HistGradientBoostingClassifier(max_iter=300, learning_rate=0.08, max_leaf_nodes=31, min_samples_leaf=500,
                                          l2_regularization=1.0, categorical_features=[ALL_FEATURES.index("position_i")],
                                          early_stopping=False, random_state=0)


def _ll(y, p, w) -> float:
    import numpy as np

    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-np.average(y * np.log(p) + (1 - y) * np.log(1 - p), weights=w))


def cmd_train(output: Path) -> None:
    """Validation by match (5 folds): no match is predicted with a model that has seen it. It compares with
    what a gold-and-health rule would say, measures calibration, which features decide and how the policy changes with the
    league in the same states. It stores the final model, trained on the whole corpus (without the exam)."""
    import pickle

    import numpy as np
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import GroupKFold

    df = _read(output)
    corpus = df[~df["exam"]].reset_index(drop=True)
    X = corpus[ALL_FEATURES].astype(float).to_numpy()
    y, w, g = corpus["y"].to_numpy(), corpus["weight"].to_numpy().astype(float), corpus["game"].to_numpy()
    print(f"## Corpus\n\n{len(corpus):,d} rows from {corpus['game'].nunique():,d} games "
          f"({(corpus.groupby('game')['source'].first().value_counts().to_dict())}), {int(y.sum()):,d} recalls. "
          f"Exam held out: {df[df['exam']]['game'].nunique()} games.\n", flush=True)

    few = [ALL_FEATURES.index(r) for r in ("minute", "gold", "health", "time_away", "position_i")]
    p, p_few = np.zeros(len(corpus)), np.zeros(len(corpus))
    for tr, te in GroupKFold(5).split(X, y, g):
        p[te] = _model().fit(X[tr], y[tr], sample_weight=w[tr]).predict_proba(X[te])[:, 1]
        from sklearn.ensemble import HistGradientBoostingClassifier
        m = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.08, min_samples_leaf=500,
                                           categorical_features=[4], random_state=0)
        p_few[te] = m.fit(X[tr][:, few], y[tr], sample_weight=w[tr]).predict_proba(X[te][:, few])[:, 1]
        print(".", end="", flush=True)
    base = np.average(y, weights=w)
    print("\n\n## Validation by game (out of fold)\n")
    print("| model | log-loss | AUC |\n|---|---|---|")
    print(f"| base rate ({base:.3%} per 10 s row) | {_ll(y, np.full(len(y), base), w):.4f} | 0.500 |")
    print(f"| only minute, gold, health, time away and position | {_ll(y, p_few, w):.4f} | "
          f"{roc_auc_score(y, p_few, sample_weight=w):.3f} |")
    print(f"| whole state ({len(ALL_FEATURES)} features) | {_ll(y, p, w):.4f} | {roc_auc_score(y, p, sample_weight=w):.3f} |")

    print("\n### Calibration by deciles\n\n| predicts | go back |\n|---|---|")
    command = np.argsort(p)
    for chunk in np.array_split(command, 10):
        print(f"| {np.average(p[chunk], weights=w[chunk]):.2%} | {np.average(y[chunk], weights=w[chunk]):.2%} |")

    final = _model().fit(X, y, sample_weight=w)
    (output / "policy.pkl").write_bytes(pickle.dumps(final))

    # which features decide: how much the log-loss worsens on shuffling each one (on a sample, with the final model)
    rng = np.random.default_rng(0)
    idx = rng.choice(len(corpus), size=min(300_000, len(corpus)), replace=False)
    Xs, ys, ws = X[idx], y[idx], w[idx]
    ref = _ll(ys, final.predict_proba(Xs)[:, 1], ws)
    imp = []
    for k, r in enumerate(ALL_FEATURES):
        Xb = Xs.copy()
        Xb[:, k] = rng.permutation(Xb[:, k])
        imp.append((_ll(ys, final.predict_proba(Xb)[:, 1], ws) - ref, r))
    print("\n## What decides a recall (log-loss when shuffling the feature, on the final model)\n")
    print("| feature | worsens |\n|---|---|")
    for d, r in sorted(imp, reverse=True)[:15]:
        print(f"| {r} | +{d:.4f} |")

    # the league in the same states: how much a Gold goes back and how much a Challenger in each situation
    print("\n## The same situation, different league (P of going back in the next 10 s, in the same states)\n")
    laners = corpus["position"].isin(["TOP", "MIDDLE", "BOTTOM"]).to_numpy() & (corpus["minute"] < 14).to_numpy()
    Xl = X[laners & np.isin(np.arange(len(X)), idx)]
    spans = {"wave_vs_rival_tower": [-1, -0.25, -0.1, -0.03, 0.02, 1], "gold": [0, 500, 900, 1300, 1800, 99999],
              "health": [0, 0.3, 0.5, 0.7, 0.9, 1.01]}
    for feature, cuts in spans.items():
        k = ALL_FEATURES.index(feature)
        print(f"\nLaners before 14, by `{feature}`:\n\n| stretch | rows | Gold | Diamond | Challenger |\n|---|---|---|---|---|")
        for a, b in zip(cuts, cuts[1:]):
            sel = Xl[(Xl[:, k] >= a) & (Xl[:, k] < b)]
            if len(sel) < 200:
                continue
            row = [f"[{a}, {b})", f"{len(sel):,d}"]
            for league in (0, 3, 6):
                Xc = sel.copy()
                Xc[:, ALL_FEATURES.index("league_i")] = league
                row.append(f"{final.predict_proba(Xc)[:, 1].mean():.1%}")
            print("| " + " | ".join(row) + " |")


def _high(model, X):
    import numpy as np

    k = ALL_FEATURES.index("league_i")
    ps = []
    for league in HIGH:
        Xc = X.copy()
        Xc[:, k] = league
        ps.append(model.predict_proba(Xc)[:, 1])
    return np.mean(ps, axis=0)


def _reference(output: Path):
    """The model, the p of the rows in which the high league really goes back (sorted) and the against-the-grain cut."""
    import pickle

    import numpy as np

    model = pickle.loads((output / "policy.pkl").read_bytes())
    df = _read(output)
    corpus = df[~df["exam"] & df["league_i"].isin(HIGH)]
    p_recalls = np.sort(_high(model, corpus[corpus["y"] == 1][ALL_FEATURES].astype(float).to_numpy()))
    return df, model, p_recalls, float(np.percentile(p_recalls, 10))


def _player(me, info: dict, model, p_recalls, low_cut: float) -> dict:
    """Missed windows and against-the-grain recalls of a player, with their rows (`me`, in order) and their recalls and deaths.

    Two measures, because they are two questions:
    - staying: H30 = the share of high-league players who, in the states they actually went through,
      would have started a recall in those 30 s (the three consecutive rows there are while they stay out). **Missed
      window**: H30 >= 0.5 and they don't go back in those 30 s.
    - going back: p = the share that goes back in those 10 s in that state. After a recall there are no rows (they're in base), so
      a recall made is compared with its single row, against the rows in which the high league really went back.
      **Against-the-grain recall**: p below the 10th percentile of those rows."""
    import numpy as np

    p = _high(model, me[ALL_FEATURES].astype(float).to_numpy())
    t = me["t"].to_numpy()
    h = np.empty(len(p))  # 1 - probability that nobody goes back in the three rows from this one (if they are consecutive)
    for i in range(len(p)):
        continues = [p[j] for j in range(i, min(i + WINDOW, len(p))) if t[j] - t[i] < WINDOW * STEP]
        h[i] = 1 - np.prod([1 - q for q in continues])
    made = sorted(r["time"] for r in info["recalls"] if not r["cancelled"])
    cancelled_ones = sorted(r["time"] for r in info["recalls"] if r["cancelled"])
    lost_, i = [], 0
    while i < len(h):
        if h[i] >= 0.5 and not any(t[i] <= r < t[i] + WINDOW * STEP for r in made):
            j = i
            while j + 1 < len(h) and h[j + 1] >= 0.5 and t[j + 1] - t[j] <= STEP and \
                    not any(t[j + 1] <= r < t[j + 1] + WINDOW * STEP for r in made):
                j += 1
            end = t[j] + STEP
            row = me.iloc[int(np.argmax(h[i:j + 1])) + i]
            lost_.append({"since": int(t[i]), "until": int(end), "h30": round(float(h[i:j + 1].max()), 2),
                             "gold": int(row["gold"]), "health": row["health"], "mana": row["mana"],
                             "goes_back": next((r for r in made if r >= t[i]), None),
                             "died": next((m for m in info["deaths"] if t[i] <= m <= end + 30), None),
                             "cancel": next((c for c in cancelled_ones if t[i] <= c <= end), None)})
            i = j + 1
        else:
            i += 1
    against_the_grain, in_recall = [], {}
    for r in made:
        # their row; if there isn't one (a recall cancelled just before leaves those seconds out), the last one before
        k = np.searchsorted(t, r, side="right") - 1
        if k >= 0 and r - t[k] <= 2 * STEP:
            pct = float(np.searchsorted(p_recalls, p[k]) / len(p_recalls))
            in_recall[r] = (float(p[k]), pct)
            if p[k] < low_cut:
                against_the_grain.append({"t": r, "p": round(float(p[k]), 3), "pct": pct, "gold": int(me.iloc[k]["gold"]),
                                   "health": me.iloc[k]["health"]})
    return {"t": t, "h": h, "p": p, "lost": lost_, "against_the_grain": against_the_grain, "made": made,
            "cancelled_ones": cancelled_ones, "in_recall": in_recall}


def _print(pid: str, info: dict, r: dict) -> None:
    import numpy as np

    print(f"### {info['champion']} ({info['position']}) · {pid}{' · author review' if any(a[0] == pid for a in AUTHOR) else ''}\n")
    print(f"{len(r['made'])} recalls made, {len(r['cancelled_ones'])} cancelled. Median H30 in the game: "
          f"{np.median(r['h']):.0%}.\n")
    print("Recalls made:\n")
    for x, (q, pct) in sorted(r["in_recall"].items()):
        print(f"- {_clock(x)}: p {q:.1%}, percentile {pct:.0%} of the high league's recalls")
    print("\nMissed windows (the high league goes back and he does not):\n")
    for v in r["lost"]:
        then = []
        if v["cancel"]:
            then.append(f"cancels a recall at {_clock(v['cancel'])}")
        if v["died"]:
            then.append(f"dies at {_clock(v['died'])}")
        if v["goes_back"]:
            then.append(f"goes back at {_clock(v['goes_back'])}")
        mana = "" if v["mana"] != v["mana"] or v["mana"] in ("", None) else f", mana {float(v['mana']):.0%}"
        print(f"- {_clock(v['since'])}-{_clock(v['until'])}: H30 {v['h30']:.0%}, {v['gold']} gold, "
              f"health {float(v['health']):.0%}{mana}. Then: {', '.join(then) or 'nothing'}.")
    if not r["lost"]:
        print("- none")
    print("\nAgainst-the-grain recalls (almost nobody in the high league would go back there):\n")
    for c in r["against_the_grain"]:
        print(f"- {_clock(c['t'])}: p {c['p']:.1%} (percentile {c['pct']:.0%} of the high league's recalls), "
              f"{c['gold']} gold, health {float(c['health']):.0%}")
    if not r["against_the_grain"]:
        print("- none")
    print()


def cmd_player(output: Path, game: str) -> None:
    """Any match (already in `games/` with `rows` and with its `<match>.player.json` from `exam
    --game`): the high-league policy on the player that was requested."""
    import pandas as pd

    _df, model, p_recalls, low_cut = _reference(output)
    info = json.loads((output / f"{game}.player.json").read_text(encoding="utf-8"))
    rows = pd.read_csv(output / "games" / f"{game}.csv.gz")
    me = rows[rows["champion"] == info["champion"]].sort_values("t").reset_index(drop=True)
    print(f"Against-the-grain recall: p < {low_cut:.1%}. Missed window: H30 >= 50% without going back.\n")
    _print(game, info, _player(me, info, model, p_recalls, low_cut))


def cmd_cross(output: Path) -> None:
    """The high-league policy on the exam matches, against what the author says about each recall (see
    `_player` for the two measures)."""
    df, model, p_recalls, low_cut = _reference(output)
    exam = json.loads((output / "exam.json").read_text(encoding="utf-8"))
    print("## The exam games\n")
    results = {}
    for pid, info in exam.items():
        me = df[(df["game"] == pid) & (df["champion"] == info["champion"])].sort_values("t").reset_index(drop=True)
        results[pid] = _player(me, info, model, p_recalls, low_cut)
        _print(pid, info, results[pid])

    print(f"## Against what the author says\n\nAgainst-the-grain recall: p < {low_cut:.1%} in their 10 s (10th percentile "
          f"of the rows in which the high league goes back). Missed window: H30 >= 50% without going back.\n")
    print("| game | minute | author | what they say | the policy at that moment | match? |")
    print("|---|---|---|---|---|---|")
    hits = 0
    for pid, clock, kind, text in AUTHOR:
        r = results.get(pid)
        if r is None:
            print(f"| {pid} | {clock} | {kind} | {text} | no data | |")
            continue
        T = _seconds(clock)
        if kind == "done":
            near = [x for x in r["in_recall"] if abs(x - T) <= 20]
            if not near:
                print(f"| {pid} | {clock} | {kind} | {text} | no recall made within ±20 s | |")
                continue
            q, pct = r["in_recall"][min(near, key=lambda x: abs(x - T))]
            ok = q >= low_cut
            says = f"p {q:.1%}, percentile {pct:.0%} of the high league's recalls"
        else:
            near = (r["t"] >= T - 20) & (r["t"] <= T + 20)
            hm = float(r["h"][near].max()) if near.any() else float("nan")
            pct = float((r["h"] < hm).mean()) if near.any() else float("nan")
            ok = any(v["since"] - 20 <= T <= v["until"] + 20 for v in r["lost"])
            says = f"H30 max. {hm:.0%} within ±20 s, percentile {pct:.0%} of their game"
        hits += ok
        print(f"| {pid} | {clock} | {kind} | {text} | {says} | {'✓' if ok else '✗'} |")
    print(f"\n**{hits} of {len(AUTHOR)}** match the author.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("command", choices=["rows", "merge", "exam", "train", "cross", "player"])
    ap.add_argument("output", type=Path)
    ap.add_argument("--processes", type=int, default=2)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--parts", type=int, default=4)
    ap.add_argument("--time-limit", type=float, default=None)
    ap.add_argument("--game", default=None)
    ap.add_argument("--champion", default=None)
    ap.add_argument("--timelines", type=Path, default=None)
    a = ap.parse_args()
    if a.command == "rows":
        cmd_rows(a.output, a.processes, a.limit, a.time_limit, a.timelines)
    elif a.command == "merge":
        cmd_join(a.output, a.parts)
    elif a.command == "exam":
        cmd_exam(a.output, a.game, a.champion)
    elif a.command == "train":
        cmd_train(a.output)
    elif a.command == "player":
        cmd_player(a.output, a.game)
    else:
        cmd_cross(a.output)


if __name__ == "__main__":
    main()
