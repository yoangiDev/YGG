"""A match's timeline: everything from the replay that the analyses use, extracted once.

There are three layers, from the most expensive to repeat to the cheapest:

1. **Decode** (`lol-replay-decoder/cosecha.py`): the .rofl → `state.csv`, `events.json`, `vision.json` and
   `torres.json`. About 25 s per match.
2. **The timeline** (this): one pass per match that leaves in a `.npz` the state of the ten every second, the
   clean events and the map facts that are costly to compute (waves, turrets, wards, fights, recalls). It is only repeated
   if what it stores changes (`VERSION`).
3. **The analyses** (`policy`, `routes`, `trees`…): they read the timeline with `load` and define their decisions,
   their outcomes and their horizons. That is where one iterates without going through the matches again. The catalogue of what is going to be
   analysed is in `catalog.md`. The earlier code, written for what is decoded, runs the same on the
   timeline with `rehydrate` (`routes.py rows --timelines`, `policy.py rows --timelines`).

    python research/replays/timeline.py extract <output> [--processes 2] [--time-limit 115] [--only 20]   # on the PC, resumable
    python research/replays/timeline.py check <output> --routes research/ladder/data/routes2    # that it matches routes.py

**What each `<match>.npz` stores** (`load` returns it as a `Timeline`):

- `meta`: the match, the league, the source, the duration, the ten players (champion, team, position, summoner
  spells, whether they win), the bases, the names of each column and the vocabularies of the text columns.
- **Every second, the ten champions** (`champions16`, `champions32`, `flags`): place, health, CS, camps,
  speed, level, distance to the nearest ally and enemy; in floating point, unspent gold, total gold,
  experience and mana; and whether there is a row that second, whether they are alive, whether the enemy sees them and whether Q, W, E, R
  and the two spells are ready. The decoder only writes a value when it changes: here each
  gap carries the last known value (`row` says whether that second really carries a row).
- **Every second, the three waves** (`lane_waves`): where the front is (the advance from 0, the blue barracks, to 1000, the
  red one, and its place; `moments._advance`) and how many live minions each side has (`moments._alive`).
- **Event tables** (`table(name)`), with the champion as an index from 0 to 9 (-1 if not a champion):
  `deaths` (with the killer and who hit them in the previous 10 s), `recalls`, `camps`, `spawns`,
  `towers`, `towers_fallen`, `towers_health`, `wards`, `minions`, `fights`, `damage`, `casts`, `controls`, `purchases`,
  `finishes`, `gold`, `attacks`, `buffs` and `headings` (the destination of each champion click). The champions' headings only
  come in what was decoded with the recent decoder: in the ladder and in the 16.20 uploads the table comes out empty, and
  where each one is heading is derived from their place second by second.
- `corridors`: the cells the minions of each lane walk through (`moments.lane_waves`); in `meta`, their
  barracks and their axis, the turrets and each player's `stats` (without the season event counters).

What isn't there because the replay doesn't carry it: pings, chat and the seconds of cooldown remaining (only whether
the ability is ready or not).
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
YGG = HERE.parents[1]
VERSION = 5  # bump it when what is stored changes: `extract` redoes those of another version (5: the tables and columns are named in English)
C16 = ("x", "z", "health", "health_max", "cs", "jungle_minions", "move_speed", "level", "ally_dist", "enemy_dist")
C32 = ("gold", "total_gold", "xp", "mana", "mana_max")  # in floating point: there are resources from 0 to 1 (Aatrox, Briar)
FLAGS = ("row", "alive", "seen", "q_ready", "w_ready", "e_ready", "r_ready", "d_ready", "f_ready", "cc")
NO_DATA = -32768  # no data, in the 16-bit columns
LANES = ("top", "mid", "bot")
WAVE_WINDOW = 20.0  # like moments._advance
ASSIST_WINDOW = 10.0  # seconds before a death in which hitting them counts as taking part


def _import_deps() -> None:
    sys.path[:0] = [str(HERE), str(YGG / "packages" / "ygg-core" / "src")]


# ---------------------------------------------------------------- on the PC: extracting the timeline

class _Table:
    """A table by columns; text ones (type "s") are stored as codes with their vocabulary."""

    def __init__(self, **kinds: str) -> None:
        self.kinds, self.cols = kinds, {c: [] for c in kinds}

    def put(self, **v) -> None:
        for c in self.cols:
            self.cols[c].append(v[c])

    def save(self, name: str, arrays: dict, vocab: dict) -> None:
        for c, kind in self.kinds.items():
            values = self.cols[c]
            if kind == "s":
                words = sorted({str(v) for v in values})
                index = {p: i for i, p in enumerate(words)}
                vocab[f"{name}.{c}"] = words
                arrays[f"{name}.{c}"] = np.array([index[str(v)] for v in values], np.int16)
            elif kind.startswith("i"):  # trimmed to the type: some cast points outside the map (x of 60,000)
                info = np.iinfo(np.dtype(kind))
                v = np.nan_to_num(np.array(values, dtype=float), nan=-1.0)
                arrays[f"{name}.{c}"] = np.clip(np.round(v), info.min, info.max).astype(kind)
            else:
                arrays[f"{name}.{c}"] = np.array(values, dtype=kind)


def _number(v) -> float | None:
    if v in (None, "", "nan"):
        return None
    x = float(v)
    return x if math.isfinite(x) and abs(x) < 1e7 else None


def _dense(ev: dict, rows: dict, T: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The ten champions every second, with the last known value in the gaps."""
    a16 = np.full((T, 10, len(C16)), NO_DATA, np.int16)
    a32 = np.full((T, 10, len(C32)), np.nan, np.float32)
    ban = np.zeros((T, 10), np.uint16)
    level = C16.index("level")
    for i, p in enumerate(ev["players"]):
        # all the rows of each second, in order: a second can carry several and each only what changed
        per_second = collections.defaultdict(list)
        for f in rows.get(p["champion"], []):
            s = int(float(f["time"]))
            if 0 <= s < T:
                per_second[s].append(f)
        u16, u32 = [None] * len(C16), [None] * len(C32)
        u16[level] = 1.0
        ub = dict.fromkeys(FLAGS[1:], False)
        for s in range(T):
            bits = 0
            for f in per_second.get(s, ()):
                bits = 1
                for k, c in enumerate(C16):
                    if (x := _number(f.get(c))) is not None:
                        u16[k] = x
                for k, c in enumerate(C32):
                    if (x := _number(f.get(c))) is not None:
                        u32[k] = x
                for c in FLAGS[1:]:
                    v = f.get(c)
                    if c == "cc":
                        ub[c] = v not in (None, "", "0", "0.0", "False")
                    elif v not in (None, ""):
                        ub[c] = v == "True"
            for k, x in enumerate(u16):
                if x is not None:
                    a16[s, i, k] = max(-32767, min(32767, round(x)))
            for k, x in enumerate(u32):
                if x is not None:
                    a32[s, i, k] = x
            for b, c in enumerate(FLAGS[1:], 1):
                if ub[c]:
                    bits |= 1 << b
            ban[s, i] = bits
    return a16, a32, ban


def _dense_waves(waves: dict, T: int) -> np.ndarray:
    """Each second and lane: the front's advance (x1000, from blue), its x and its z, and the live minions of blue and
    red. The same as moments._advance and moments._vivos, for all the seconds at once."""
    out = np.full((T, 3, 5), NO_DATA, np.int16)
    s = np.arange(T, dtype=float)
    for j, lane in enumerate(LANES):
        falls = waves["falls"].get(lane, [])
        if falls:
            ts = np.array([c[0] for c in falls])
            vals = np.array([c[1:4] for c in falls], float)
            lo = np.searchsorted(ts, s - WAVE_WINDOW, "left")
            hi = np.searchsorted(ts, s + WAVE_WINDOW, "right")
            for k in np.flatnonzero(hi - lo >= 3):
                m = np.median(vals[lo[k]:hi[k]], axis=0)
                out[k, j, :3] = (round(m[0] * 1000), round(m[1]), round(m[2]))
        for l, side in enumerate(("blue", "red")):
            healths = waves["healths"].get((lane, side), [])
            t0 = np.sort([a for a, _b in healths]) if healths else np.array([])
            t1 = np.sort([b for _a, b in healths]) if healths else np.array([])
            out[:, j, 3 + l] = np.searchsorted(t0, s, "right") - np.searchsorted(t1, s, "right")
    return out


def one(events_path: Path, state_path: Path, game: str, league: str | None, source: str) -> dict:
    """A match's timeline arrays, ready for `np.savez_compressed`."""
    _import_deps()
    import moments as M

    with M.open_file(events_path) as fh:
        ev = M.drop_revived(json.load(fh))
    rows = M.read_state(state_path)
    waves = M.lane_waves(ev)
    T = int(ev["game_length"]) + 1
    roster = ev["players"]
    idx = {p["net_id"]: i for i, p in enumerate(roster)}
    tower_ids = {e["net_id"] for e in ev["events"] if e["type"] == "SetSpell" and "Turret" in (e.get("name") or "")}
    minion_ids = set(waves["minions"])
    monster_ids = {e["net_id"] for e in ev["events"] if e["type"] == "SpawnNeutral"}
    wards_ids = {e["net_id"] for e in ev["events"]
                 if e["type"] == "SpawnMinion" and e.get("character") in M.WARD_UNITS}

    def kind(net) -> str:
        return ("champion" if net in idx else "tower" if net in tower_ids else "minion" if net in minion_ids
                else "monster" if net in monster_ids else "ward" if net in wards_ids else "other")

    def index_of(net) -> int:
        return idx.get(net, -1)

    def xy(pair) -> tuple[int, int]:
        return (round(pair[0]), round(pair[1])) if pair and any(pair) else (NO_DATA, NO_DATA)

    a16, a32, ban = _dense(ev, rows, T)
    arrays = {"champions16": a16, "champions32": a32, "flags": ban, "lane_waves": _dense_waves(waves, T)}
    vocab: dict[str, list[str]] = {}

    # deaths, with the killer (from the same champion's UnitDeath) and who hit them in the ASSIST_WINDOW s before
    hits = collections.defaultdict(list)
    for e in ev["events"]:
        if e["type"] == "Damage" and e["net_id"] in idx and e.get("source") in idx:
            hits[e["net_id"]].append((e["time"], idx[e["source"]]))
    killers = collections.defaultdict(list)
    for e in ev["events"]:
        if e["type"] == "UnitDeath" and e["net_id"] in idx:
            killers[e["net_id"]].append((e["time"], e.get("killer")))
    deaths = _Table(t="f4", who="i1", killer="i1", killer_kind="s", respawns="f4", x="i2", z="i2", hitters="i2")
    for e in ev["events"]:
        if e["type"] != "Death" or e["net_id"] not in idx:
            continue
        i, t = idx[e["net_id"]], e["time"]
        k = min(killers[e["net_id"]], key=lambda a: abs(a[0] - t), default=(t, None))
        killer = k[1] if abs(k[0] - t) <= 2 else None
        s = min(int(t), T - 1)
        hitters = 0
        for tg, j in hits[e["net_id"]]:
            if t - ASSIST_WINDOW <= tg <= t and roster[j]["team"] != roster[i]["team"]:
                hitters |= 1 << j
        deaths.put(t=t, who=i, killer=index_of(killer), killer_kind=kind(killer) if killer else "nobody",
                     respawns=e.get("respawn_time", -1), x=a16[s, i, 0], z=a16[s, i, 1], hitters=hitters)
    deaths.save("deaths", arrays, vocab)

    recalls = _Table(t="f4", who="i1", cancelled="i1", cut_short="i1", rival_near="i2")
    by_name = {p["champion"]: i for i, p in enumerate(roster)}
    for r in M.recalls(ev, rows):
        recalls.put(t=r["time"], who=by_name[r["champion"]], cancelled=r["cancelled"], cut_short=r["cut_short"],
                     rival_near=r["rival_near"] if r["rival_near"] != "" else -1)
    recalls.save("recalls", arrays, vocab)

    camps = _Table(t="f4", camp="s", side="s", killer="i1", killer_kind="s", x="i2", z="i2")
    for c in ev["camps"]:
        x, z = xy(c.get("position"))
        camps.put(t=c["time"], camp=c["camp"], side=c.get("side", ""), killer=index_of(c.get("killer")),
                         killer_kind=kind(c.get("killer")), x=x, z=z)
    camps.save("camps", arrays, vocab)

    spawns = _Table(t="f4", name="s", x="i2", z="i2")
    for e in ev["events"]:
        if e["type"] == "SpawnNeutral":
            x, z = xy(e.get("position"))
            spawns.put(t=e["time"], name=e.get("character") or e.get("name") or "", x=x, z=z)
    spawns.save("spawns", arrays, vocab)

    falls_ = {e["net_id"]: (e["time"], e.get("killer")) for e in ev["events"]
           if e["type"] == "UnitDeath" and e["net_id"] in tower_ids}
    towers = _Table(id="s", team="s", lane="s", rank="s", x="i2", z="i2", falls_="f4")
    for t in M.turrets(ev, waves):
        towers.put(id=t["id"], team=t["team"], lane=t["lane"], rank=t["rank"], x=round(t["x"]),
                    z=round(t["z"]), falls_=falls_.get(t["id"], (-1.0, None))[0])
    towers.save("towers", arrays, vocab)
    falls = _Table(id="s", t="f4", killer="i1", killer_kind="s")
    for net, (t, killer) in sorted(falls_.items(), key=lambda kv: kv[1][0]):
        falls.put(id=net, t=t, killer=index_of(killer), killer_kind=kind(killer))
    falls.save("towers_fallen", arrays, vocab)
    healths = _Table(id="s", t="f4", health="f4")
    for net, series in M.read_turrets(state_path).items():
        for t, v in series:
            healths.put(id=net, t=t, health=v)
    healths.save("towers_health", arrays, vocab)

    # wards, like moments._wards but with the item that places it
    cast = collections.defaultdict(list)
    for e in ev["events"]:
        if e["type"] == "CastSpell" and e["spell"] in M.WARDS:
            cast[round(e["time"], 3)].append((e["net_id"], e.get("target"), e["spell"]))
    died = {e["net_id"]: e["time"] for e in ev["events"] if e["type"] == "UnitDeath"}
    wards = _Table(t="f4", end="f4", x="i2", z="i2", who="i1", item="s")
    for e in ev["events"]:
        if e["type"] == "SpawnMinion" and e.get("character") in M.WARD_UNITS and (own_items := cast.get(round(e["time"], 3))):
            net, where, item = own_items.pop(0)
            x, z = xy(where)
            wards.put(t=e["time"], end=died.get(e["net_id"], -1.0), x=x, z=z, who=index_of(net), item=item)
    wards.save("wards", arrays, vocab)

    minions = _Table(lane="s", side="s", wave="i2", spawned_at="f4", died="f4", advance="f4", x="i2", z="i2",
                      killed_by="i1", killed_by_kind="s", tower="s", earns="i1")
    for s in waves["minions"].values():
        x, z = xy(s["where"])
        minions.put(lane=s["lane"], side=s["side"], wave=s["wave"], spawned_at=s["spawned_at"],
                      died=s["died"] if math.isfinite(s["died"]) else -1.0,
                      advance=s["advance"] if s["advance"] is not None else np.nan, x=x, z=z, killed_by=index_of(s["killed_by"]),
                      killed_by_kind=kind(s["killed_by"]) if s["killed_by"] else "nobody",
                      tower=s["killed_by"] if s["killed_by"] in tower_ids else "", earns=index_of(s["farm"]))
    minions.save("minions", arrays, vocab)

    items = M.fights(ev, rows)
    fights = _Table(since="f4", until="f4", x="i2", z="i2", take_part="i1", teamfight="i1", gold_100="i4",
                    gold_200="i4", deaths_100="i1", deaths_200="i1", who="i2")
    damage_p, taken_p = np.zeros((len(items), 10), np.float32), np.zeros((len(items), 10), np.float32)
    for k, p in enumerate(items):
        fights.put(since=p["since"], until=p["until"], x=p["x"], z=p["z"], take_part=p["take_part"],
                    teamfight=p["teamfight"], gold_100=p["gold_100"], gold_200=p["gold_200"], deaths_100=p["deaths_100"],
                    deaths_200=p["deaths_200"], who=sum(1 << by_name[c] for c in p["who"]))
        for c, v in p["damage"].items():
            damage_p[k, by_name[c]] = v
        for c, v in p["taken"].items():
            taken_p[k, by_name[c]] = v
    fights.save("fights", arrays, vocab)
    arrays["fights.damage"], arrays["fights.taken"] = damage_p, taken_p

    damage = _Table(t="f4", source="i1", a="i1", amount="f4", kind="s", spell="s")
    casts = _Table(t="f4", who="i1", gap="i1", spell="s", cooldown="f4", ox="i2", oz="i2", dx="i2", dz="i2")
    purchases = _Table(t="f4", who="i1", item="i4")
    gold = _Table(t="f4", who="i1", amount="f4", source="s")
    headings = _Table(t="f4", who="i1", x="i2", z="i2")
    for e in ev["events"]:
        ty = e["type"]
        if ty == "Damage" and e["net_id"] in idx and e.get("source") in idx:
            damage.put(t=e["time"], source=idx[e["source"]], a=idx[e["net_id"]], amount=e.get("amount", 0.0),
                      kind=e.get("damage_type", ""), spell=e.get("spell", ""))
        elif ty == "CastSpell" and e["net_id"] in idx:
            ox, oz = xy(e.get("origin"))
            dx, dz = xy(e.get("target"))
            casts.put(t=e["time"], who=idx[e["net_id"]], gap=e.get("slot", -1), spell=e.get("spell", ""),
                       cooldown=e.get("cooldown", -1.0), ox=ox, oz=oz, dx=dx, dz=dz)
        elif ty == "BuyItem" and e["net_id"] in idx:
            purchases.put(t=e["time"], who=idx[e["net_id"]], item=e.get("item_id", -1))
        elif ty == "Gold" and e["net_id"] in idx:
            gold.put(t=e["time"], who=idx[e["net_id"]], amount=e.get("amount", 0.0), source=kind(e.get("unit")))
        elif ty.startswith("WaypointGroup"):
            for u in e["units"]:
                if u["net_id"] in idx and u.get("path"):
                    x, z = xy(u["path"][-1])
                    headings.put(t=e["time"], who=idx[u["net_id"]], x=x, z=z)
    for name, table in (("damage", damage), ("casts", casts), ("purchases", purchases), ("gold", gold), ("headings", headings)):
        table.save(name, arrays, vocab)

    controls = _Table(t="f4", a="i1", source="i1", kind="s", duration="f4", spell="s")
    for c in ev.get("controls") or []:
        if c["net_id"] in idx:
            controls.put(t=c["time"], a=idx[c["net_id"]], source=index_of(c.get("caster")), kind=c.get("type", ""),
                           duration=c.get("duration", 0.0), spell=c.get("buff", ""))
    controls.save("controls", arrays, vocab)
    finishes = _Table(t="f4", who="i1", unit="s", how_many="i2")
    for c in ev.get("creeps") or []:
        if c["net_id"] in idx:
            finishes.put(t=c["time"], who=idx[c["net_id"]], unit=c.get("character", ""), how_many=c.get("count", 1))
    finishes.save("finishes", arrays, vocab)
    attacks = _Table(t="f4", who="i1", unit="s")
    for c in ev.get("attacks") or []:
        if c["net_id"] in idx:
            attacks.put(t=c["time"], who=idx[c["net_id"]], unit=kind(c.get("unit")))
    attacks.save("attacks", arrays, vocab)
    buffs = _Table(t="f4", who="i1", buff="s", source="i1", kind="s", duration="f4")
    for e in ev["events"]:
        if e["type"] == "AddBuff" and e["net_id"] in idx:
            buffs.put(t=e["time"], who=idx[e["net_id"]], buff=e.get("buff", ""), source=index_of(e.get("caster")),
                       kind=e.get("buff_type", ""), duration=e.get("duration", -1.0))
    buffs.save("buffs", arrays, vocab)

    arrays["corridors"] = np.array([(cx, cz, LANES.index(c)) for (cx, cz), cs in waves["corridors"].items()
                                   for c in sorted(cs)], np.int16).reshape(-1, 3)
    stats = ev.get("stats") or [{}] * len(roster)
    meta = {"version": VERSION, "game": game, "league": league or "", "source": source,
            "duration": ev["game_length"], "seconds": T, "cell": M.CELL,
            "players": [{"champion": p["champion"], "team": p["team"], "position": p["position"],
                           "net_id": p["net_id"],
                           "spells": [s.get("SUMMONER_SPELL_1", ""), s.get("SUMMONER_SPELL_2", "")],
                           "wins": int(s["WIN"] == "Win") if "WIN" in s else -1} for p, s in zip(roster, stats)],
            "bases": {eq: list(v) for eq, v in M._bases(rows).items()},
            "waves": {"barracks": {b: list(v) for b, v in waves["barracks"].items()}, "axis": waves["axis"],
                     "output": waves["output"]},
            "turrets": sorted(tower_ids),
            "stats": [{k: v for k, v in s.items() if not k[:1].isdigit()} for s in stats],
            "columns": {"champions16": C16, "champions32": C32, "flags": FLAGS,
                         "lane_waves": ("advance_x1000", "x", "z", "alive_blue", "alive_red"), "lanes": LANES},
            "vocab": vocab, "origin": [str(events_path), str(state_path)]}
    arrays["meta"] = np.frombuffer(json.dumps(meta).encode("utf-8"), dtype=np.uint8)
    return arrays


def _one(args: tuple) -> tuple[str, int, float, str]:
    pid, evs, st, source, league, dest = args
    t0 = time.time()
    try:
        arrays = one(evs, st, pid, league, source)
    except Exception as e:  # a strange match doesn't stop the others
        return pid, 0, time.time() - t0, f"{type(e).__name__}: {e}"
    tmp = dest / f"{pid}.tmp.npz"
    np.savez_compressed(tmp, **arrays)
    tmp.replace(dest / f"{pid}.npz")
    return pid, (dest / f"{pid}.npz").stat().st_size, time.time() - t0, ""


def _up_to_date(path: Path) -> bool:
    """Whether it is already made with this VERSION."""
    if not path.exists():
        return False
    try:
        with np.load(path) as d:
            return json.loads(bytes(d["meta"]).decode("utf-8")).get("version") == VERSION
    except Exception:  # half-written or of another shape: it is redone
        return False


def cmd_extract(output: Path, processes: int, time_limit: float | None, only: int | None) -> None:
    """Resumable, like `routes.py rows`: each match leaves its file and the next round skips those done. With
    `only`, a sample spread over the whole corpus (to measure before launching everything)."""
    _import_deps()
    import policy as P

    output.mkdir(parents=True, exist_ok=True)
    cache = YGG / "research" / "ladder" / "data" / "policy" / "leagues.json"
    league = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else P.leagues()
    failed = set()
    if (output / "errors.log").exists():
        failed = {x.split("\t")[0] for x in (output / "errors.log").read_text(encoding="utf-8").splitlines()}
    all_ = P.sources()
    if only:
        all_ = [all_[round(k)] for k in np.linspace(0, len(all_) - 1, only)]
    queue = [(pid, evs, st, src, league.get(pid), output) for pid, evs, st, src in all_
            if not _up_to_date(output / f"{pid}.npz") and pid not in failed]
    total = len(queue)
    print(f"{len(all_)} games · {total} pending · {processes} processes", flush=True)
    t0, done, bytes_, seconds = time.time(), 0, 0, 0.0
    with ProcessPoolExecutor(processes) as pool, (output / "errors.log").open("a", encoding="utf-8") as err:
        running = set()
        while queue or running:
            while queue and len(running) < 2 * processes and (time_limit is None or time.time() - t0 < time_limit):
                running.add(pool.submit(_one, queue.pop(0)))
            if not running:
                break
            done_ = next(as_completed(running))
            running.discard(done_)
            pid, size, sec, notice = done_.result()
            done, bytes_, seconds = done + 1, bytes_ + size, seconds + sec
            if notice:
                err.write(f"{pid}\t{notice}\n")
                err.flush()
    mean = bytes_ / max(1, done)
    print(f"done {done} · {bytes_ / 1e6:.1f} MB ({mean / 1e3:.0f} KB per game) · "
          f"{seconds / max(1, done):.2f} s per game · {total - done} left · {time.time() - t0:.0f} s", flush=True)


# ---------------------------------------------------------------- for the analyses: reading it

class Timeline:
    """A match read from its `.npz`. Champions go by index (0-9, the order of `players`)."""

    def __init__(self, path: Path) -> None:
        self._d = np.load(path, allow_pickle=False)
        self.meta = json.loads(bytes(self._d["meta"]).decode("utf-8"))
        self.players = self.meta["players"]
        self.T = self.meta["seconds"]
        self.c16, self.c32, self.flags = self._d["champions16"], self._d["champions32"], self._d["flags"]
        self.lane_waves = self._d["lane_waves"]
        self._tables: dict[str, dict[str, np.ndarray]] = {}

    def i(self, champion: str) -> int:
        return next(k for k, p in enumerate(self.players) if p["champion"] == champion)

    def series(self, field: str, i: int) -> np.ndarray:
        """A champion's column, one value per second (float, nan without data)."""
        if field in C16:
            v = self.c16[:, i, C16.index(field)].astype(float)
            v[v == NO_DATA] = np.nan
        else:
            v = self.c32[:, i, C32.index(field)].astype(float)
        return v

    def flag(self, name: str, i: int) -> np.ndarray:
        return (self.flags[:, i] >> FLAGS.index(name)) & 1 == 1

    def at(self, field: str, i: int, t: float) -> float | None:
        s = min(max(int(t), 0), self.T - 1)
        v = self.series(field, i)[s]
        return None if np.isnan(v) else float(v)

    def wave(self, lane: str, t: float, team: str = "100") -> float | None:
        """Where that lane's front is (0, their turret; 1, the enemy's) seen from `team`; None if unknown."""
        a = self.lane_waves[min(max(int(t), 0), self.T - 1), LANES.index(lane), 0]
        if a == NO_DATA:
            return None
        return a / 1000 if team == "100" else 1 - a / 1000

    def table(self, name: str) -> dict[str, np.ndarray]:
        """An event table as columns; the text ones, already with their text."""
        if name not in self._tables:
            pre = f"{name}."
            cols = {}
            for k in self._d.files:
                if k.startswith(pre):
                    c = k[len(pre):]
                    v = self._d[k]
                    if f"{name}.{c}" in self.meta["vocab"]:
                        v = np.array(self.meta["vocab"][f"{name}.{c}"], dtype=object)[v] if len(v) else v.astype(object)
                    cols[c] = v
            self._tables[name] = cols
        return self._tables[name]


def load(path: Path) -> Timeline:
    return Timeline(Path(path))


# ---------------------------------------------------------------- for the earlier code: rehydrating

STATE_ORDER = ("time", "net_id", "champion", "team", "x", "z", "alive", "seen", "vision_changes", "enemy_dist",
                "ally_dist", "cs", "target", "cc", "gold", "total_gold", "xp", "level", "jungle_minions", "health",
                "health_max", "mana", "mana_max", "move_speed", "attack_speed", "lifesteal", "q_ready", "w_ready",
                "e_ready", "r_ready", "d_ready", "f_ready")


def rehydrate(L: Timeline) -> tuple[dict, object, dict]:
    """(events, rows, waves) with the shape left by `moments.drop_revived`, `moments.read_state` and
    `moments.lane_waves`, but taken from the timeline: that way the code that already exists (`routes`, `policy`…) runs
    on it unchanged. Each gap in the table carries its last value (the original left it blank). What wasn't
    stored doesn't come back: the minions' and monsters' ids are made up, of whoever kills a minion only
    a champion or a turret remains, and of a row `target`, `vision_changes`, `attack_speed` and
    `lifesteal` are not left."""
    _import_deps()
    import moments as M

    roster, net = L.players, [p["net_id"] for p in L.players]

    def n(i) -> str | None:
        return net[int(i)] if int(i) >= 0 else None

    def spot(x, z) -> list[int] | None:
        return None if int(x) == NO_DATA else [int(x), int(z)]

    ev: list[dict] = [{"type": "SetSpell", "time": 0.0, "net_id": t, "name": "TurretBasicAttack"}
                      for t in L.meta.get("turrets", [])]
    m = L.table("deaths")
    for k in range(len(m["t"])):
        t, i = float(m["t"][k]), int(m["who"][k])
        ev.append({"type": "Death", "time": t, "net_id": net[i], "respawn_time": float(m["respawns"][k])})
        ev.append({"type": "UnitDeath", "time": t, "net_id": net[i], "killer": n(m["killer"][k]),
                   "position": spot(m["x"][k], m["z"][k]) or [0, 0]})
    # minions: their births and deaths in the events, and the wave as left by moments.lane_waves
    all_barracks = {(side, lane): b for b, (side, lane) in L.meta["waves"]["barracks"].items()}
    s = L.table("minions")
    minions, falls, healths = {}, collections.defaultdict(list), collections.defaultdict(list)
    groups: dict[tuple, dict] = {}
    for k in range(len(s["spawned_at"])):
        sid, lane, side = f"s{k}", str(s["lane"][k]), str(s["side"][k])
        spawned_at, died = float(s["spawned_at"][k]), float(s["died"][k])
        died = math.inf if died < 0 else died
        where = spot(s["x"][k], s["z"][k])
        advance = None if math.isnan(float(s["advance"][k])) else float(s["advance"][k])
        killed_by = n(s["killed_by"][k]) or (str(s["tower"][k]) or None)
        minions[sid] = {"side": side, "lane": lane, "wave": int(s["wave"][k]), "spawned_at": spawned_at, "died": died,
                         "advance": advance, "where": where, "farm": n(s["earns"][k]), "killed_by": killed_by}
        healths[(lane, side)].append((spawned_at, died))
        if advance is not None:
            falls[lane].append((died, advance, where[0], where[1]))
        g = groups.setdefault((lane, side, int(s["wave"][k])), {"spawned_at": spawned_at, "minions": []})
        g["spawned_at"] = min(g["spawned_at"], spawned_at)
        g["minions"].append(sid)
        ev.append({"type": "SpawnLaneMinion", "time": spawned_at, "net_id": sid, "barracks": all_barracks.get((side, lane))})
        if math.isfinite(died):
            ev.append({"type": "UnitDeath", "time": died, "net_id": sid, "killer": killed_by, "position": where or [0, 0]})
    for g in groups.values():
        g["cannon"] = len(g["minions"]) >= 7
    corridors = collections.defaultdict(set)
    for cx, cz, c in L._d["corridors"]:
        corridors[(int(cx), int(cz))].add(LANES[int(c)])
    waves = {"barracks": {b: tuple(v) for b, v in L.meta["waves"]["barracks"].items()}, "axis": L.meta["waves"]["axis"],
            "falls": {c: sorted(v) for c, v in falls.items()}, "healths": {k: sorted(v) for k, v in healths.items()},
            "minions": minions, "waves": groups, "output": L.meta["waves"]["output"], "corridors": dict(corridors)}

    a = L.table("spawns")
    for k in range(len(a["t"])):
        ev.append({"type": "SpawnNeutral", "time": float(a["t"][k]), "net_id": f"n{k}", "name": str(a["name"][k]),
                   "character": str(a["name"][k]), "position": spot(a["x"][k], a["z"][k]) or [0, 0]})
    tc = L.table("towers_fallen")
    for k in range(len(tc["t"])):
        ev.append({"type": "UnitDeath", "time": float(tc["t"][k]), "net_id": str(tc["id"][k]),
                   "killer": n(tc["killer"][k]), "position": [0, 0]})
    w = L.table("wards")
    for k in range(len(w["t"])):
        character = "JammerDevice" if w["item"][k] == "JammerDevice" else "SightWard"
        ev.append({"type": "SpawnMinion", "time": float(w["t"][k]), "net_id": f"w{k}", "name": character,
                   "character": character})
        if w["end"][k] >= 0:
            ev.append({"type": "UnitDeath", "time": float(w["end"][k]), "net_id": f"w{k}", "killer": None,
                       "position": [0, 0]})
    d = L.table("damage")
    for k in range(len(d["t"])):
        ev.append({"type": "Damage", "time": float(d["t"][k]), "net_id": net[int(d["a"][k])],
                   "source": net[int(d["source"][k])], "amount": float(d["amount"][k]),
                   "damage_type": str(d["kind"][k]), "spell": str(d["spell"][k])})
    c = L.table("casts")
    for k in range(len(c["t"])):
        ev.append({"type": "CastSpell", "time": float(c["t"][k]), "net_id": net[int(c["who"][k])],
                   "spell": str(c["spell"][k]), "slot": int(c["gap"][k]), "cooldown": float(c["cooldown"][k]),
                   "origin": spot(c["ox"][k], c["oz"][k]), "target": spot(c["dx"][k], c["dz"][k])})
    for name, kind, fields in (("purchases", "BuyItem", {"item_id": "item"}), ("gold", "Gold", {"amount": "amount"}),
                                 ("buffs", "AddBuff", {"buff": "buff", "buff_type": "kind", "duration": "duration"})):
        tb = L.table(name)
        for k in range(len(tb["t"])):
            e = {"type": kind, "time": float(tb["t"][k]), "net_id": net[int(tb["who"][k])]}
            for key, col in fields.items():
                v = tb[col][k]
                e[key] = v.item() if hasattr(v, "item") else v
            if kind == "AddBuff":
                e["caster"] = n(tb["source"][k])
            if kind == "Gold":
                e["unit"] = None
            ev.append(e)
    r = L.table("headings")
    for k in range(len(r["t"])):
        ev.append({"type": "WaypointGroup", "time": float(r["t"][k]),
                   "units": [{"net_id": net[int(r["who"][k])], "speed": 0.0,
                              "path": [spot(r["x"][k], r["z"][k]) or [0, 0]]}]})
    ev.sort(key=lambda e: e["time"])

    cm = L.table("camps")
    camps = [{"camp": str(cm["camp"][k]), "side": str(cm["side"][k]), "time": float(cm["t"][k]),
              "killer": n(cm["killer"][k]), "position": spot(cm["x"][k], cm["z"][k]) or [0, 0]}
             for k in range(len(cm["t"]))]
    ctrl = L.table("controls")
    controls = [{"type": str(ctrl["kind"][k]), "time": float(ctrl["t"][k]), "net_id": net[int(ctrl["a"][k])],
                 "caster": n(ctrl["source"][k]), "buff": str(ctrl["spell"][k]), "duration": float(ctrl["duration"][k])}
                for k in range(len(ctrl["t"]))]
    re = L.table("finishes")
    creeps = [{"time": float(re["t"][k]), "net_id": net[int(re["who"][k])], "unit": None,
               "character": str(re["unit"][k]), "count": int(re["how_many"][k])} for k in range(len(re["t"]))]
    at = L.table("attacks")
    attacks = [{"time": float(at["t"][k]), "net_id": net[int(at["who"][k])], "unit": None}
               for k in range(len(at["t"]))]
    events = {"game_length": L.meta["duration"],
               "players": [{"net_id": p["net_id"], "champion": p["champion"], "team": p["team"],
                            "position": p["position"]} for p in roster],
               "stats": [] if not any(L.meta.get("stats") or []) else L.meta["stats"], "events": ev, "camps": camps,
               "creeps": creeps,
               "controls": controls, "attacks": attacks}

    rows = M.StateTable()
    for i, p in enumerate(roster):
        there_are = np.flatnonzero(L.flag("row", i))
        cols16 = {c: L.c16[there_are, i, k] for k, c in enumerate(C16)}
        cols32 = {c: L.c32[there_are, i, k] for k, c in enumerate(C32)}
        bits = {c: L.flag(c, i)[there_are] for c in FLAGS[1:]}
        for j, sgd in enumerate(there_are):
            f = dict.fromkeys(STATE_ORDER, "")
            f.update(time=f"{sgd}.0", net_id=p["net_id"], champion=p["champion"], team=p["team"])
            for col, v in cols16.items():
                f[col] = "" if v[j] == NO_DATA else str(int(v[j]))
            for col, v in cols32.items():
                f[col] = "" if np.isnan(v[j]) else format(float(v[j]), ".7g")
            for col, v in bits.items():
                f[col] = ("True" if v[j] else "") if col == "cc" else ("True" if v[j] else "False")
            rows[p["champion"]].append(f)
    return events, rows, waves


# ---------------------------------------------------------------- checking against routes.py

def _same(a, b, tol: float) -> bool | None:
    try:
        a, b = float(a), float(b)
    except (TypeError, ValueError):
        return None
    if math.isnan(a) or math.isnan(b):
        return None
    return abs(a - b) <= tol


def cmd_check(output: Path, routes: Path) -> None:
    """Redoes, with only the timeline, what `routes.py rows` extracted from each of the jungler's decisions (the moments of
    deciding, their level, health, gold, where each wave is, when the enemy jungler was seen, whether they die in 90 s and the
    gold against the enemy), and counts how many times it matches."""
    import csv
    import gzip

    count = collections.Counter()
    ok = collections.Counter()
    examples = collections.defaultdict(list)
    for file in sorted(output.glob("*.npz")):
        L = load(file)
        pid = L.meta["game"]
        route_rows = routes / "games" / f"{pid}.csv.gz"
        if not route_rows.exists():
            continue
        with gzip.open(route_rows, "rt", encoding="utf-8") as fh:
            expected_ones = [f for f in csv.DictReader(fh) if f["decision"] != "0"]
        cmp = L.table("camps")
        deaths = L.table("deaths")
        for f in expected_ones:
            i, rival = L.i(f["jungler"]), L.i(f["rival_jungler"]) if f["rival_jungler"] else None
            t = float(f["t"])
            team = L.players[i]["team"]
            # the moment: a camp they kill in that second
            killed_by = np.flatnonzero((cmp["killer"] == i) & (np.abs(cmp["t"] - t) < 0.06))
            count["moment"] += 1
            ok["moment"] += len(killed_by) > 0
            s = int(t)
            health, max_v = L.at("health", i, t), L.at("health_max", i, t)
            checks = {
                "level": (f["level"], L.at("level", i, t), 0),
                "health": (f["health"], health / max_v if health is not None and max_v and L.flag("alive", i)[s] else None, 0.02),
                "gold_unspent": (f["gold_unspent"], L.at("gold", i, t), 2),
                "dies_in_horizon": (f["dies_in_horizon"], int(bool(np.any(
                    (deaths["who"] == i) & (deaths["t"] > t) & (deaths["t"] <= t + 90)))), 0),
            }
            for lane in LANES:
                o = L.wave(lane, t, team)
                checks[f"{lane}_wave"] = (f[f"{lane}_wave"], 0.5 if o is None else min(1.0, max(0.0, o)), 0.05)
            if rival is not None:
                sighted = L.flag("seen", rival) & L.flag("row", rival)
                before = np.flatnonzero(sighted[max(0, s - 599):s + 1])
                does = t - (max(0, s - 599) + before[-1]) if len(before) else 600
                checks["rival_seen_ago"] = (f["rival_seen_ago"], does, 1.0)
                if t + 90 < L.T:
                    a = (L.at("total_gold", i, t) or 0) - (L.at("total_gold", rival, t) or 0)
                    b = (L.at("total_gold", i, t + 90) or 0) - (L.at("total_gold", rival, t + 90) or 0)
                    checks["gold_vs_rival_change"] = (f["gold_vs_rival_change"], b - a, 15)
            for field, (expected, is_new, tol) in checks.items():
                r = _same(expected, is_new, tol)
                if r is None:
                    count[f"{field} (no data in routes)"] += 1 if expected in ("", None) else 0
                    continue
                count[field] += 1
                ok[field] += r
                if not r and len(examples[field]) < 3:
                    examples[field].append(f"{pid} {f['jungler']} {t}: routes {expected} · timeline {is_new}")
    print(f"{len(list(output.glob('*.npz')))} games\n")
    print("| field | decisions | adds up |\n|---|---|---|")
    for field in sorted(count):
        if "no data" in field:
            print(f"| {field} | {count[field]} | (the timeline does have it) |")
        else:
            print(f"| {field} | {count[field]} | {ok[field] / max(1, count[field]):.1%} |")
    for field, items in examples.items():
        print(f"\n{field}:\n  " + "\n  ".join(items))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("command", choices=["extract", "check"])
    ap.add_argument("output", type=Path)
    ap.add_argument("--processes", type=int, default=2)
    ap.add_argument("--time-limit", type=float, default=None)
    ap.add_argument("--only", type=int, default=None)
    ap.add_argument("--routes", type=Path, default=None)
    a = ap.parse_args()
    if a.command == "extract":
        cmd_extract(a.output, a.processes, a.time_limit, a.only)
    else:
        cmd_check(a.output, a.routes)


if __name__ == "__main__":
    main()
