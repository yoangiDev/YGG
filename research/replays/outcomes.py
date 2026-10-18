"""The jungler's outcome tree: each option by what usually happens afterwards and what each thing is worth.

    python research/replays/outcomes.py wave <output> --timelines <dir of .npz>                        # scikit-learn
    python research/replays/outcomes.py extract <output> --timelines <dir of .npz> --decisions <decisions.csv.gz>
    python research/replays/outcomes.py analyse <output> --decisions <valued_decisions.pkl> \\
        --routes-model-file <routes_model.pkl>                                                   # scikit-learn
    python research/replays/outcomes.py correct <output> --decisions <valued_decisions.pkl>   # scikit-learn
    python research/replays/outcomes.py game <output> <EUW1-123> <champion> \\
        --rows <games/EUW1-123.csv.gz from routes.py rows>

Measuring an option by how much it changes its team's WP over the following minutes drags in everything that happens on the map:
with 5,000 matches, the value of an option state by state isn't learned that way (see `routes.md`). Here each option is
split into what happens in the following `WINDOW` s (`OUTCOMES`), and:

1. **what each outcome is worth** comes from all the decisions at once: the change in their team's WP (what remains
   over what was expected in that state, `routes_model.centre`) against how much each thing happens, at 90 s and at 5 min, with its
   interval resampling matches;
2. **what usually happens with each option in each state** is learned by a model per outcome, with the option as one more
   feature and **only what the player knew** (it is the decision that is judged, not what came out);
3. **what an option is worth in a state** is the sum of each expected outcome times what it is worth.

Second version, because of what the first failed at (`outcomes.md`):

- **Options go by intention** (`options`), not by what happened: where the jungler goes after the camp,
  whether or not there is a fight. Going to a lane is being `IN_LANE` consecutive s in it, between the two turrets, with an enemy of that
  lane within `NEAR_LANE`; within that, **dive** is getting into the range of a live enemy turret with an
  enemy under it, and **counter-gank**, arriving with the enemy jungler already there. Before, a gank was only one that got to fight.
- **The wave is the one that was seen and the one that will be on arrival** (`wave`): the front with the minions already fallen (before
  it was measured with those falling up to 20 s later) and a model that, from that, how many minions remain on each side and how it
  was moving, predicts where it will be when the jungler arrives. A wave that crashes into the enemy turret comes back on its own.
- **More outcomes**: the lanes' CS, the turret and plate gold of each side, and the jungler's health, mana and spent
  gold.

`correct` compares what each option is worth in the tree with what was measured, adjusted for who chooses each thing
(`cmd_correct`), and tries to correct it state by state: with this data, that correction comes out as noise, and `game` doesn't use it.

`analyse` checks, with matches the models haven't seen, whether those state-by-state values hold, and whether
the tree reproduces what was measured directly (the gank according to where the wave will be, going back to base according to gold and health).
"""

from __future__ import annotations

import argparse
import collections
import pickle
import sys
import zlib
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
WINDOW = 90.0  # seconds after the decision in which outcomes are counted
NEAR = 3000.0  # an ally falls "near" if it falls within this of the jungler
FLASH_NEAR = 2000.0  # an enemy flash counts as forced if it is spent within this of the jungler
GOLD = ("Gromp", "Wolves", "Raptors", "Krugs", "Blue", "Red")
EPICS = ("Dragon", "Voidgrub", "Herald", "Baron", "Atakhan")
LANES = ("top", "mid", "bot")

# the options by intention
INTENT = 75  # s after the decision in which it is looked at where they go (like FIRST in routes.py)
IN_LANE = {0: 4, 1: 5, 2: 4}  # consecutive s in a lane to count as having gone to it (mid is crossed often: 5)
NEAR_LANE = 3000.0  # and in those seconds, a live enemy of that lane within this: otherwise, they were just passing through
OUTSIDE = (0.25, 0.80)  # part of the lane that counts (advance from their team): neither against their base nor the enemy's
MID_WIDTH = 650.0  # half-width of the mid lane from the diagonal x = z: the raptors are about 1,100 away
IN_RIVAL_JUNGLE = 4  # s in the enemy jungle to count as invading
IN_RIVER = 8  # consecutive s in the river, if they do nothing else, to count as having gone to the river
RIVER = 1500.0  # half-width of the river over x + z
BASE = 3000.0
DIVE = 800.0  # a turret's range (750) plus the champion's size
UNDER_TOWER = 900.0  # an enemy "under their turret"
DIVE_UNTIL = 30  # s after reaching the lane in which it is looked at whether they go under the turret
BEFORE_COUNTER, TOGETHER = 20, 3000.0  # counter-gank: the enemy jungler within TOGETHER of where they arrive, in the 20 s before
OPTIONS = ("camp", "base", "invade", "crab", "objective", "river",
            "gank top", "gank mid", "gank bot", "dive top", "dive mid", "dive bot",
            "contragank top", "contragank mid", "contragank bot")

# the wave
WAVE_WINDOW = 15.0  # the front that is seen: the median of where the minions fell in these s before
ARRIVES = (3.0, 45.0)  # how long it takes to reach a lane, bounded
DETOUR = 1.3  # how much the path lengthens compared with the straight line
WAVE_COLS = ["wave_pos", "age", "change_10", "change_20", "alive_blue", "alive_red", "alive_diff", "minute", "phase",
            "lane", "delta"]
CENTER = {"top": (2500.0, 12300.0), "mid": (7400.0, 7400.0), "bot": (12300.0, 2500.0)}
# where each turret usually is if the match doesn't carry it (median of 200 matches)
TOWERS = {("100", "bot", "OUTER_TURRET"): (10913, 1302), ("100", "bot", "INNER_TURRET"): (7472, 1296),
          ("100", "mid", "OUTER_TURRET"): (6390, 6620), ("100", "mid", "INNER_TURRET"): (5124, 5215),
          ("100", "top", "OUTER_TURRET"): (1186, 10894), ("100", "top", "INNER_TURRET"): (1290, 7230),
          ("200", "bot", "OUTER_TURRET"): (13685, 4036), ("200", "bot", "INNER_TURRET"): (13492, 7668),
          ("200", "mid", "OUTER_TURRET"): (8416, 8294), ("200", "mid", "INNER_TURRET"): (9598, 9732),
          ("200", "top", "OUTER_TURRET"): (3846, 13654), ("200", "top", "INNER_TURRET"): (7368, 13541)}

OUTCOMES = ("kills_with_him", "kills_without_him", "he_dies", "allies_fall_near", "allies_fall_far", "flash_rival",
              "flash_own", "camps_stolen", "camps_lost", "camps_own", "farms_the_rival",
              "crabs_own", "crabs_rival", "objectives_own", "objectives_rival",
              "cs_lane", "tower_own", "rival_tower", "health_change", "mana_change", "gold_spent")
CONTINUOUS = ("cs_lane", "health_change", "mana_change")  # they can be negative: squared error, not Poisson
NAMES = {"kills_with_him": "kill they take part in", "kills_without_him": "kill by their team without them",
           "he_dies": "he dies", "allies_fall_near": "an ally falls next to them",
           "allies_fall_far": "an ally falls far away", "flash_rival": "forces a rival flash",
           "flash_own": "spends their flash", "camps_stolen": "stolen camp",
           "camps_lost": "lost camp", "camps_own": "own camp",
           "farms_the_rival": "rival jungler's camp", "crabs_own": "crab for their team",
           "crabs_rival": "crab for the rival", "objectives_own": "objective for their team",
           "objectives_rival": "objective for the rival", "cs_lane": "10 CS of lead in the lanes",
           "tower_own": "100 gold of towers and plates for their team",
           "rival_tower": "100 gold of towers and plates for the rival",
           "health_change": "jungler's health (0 to 1 more)", "mana_change": "jungler's mana (0 to 1 more)",
           "gold_spent": "100 gold spent by the jungler"}
# each lane's features that weigh in a gank: flashes, abilities, vision, levels and who is who
LEVELS = np.cumsum([0, 280] + [380 + 100 * k for k in range(16)])  # experience for each level, from 1 to 18
FLASH = "4"  # the flash id in the spells of `meta.players` (the first goes in d_ready, the second in f_ready)
WARD_LASTS = {"TrinketTotemLvl1": 120.0, "ItemGhostWard": 150.0, "JammerDevice": 900.0}  # if the replay doesn't carry the end
WARD_NEAR = 2500.0  # a ward counts for a lane if it is within this of the wave's front
WARD_PATH = 1200.0  # or, the enemy's, within this of the jungler's straight path to that front
GANK_KILL = 30.0  # s after reaching the lane in which it is looked at whether the gank ends in a kill of an enemy of that lane
OF_LANE = ("wave_seen", "wave_arrives", "arrives_s", "minions_diff", "flash_ally", "r_rival", "abilities_rival",
            "abilities_ally", "wards_own", "levels_diff")
OMNISCIENT_LANE = ("wards_rival", "wards_rival_path")  # the jungler doesn't know where they are: only to check
CHAMPIONS = ("champion_rival", "champion_rival2", "champion_ally", "champion_ally2")
OWN = ("flash_ready_own", "r_own", "abilities_own", "level_xp")  # without clashing with the flash_own outcome
STATE = [f"{c}_{x}" for c in LANES for x in OF_LANE] + list(OWN)
HORIZONS = {90: "centred_value_90", 300: "centred_value_300"}
MOMENTS = ((1, 2), (3, 6), (7, 999))  # what each option is worth by itself, separately in each stretch
FOLDS = 3


def _import_deps() -> None:
    sys.path[:0] = [str(HERE), str(HERE.parents[1] / "packages" / "ygg-core" / "src")]


def _half(pid: str) -> int:
    """Which half of the matches each one goes to, so that one match's wave is predicted by the other half's model."""
    return zlib.crc32(pid.encode()) % 2


# ---------------------------------------------------------------- the wave that was seen and the one that will be on arrival

def wave_seen(L) -> np.ndarray:
    """(T, 3, 4): each second and lane, the front that was seen (advance from blue, x, z) with the minions that had already
    fallen in the WAVE_WINDOW s before, carrying forward the last known one, and the seconds since it was seen."""
    import timeline

    sb = L.table("minions")
    out = np.full((L.T, 3, 4), np.nan)
    s = np.arange(L.T, dtype=float)
    # one in four minions dies with no known position (advance nan): out, or the median comes out nan
    valid = (sb["died"] > 0) & np.isfinite(sb["advance"].astype(float)) & (sb["x"] != timeline.NO_DATA)
    for j, c in enumerate(LANES):
        m = (sb["lane"] == c) & valid
        ts = sb["died"][m].astype(float)
        o = np.argsort(ts)
        ts = ts[o]
        vals = np.column_stack([sb["advance"][m][o], sb["x"][m][o], sb["z"][m][o]]).astype(float)
        lo, hi = np.searchsorted(ts, s - WAVE_WINDOW, "left"), np.searchsorted(ts, s, "right")
        ult, when = None, 0
        for k in range(L.T):
            if hi[k] - lo[k] >= 3:
                ult, when = np.median(vals[lo[k]:hi[k]], axis=0), k
            if ult is not None:
                out[k, j, :3], out[k, j, 3] = ult, k - when
    return out


def _wave_features(L, view: np.ndarray, s: int, j: int) -> list[float]:
    """What is known at second s of lane j's wave, seen from blue (without the `delta`)."""
    a = view[s, j, 0]
    vz, vr = float(L.lane_waves[s, j, 3]), float(L.lane_waves[s, j, 4])
    return [a, view[s, j, 3], a - view[max(s - 10, 0), j, 0], a - view[max(s - 20, 0), j, 0], vz, vr, vz - vr,
            s / 60.0, (s - L.meta["waves"]["output"]) % 30, float(j)]


def _wave_samples(L, every: int = 7) -> tuple[list, list]:
    """For training: the front seen at s and the real (centred) one at s + Δ, with Δ random."""
    import timeline

    view = wave_seen(L)
    truth = L.lane_waves[:, :, 0].astype(float)
    truth[truth == timeline.NO_DATA] = np.nan
    truth /= 1000
    rng = np.random.default_rng(zlib.crc32(L.meta["game"].encode()))
    X, y = [], []
    for s in range(60, min(L.T - int(ARRIVES[1]) - 1, 840), every):
        for j in range(3):
            d = int(rng.integers(ARRIVES[0], ARRIVES[1] + 1))
            if np.isnan(view[s, j, 0]) or np.isnan(truth[s + d, j]):
                continue
            X.append(_wave_features(L, view, s, j) + [d])
            y.append(truth[s + d, j])
    return X, y


def _wave_model():
    from sklearn.ensemble import HistGradientBoostingRegressor

    return HistGradientBoostingRegressor(loss="absolute_error", max_iter=300, learning_rate=0.08, max_leaf_nodes=31,
                                         min_samples_leaf=100, categorical_features=[c == "lane" for c in WAVE_COLS],
                                         random_state=0)


def cmd_wave(output: Path, timelines: Path, per_half: int = 1300) -> None:
    """Two models of where the wave will be, one with each half of the matches, and its error on the other half."""
    _import_deps()
    import timeline

    output.mkdir(parents=True, exist_ok=True)
    data = {0: ([], [], 0), 1: ([], [], 0)}
    for f in sorted(timelines.glob("*.npz")):
        h = _half(f.stem)
        X, y, n = data[h]
        if n >= per_half:
            continue
        Xp, yp = _wave_samples(timeline.load(f))
        data[h] = (X + Xp, y + yp, n + 1)
    models = {h: _wave_model().fit(pd.DataFrame(data[h][0], columns=WAVE_COLS), np.array(data[h][1])) for h in (0, 1)}
    print(f"# Where the wave will be\n\n{data[0][2]:,d} + {data[1][2]:,d} games, {len(data[0][1]):,d} + "
          f"{len(data[1][1]):,d} samples. Mean error (in advance, from 0 to 1 between the two barracks) with the other half "
          "of the games, against keeping the one that is seen.\n")
    print("| within | the model | the one seen |\n|---|---|---|")
    X, y = pd.DataFrame(data[1][0], columns=WAVE_COLS), np.array(data[1][1])
    p = models[0].predict(X)
    for a, b in ((3, 10), (11, 20), (21, 30), (31, 45)):
        k = X["delta"].between(a, b).to_numpy()
        print(f"| {a}-{b} s | {np.abs(p[k] - y[k]).mean():.3f} | {np.abs(X['wave_pos'][k] - y[k]).mean():.3f} |")
    for side, sel in (("red", X["wave_pos"] >= 0.6), ("blue", X["wave_pos"] <= 0.4)):
        k = (sel & (X["delta"] >= 15)).to_numpy()
        print(f"\nClashing against the {side} tower, 15 s or more later: real {y[k].mean():.3f}, the model "
              f"{p[k].mean():.3f}, the one seen {X['wave_pos'][k].mean():.3f} ({k.sum():,d} samples).")
    (output / "wave_model.pkl").write_bytes(pickle.dumps(models))


# ---------------------------------------------------------------- where they go: the options by intention

def zones(L) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """(Z, A, xs, zs), (T, 10) each: each champion's zone each second (0-2 the top, mid or bot lane; 3 the
    river; 4 and 5 the blue and red jungle; 6 and 7 the bases; -1 no data), their advance in that lane from blue and their place.
    The lanes are that match's minion corridors (`line`), and mid also against the diagonal."""
    cell = L.meta["cell"]
    corridor_cells = collections.defaultdict(set)
    for cx, cz, c in L._d["corridors"]:
        corridor_cells[(int(cx), int(cz))].add(int(c))
    axis = L.meta["waves"]["axis"]
    c_river = (axis["mid"]["blue"] + axis["mid"]["red"]) / 2
    xs = np.stack([L.series("x", k) for k in range(10)], 1)
    zs = np.stack([L.series("z", k) for k in range(10)], 1)
    Z, A = np.full(xs.shape, -1, np.int8), np.full(xs.shape, np.nan)
    ok, total = ~np.isnan(xs), xs + zs
    Z[ok & (total < c_river - RIVER)], Z[ok & (total > c_river + RIVER)] = 4, 5
    Z[ok & (np.abs(total - c_river) <= RIVER)] = 3

    def advance(j: int, v: float) -> float:
        e = axis[LANES[j]]
        return (v - e["blue"]) / (e["red"] - e["blue"])

    for t, k in zip(*np.nonzero(ok)):
        ls = corridor_cells.get((int(xs[t, k] // cell), int(zs[t, k] // cell)))
        if not ls:
            continue
        if 1 in ls and abs(xs[t, k] - zs[t, k]) / 1.4142 > MID_WIDTH:
            ls = ls - {1}
        if ls:
            j = min(ls, key=lambda j: abs(advance(j, total[t, k]) - 0.5))
            Z[t, k], A[t, k] = j, advance(j, total[t, k])
    b = L.meta["bases"]
    Z[ok & (np.hypot(xs - b["100"][0], zs - b["100"][1]) < BASE)] = 6
    Z[ok & (np.hypot(xs - b["200"][0], zs - b["200"][1]) < BASE)] = 7
    return Z, A, xs, zs


def towers(L) -> dict:
    """{(team, lane, rank): (x, z, when it falls)}. The replay doesn't carry the turrets' death: it is taken as fallen when
    its health stops being recorded below 300."""
    t, tv = L.table("towers"), L.table("towers_health")
    leaves = {k: (float(x), float(z), np.inf) for k, (x, z) in TOWERS.items()}
    for k in range(len(t["id"])):
        key = (str(t["team"][k]), str(t["lane"][k]), str(t["rank"][k]))
        sel = tv["id"] == t["id"][k]
        v, tt = tv["health"][sel], tv["t"][sel]
        falls_ = float(tt.max()) if len(v) and v[np.argmax(tt)] < 300 else np.inf
        leaves[key] = (float(t["x"][k]), float(t["z"][k]), falls_)
    return leaves


LANES_OF = {0: ("TOP",), 1: ("MIDDLE",), 2: ("BOTTOM", "UTILITY")}


def _ready(L) -> dict[str, np.ndarray]:
    """(T, 10) each: flash ready, R ready, how many of Q, W and E ready, and the level derived from the experience."""
    flash = np.zeros((L.T, 10), bool)
    for k, p in enumerate(L.players):
        h = [str(x) for x in p.get("spells") or []]
        for slot, flag in ((0, "d_ready"), (1, "f_ready")):
            if len(h) > slot and h[slot] == FLASH:
                flash[:, k] = L.flag(flag, k)
    xp = np.stack([L.series("xp", k) for k in range(10)], 1)
    return {"flash": flash, "r": np.stack([L.flag("r_ready", k) for k in range(10)], 1),
            "abilities": sum(np.stack([L.flag(b, k) for k in range(10)], 1).astype(int)
                               for b in ("q_ready", "w_ready", "e_ready")),
            "level": np.where(np.isnan(xp), 1, np.searchsorted(LEVELS, np.nan_to_num(xp), side="right"))}


def _wards(L) -> dict[str, np.ndarray]:
    """The wards with their team, and their end even if the replay doesn't carry it (that ward's duration)."""
    w = L.table("wards")
    team = np.array([L.players[int(q)]["team"] if 0 <= int(q) < 10 else "" for q in w["who"]], dtype=object)
    lasts = np.array([WARD_LASTS.get(str(o), 120.0) for o in w["item"]])
    end = np.where(w["end"] > 0, w["end"], w["t"] + lasts)
    return {"t": w["t"].astype(float), "end": end.astype(float), "x": w["x"].astype(float), "z": w["z"].astype(float),
            "team": team}


def _to_path(px, pz, ax, az, bx, bz) -> np.ndarray:
    """The distance of each point (px, pz) to the segment from (ax, az) to (bx, bz)."""
    dx, dz = bx - ax, bz - az
    length = dx * dx + dz * dz
    t = np.clip(((px - ax) * dx + (pz - az) * dz) / length, 0, 1) if length > 0 else np.zeros_like(px)
    return np.hypot(px - (ax + t * dx), pz - (az + t * dz))


def options(L, decisions: pd.DataFrame, Z, A, xs, zs, is_alive, tower: dict) -> list[dict]:
    """Each decision's option by the first place they go in the following INTENT s: a lane, their base, the enemy
    jungle or the river, or the first thing they kill (one of their own camps or the enemy's, the crab, an objective)."""
    eq = [p["team"] for p in L.players]
    position = [p["position"] for p in L.players]
    jungler = {p["team"]: k for k, p in enumerate(L.players) if p["position"] == "JUNGLE"}
    lanes_of = {0: ("TOP",), 1: ("MIDDLE",), 2: ("BOTTOM", "UTILITY")}
    rc, cm = L.table("recalls"), L.table("camps")
    name = np.array([str(n).split(" ")[0] for n in cm["camp"]], dtype=object)
    out = []
    for f in decisions.itertuples():
        i = L.i(f.jungler)
        e = eq[i]
        rival_team = "200" if e == "100" else "100"
        own_side = "blue" if e == "100" else "red"
        my_base, jr = (6, 5) if e == "100" else (7, 4)
        rivals = {j: [k for k in range(10) if eq[k] == rival_team and position[k] in lanes_of[j]] for j in range(3)}
        t0, t1 = int(f.t), min(int(f.t) + INTENT, L.T - 1)
        cand = []  # (when, option, detail)
        for k in np.flatnonzero((rc["who"] == i) & (rc["t"] > f.t) & (rc["t"] <= f.t + INTENT))[:1]:
            cand.append((float(rc["t"][k]), "base", ""))
        streak, count, done_, river = collections.Counter(), collections.Counter(), set(), None
        for s in range(t0 + 1, t1 + 1):
            z = int(Z[s, i])
            count["base"] += z == my_base
            count["jr"] += z == jr
            a = A[s, i] if e == "100" else 1 - A[s, i]
            for j in range(3):
                inside = z == j and OUTSIDE[0] <= a <= OUTSIDE[1]
                if not inside:
                    streak[j], streak[f"r{j}"] = 0, 0
                    continue
                streak[j] += 1
                if any(is_alive[s, k] and np.hypot(xs[s, k] - xs[s, i], zs[s, k] - zs[s, i]) <= NEAR_LANE
                       for k in rivals[j]):
                    streak[f"r{j}"] = 1  # in this run they have had an enemy of that lane nearby
                if streak[j] >= IN_LANE[j] and streak[f"r{j}"] and j not in done_:
                    done_.add(j)
                    cand.append((s - streak[j] + 1, "line", LANES[j]))
            streak["river"] = streak["river"] + 1 if z == 3 else 0
            if streak["river"] >= IN_RIVER and river is None:
                river = s - IN_RIVER + 1
            if count["base"] == 3 and "base" not in done_:
                done_.add("base")
                cand.append((s, "base", ""))
            if count["jr"] == IN_RIVAL_JUNGLE and "jr" not in done_:
                done_.add("jr")
                cand.append((s, "invade", "stay"))
        # the camp they just killed falls at the same time as the decision: those afterwards, from 1.5 s
        for k in np.flatnonzero((cm["t"] > f.t + 1.5) & (cm["t"] <= f.t + INTENT) & (cm["killer"] == i)):
            n = name[k]
            if n in GOLD:
                cand.append((float(cm["t"][k]), "camp" if cm["side"][k] == own_side else "invade", ""))
            elif n == "Scuttle":
                cand.append((float(cm["t"][k]), "crab", ""))
            elif n in EPICS:
                cand.append((float(cm["t"][k]), "objective", ""))
        key = {"game": f.game, "jungler": f.jungler, "decision": f.decision}
        if not cand:
            out.append(key | {"option": "river" if river is not None else "camp",
                                  "option_t": np.nan if river is None else river - f.t})
            continue
        cand.sort()
        t_op, op, det = cand[0]
        # passing through the enemy jungle on the way to a lane is going to that lane, if they kill nothing before arriving
        lane_opts = [c for c in cand if c[1] == "line"]
        if op == "invade" and lane_opts and not any(c[1] != "line" and c[2] != "stay" and c[0] < lane_opts[0][0] for c in cand):
            t_op, op, det = lane_opts[0]
        if op == "line":
            op = _what_in_lane(L, i, rival_team, det, int(t_op), Z, xs, zs, is_alive, tower, eq, jungler)
        out.append(key | {"option": op, "option_t": round(float(t_op) - f.t, 1)})
    return out


def _what_in_lane(L, i, rival_team, lane, arrives, Z, xs, zs, is_alive, tower, eq, jungler) -> str:
    """Going to a lane: dive if they get into the range of a live enemy turret with a live enemy under it, counter-gank if
    the enemy jungler was already there, gank otherwise."""
    for s in range(arrives, min(arrives + DIVE_UNTIL, L.T - 1) + 1):
        if not is_alive[s, i] or np.isnan(xs[s, i]):
            continue
        for rank in ("OUTER_TURRET", "INNER_TURRET"):
            tx, tz, falls_ = tower[(rival_team, lane, rank)]
            if falls_ <= s or np.hypot(xs[s, i] - tx, zs[s, i] - tz) > DIVE:
                continue
            if any(eq[k] == rival_team and is_alive[s, k] and np.hypot(xs[s, k] - tx, zs[s, k] - tz) <= UNDER_TOWER
                   for k in range(10)):
                return f"dive {lane}"
    r = jungler.get(rival_team)
    if r is not None and not np.isnan(xs[arrives, i]):
        j = LANES.index(lane)
        for s in range(max(arrives - BEFORE_COUNTER, 0), arrives + 1):
            if is_alive[s, r] and np.hypot(xs[s, r] - xs[arrives, i], zs[s, r] - zs[arrives, i]) <= TOGETHER and Z[s, r] in (j, 3):
                return f"contragank {lane}"
    return f"gank {lane}"


# ---------------------------------------------------------------- what happens afterwards and the state of the lanes

def of_game(L, decisions: pd.DataFrame, wave_model) -> list[dict]:
    """Per decision: the option, what happens in the following WINDOW s and how the lanes were."""
    m, c, cm, gold = L.table("deaths"), L.table("casts"), L.table("camps"), L.table("gold")
    team = [p["team"] for p in L.players]
    position = [p["position"] for p in L.players]
    junglers = {p["team"]: k for k, p in enumerate(L.players) if p["position"] == "JUNGLE"}
    Z, A, xs, zs = zones(L)
    is_alive = np.stack([L.flag("alive", k) for k in range(10)], 1)
    ops = {(o["decision"], o["jungler"]): o for o in options(L, decisions, Z, A, xs, zs, is_alive, towers(L))}
    series = {n: np.stack([L.series(n, k) for k in range(10)], 1)
             for n in ("cs", "health", "health_max", "mana", "mana_max", "gold", "total_gold", "move_speed")}
    view = wave_seen(L)

    def spot(k: int, t: float) -> tuple[float, float]:
        s = min(max(int(t), 0), L.T - 1)
        return xs[s, k], zs[s, k]

    def fraction(field: str, k: int, s: int) -> float:
        v, peak = series[field][s, k], series[f"{field}_max"][s, k]
        return float(v / peak) if not np.isnan(v) and not np.isnan(peak) and peak > 0 else np.nan

    flash = c["spell"] == "SummonerFlash"
    name = np.array([str(n).split(" ")[0] for n in cm["camp"]], dtype=object)
    from_tower = gold["source"] == "tower"
    ready, wards = _ready(L), _wards(L)

    def _of_the_lane(j, lane, s, i, eq, front, xs, zs, is_alive, ready, wards) -> dict:
        """A lane's features that weigh in a gank: flashes and R of each side, basic abilities ready, wards, the
        level difference (from experience: the replay's level arrives late) and who they are."""
        rivals = [k for k in range(10) if team[k] != eq and position[k] in LANES_OF[j]]
        allies = [k for k in range(10) if team[k] == eq and position[k] in LANES_OF[j]]
        vr, goes = [k for k in rivals if is_alive[s, k]], [k for k in allies if is_alive[s, k]]
        fx, fz = front
        jx, jz = xs[s, i], zs[s, i]
        alive_w = (wards["t"] <= s) & (wards["end"] > s)
        near = alive_w & (np.hypot(wards["x"] - fx, wards["z"] - fz) <= WARD_NEAR)
        own_w = wards["team"] == eq
        leaves = {f"{lane}_flash_ally": int(sum(ready["flash"][s, k] for k in goes)),
                f"{lane}_r_rival": int(sum(ready["r"][s, k] for k in vr)),
                f"{lane}_abilities_rival": float(np.mean([ready["abilities"][s, k] for k in vr])) if vr else np.nan,
                f"{lane}_abilities_ally": float(np.mean([ready["abilities"][s, k] for k in goes])) if goes else np.nan,
                f"{lane}_wards_own": int((near & own_w).sum()),
                f"{lane}_levels_diff": float(np.mean([ready["level"][s, k] for k in allies])
                                               - np.mean([ready["level"][s, k] for k in rivals])) if allies and rivals else np.nan,
                f"{lane}_wards_rival": int((near & ~own_w).sum()),
                f"{lane}_wards_rival_path": int((alive_w & ~own_w & (_to_path(wards["x"], wards["z"], jx, jz, fx, fz)
                                                                          <= WARD_PATH)).sum()) if not np.isnan(jx) else 0}
        for name_c, whom in (("champion_rival", rivals), ("champion_ally", allies)):
            command = sorted(whom, key=lambda k: position[k])  # BOTTOM before UTILITY
            leaves[f"{lane}_{name_c}"] = L.players[command[0]]["champion"] if command else ""
            leaves[f"{lane}_{name_c}2"] = L.players[command[1]]["champion"] if len(command) > 1 else ""
        return leaves

    out, for_wave = [], []
    for f in decisions.itertuples():
        i = L.i(f.jungler)
        eq = team[i]
        rival = junglers.get("200" if eq == "100" else "100", -1)
        own_side, other_side = ("blue", "red") if eq == "100" else ("red", "blue")
        t0, t1 = float(f.t), float(f.t) + WINDOW
        s0, s1 = min(int(t0), L.T - 1), min(int(t1), L.T - 1)
        n = dict.fromkeys(OUTCOMES, 0.0)
        for k in np.flatnonzero((m["t"] > t0) & (m["t"] <= t1)):
            v = int(m["who"][k])
            if team[v] != eq:
                takes_part_ = int(m["killer"][k]) == i or (int(m["hitters"][k]) >> i) & 1
                n["kills_with_him" if takes_part_ else "kills_without_him"] += 1
            elif v == i:
                n["he_dies"] += 1
            else:
                jx, jz = spot(i, m["t"][k])
                near = np.hypot(jx - m["x"][k], jz - m["z"][k]) <= NEAR
                n["allies_fall_near" if near else "allies_fall_far"] += 1
        for k in np.flatnonzero(flash & (c["t"] > t0) & (c["t"] <= t1)):
            q = int(c["who"][k])
            if q == i:
                n["flash_own"] += 1
            elif team[q] != eq:
                jx, jz = spot(i, c["t"][k])
                qx, qz = spot(q, c["t"][k])
                if np.hypot(jx - qx, jz - qz) <= FLASH_NEAR:
                    n["flash_rival"] += 1
        for k in np.flatnonzero((cm["t"] > t0) & (cm["t"] <= t1) & (cm["killer"] >= 0)):
            a, who_team, side = int(cm["killer"][k]), team[int(cm["killer"][k])], cm["side"][k]
            if name[k] in GOLD:
                if a == i:
                    n["camps_stolen" if side == other_side else "camps_own"] += 1
                elif who_team != eq and side == own_side:
                    n["camps_lost"] += 1
                elif a == rival and side == other_side:
                    n["farms_the_rival"] += 1
            elif name[k] == "Scuttle":
                n["crabs_own" if who_team == eq else "crabs_rival"] += 1
            elif name[k] in EPICS:
                n["objectives_own" if who_team == eq else "objectives_rival"] += 1
        # the lanes' CS (everyone but the junglers), the turret gold, and how the jungler ends up
        cs = np.nan_to_num(series["cs"][s1] - series["cs"][s0])
        n["cs_lane"] = sum((1 if team[k] == eq else -1) * cs[k] for k in range(10) if position[k] != "JUNGLE") / 10
        for k in np.flatnonzero(from_tower & (gold["t"] > t0) & (gold["t"] <= t1)):
            n["tower_own" if team[int(gold["who"][k])] == eq else "rival_tower"] += float(gold["amount"][k]) / 100
        for name_, field in (("health_change", "health"), ("mana_change", "mana")):
            a, b = fraction(field, i, s0), fraction(field, i, s1)
            n[name_] = 0.0 if np.isnan(a) or np.isnan(b) or not is_alive[s1, i] else b - a
        spent = (series["total_gold"][s1, i] - series["total_gold"][s0, i]) - (series["gold"][s1, i] - series["gold"][s0, i])
        n["gold_spent"] = max(0.0, float(np.nan_to_num(spent))) / 100
        # the lanes at the time of deciding: the wave that was seen, how many minions each side has and how long it takes to arrive
        state = {}
        vel = series["move_speed"][s0, i] if series["move_speed"][s0, i] > 0 else 350.0
        for j, lane in enumerate(LANES):
            fx, fz = view[s0, j, 1], view[s0, j, 2]
            if np.isnan(fx):
                fx, fz = CENTER[lane]
            arrives = 20.0 if np.isnan(xs[s0, i]) else \
                float(np.clip(np.hypot(fx - xs[s0, i], fz - zs[s0, i]) / vel * DETOUR, *ARRIVES))
            a = view[s0, j, 0]
            diff = float(L.lane_waves[s0, j, 3]) - float(L.lane_waves[s0, j, 4])
            state[f"{lane}_wave_seen"] = (a if eq == "100" else 1 - a) if not np.isnan(a) else np.nan
            state[f"{lane}_wave_arrives"] = np.nan
            state[f"{lane}_arrives_s"] = round(arrives, 1)
            state[f"{lane}_minions_diff"] = diff if eq == "100" else -diff
            if not np.isnan(a):
                for_wave.append((len(out), lane, eq, _wave_features(L, view, s0, j) + [arrives]))
            state |= _of_the_lane(j, lane, s0, i, eq, (fx, fz), xs, zs, is_alive, ready, wards)
        state |= {"flash_ready_own": int(ready["flash"][s0, i]), "r_own": int(ready["r"][s0, i]),
                   "abilities_own": int(ready["abilities"][s0, i]), "level_xp": int(ready["level"][s0, i])}
        o = ops.get((f.decision, f.jungler), {"option": "camp", "option_t": np.nan})
        # if they go to a lane: does the gank end in a kill of an enemy of that lane, by them, in the GANK_KILL s of arriving?
        lane_kill = np.nan
        kind, lane = o["option"].split(" ")[0], o["option"].split(" ")[-1]
        if kind in KINDS:
            arrives_t = t0 + float(o["option_t"])
            own_rivals = {k for k in range(10) if team[k] != eq and position[k] in LANES_OF[LANES.index(lane)]}
            lane_kill = sum(1 for k in np.flatnonzero((m["t"] > arrives_t) & (m["t"] <= arrives_t + GANK_KILL))
                             if int(m["who"][k]) in own_rivals
                             and (int(m["killer"][k]) == i or (int(m["hitters"][k]) >> i) & 1))
        out.append({"game": f.game, "jungler": f.jungler, "decision": f.decision, "option": o["option"],
                      "option_t": o["option_t"], "lane_kill": lane_kill} | n | state)
    if for_wave:
        p = wave_model.predict(pd.DataFrame([r for *_, r in for_wave], columns=WAVE_COLS))
        for (row, lane, eq, _r), v in zip(for_wave, p):
            out[row][f"{lane}_wave_arrives"] = round(float(v if eq == "100" else 1 - v), 3)
    return out


def cmd_extract(output: Path, timelines: Path, decisions: Path) -> None:
    _import_deps()
    import timeline

    models = pickle.loads((output / "wave_model.pkl").read_bytes())
    d = pd.read_pickle(decisions) if decisions.suffix == ".pkl" else pd.read_csv(decisions, low_memory=False)
    d = d[d["decision"] >= 1][["game", "jungler", "decision", "t"]]
    rows = []
    for pid, g in d.groupby("game"):
        route = timelines / f"{pid}.npz"
        if route.exists():
            rows += of_game(timeline.load(route), g, models[1 - _half(pid)])
    out = pd.DataFrame(rows)
    out.to_csv(output / "outcomes.csv.gz", index=False)
    print(f"{out['game'].nunique():,d} games · {len(out):,d} decisions\n")
    print(out["option"].value_counts(normalize=True).round(3).to_string())
    print(out[list(OUTCOMES)].mean().round(3).to_string())


# ---------------------------------------------------------------- what each outcome is worth and what each option brings

def _join(output: Path, decisions: Path) -> pd.DataFrame:
    _import_deps()
    import routes_model as R

    d = pd.read_pickle(decisions)
    if "centred_value_90" not in d.columns:
        d = R.centre(d)
    n = pd.read_csv(output / "outcomes.csv.gz")
    return d.merge(n, on=["game", "jungler", "decision"], how="inner")


def _moment(decision) -> np.ndarray:
    """The stretch of the match for each decision (index into MOMENTS)."""
    d = np.asarray(decision, float)
    return np.select([d <= MOMENTS[0][1], d <= MOMENTS[1][1]], [0, 1], 2)


def values(df: pd.DataFrame, column: str, times: int = 200) -> dict:
    """What each outcome is worth (WP points), by least squares over all the decisions, and what each
    option is worth beyond its outcomes (compared with continuing to clear), separately in each stretch of the match, with the
    90% interval resampling matches.

    The second captures what the outcomes don't see: where the jungler ends up, how the lanes end up... Without it, a dive
    to bot was worth a point more by its outcomes than what was measured directly. It goes by stretches because a gank at the 3rd
    camp doesn't resemble one at the 10th."""
    ok = df[column].notna().to_numpy()
    others_ = [o for o in OPTIONS if o != "camp"]
    op = df.loc[ok, "option"].to_numpy()
    mo = _moment(df.loc[ok, "decision"])
    pairs = [(o, b) for o in others_ for b in range(len(MOMENTS))]
    X = np.column_stack([np.ones(ok.sum()), df.loc[ok, list(OUTCOMES)].to_numpy(float)]
                        + [(mo == b).astype(float) for b in range(1, len(MOMENTS))]
                        + [((op == o) & (mo == b)).astype(float) for o, b in pairs])
    y = df.loc[ok, column].to_numpy(float)
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    games = df.loc[ok, "game"].to_numpy()
    unique_, inv = np.unique(games, return_inverse=True)
    groups = [np.flatnonzero(inv == k) for k in range(len(unique_))]
    rng = np.random.default_rng(0)
    samples = []
    for _ in range(times):
        idx = np.concatenate([groups[k] for k in rng.integers(0, len(groups), len(groups))])
        samples.append(np.linalg.lstsq(X[idx], y[idx], rcond=None)[0])
    samples = np.array(samples)
    lo, hi = np.percentile(samples, 5, axis=0), np.percentile(samples, 95, axis=0)
    n = len(OUTCOMES) + 1
    since = n + len(MOMENTS) - 1
    extra, extra_lo, extra_hi = (np.zeros((len(OPTIONS), len(MOMENTS))) for _ in range(3))
    for k, (o, b) in enumerate(pairs):
        i = OPTIONS.index(o)
        extra[i, b], extra_lo[i, b], extra_hi[i, b] = beta[since + k], lo[since + k], hi[since + k]
    return {"beta": beta[1:n], "it": lo[1:n], "hi": hi[1:n], "extra": extra, "extra_lo": extra_lo, "extra_hi": extra_hi}


def _model(outcome: str, leaf: int = 200):
    from sklearn.ensemble import HistGradientBoostingRegressor

    if outcome == "lane_kill":  # very mild: equally calibrated and more stable between halves (0.84 against 0.75)
        return HistGradientBoostingRegressor(loss="poisson", max_iter=150, learning_rate=0.03, max_leaf_nodes=8,
                                             min_samples_leaf=1000, l2_regularization=5.0, random_state=0)
    return HistGradientBoostingRegressor(loss="squared_error" if outcome in CONTINUOUS else "poisson", max_iter=200,
                                         learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=leaf,
                                         l2_regularization=1.0, random_state=0)


def columns_of(m_routes: dict) -> list[str]:
    """The state features: those of `routes_model` without the earlier wave (which looked 20 s ahead), and those of
    each lane (`OF_LANE`) and of the jungler themselves (`OWN`)."""
    return [c for c in m_routes["columns"] if not c.endswith("_wave")] + STATE


# The features of the lane they go to, repeated separately for each option that goes to a lane (and gold and health for going
# back to base). With the option as one more feature, a tree model has to split first by the option and then by the
# state of that lane, and with 2% of ganks to each lane it didn't get there.
OF_THE_LANE = ("wave_arrives", "wave_seen", "arrives_s", "minions_diff", "health_rival", "health_ally", "rivals_alive",
               "allies_alive", "no_flash_rival", "ult_ally", "gold_diff", "flash_ally", "r_rival",
               "abilities_rival", "abilities_ally", "wards_own", "levels_diff")
DESTINATION = (["destination_kind"] + [f"destination_{x}" for x in OF_THE_LANE] + [f"destination_{x}" for x in CHAMPIONS]
           + ["base_gold", "base_health", "base_mana"])
DESTINATION_OMNI = [f"destination_{x}" for x in OMNISCIENT_LANE]
KINDS = {"gank": 1.0, "dive": 2.0, "counter_gank": 3.0}
LANE_LEAF = 80  # leaves of the trees of the go-to-a-lane model: it has about 30,000 decisions, not 245,000


def _X(df: pd.DataFrame, categories: dict, columns: list[str], option: str | None = None, omniscient: bool = False):
    """The state features (what they knew), those of the lane that option goes to and the option: the one chosen or, with
    `option`, the one to be valued. With `omniscient`, also the enemy wards (which the jungler doesn't see)."""
    _import_deps()
    import routes_model as R

    X, _ = R.features(df, categories)
    X = X.reindex(columns=columns)
    r = (df["option"] if option is None else pd.Series(option, index=df.index)).astype(str)
    kind, lane = r.str.split(" ").str[0], r.str.split(" ").str[-1]
    to_lane = kind.isin(KINDS).to_numpy()
    X["destination_kind"] = kind.map(KINDS).fillna(0.0).to_numpy()
    codes = {name: k for k, name in enumerate(categories.get("champion", []))}
    for x in OF_THE_LANE + (OMNISCIENT_LANE if omniscient else ()) + CHAMPIONS:
        v = np.full(len(X), np.nan)
        for c in LANES:
            at = to_lane & (lane == c).to_numpy()
            if not at.any():
                continue
            if x in CHAMPIONS:
                source = df[f"{c}_{x}"].map(codes).to_numpy(float)
            elif f"{c}_{x}" in X.columns:
                source = X[f"{c}_{x}"].to_numpy(float)
            else:
                source = pd.to_numeric(df[f"{c}_{x}"], errors="coerce").to_numpy(float)
            v[at] = source[at]
        X[f"destination_{x}"] = v
    base = (r == "base").to_numpy()
    for is_new, old in (("base_gold", "gold_unspent"), ("base_health", "health"), ("base_mana", "mana")):
        X[is_new] = np.where(base, X[old].to_numpy(float), np.nan)
    X["option_i"] = r.map({x: k for k, x in enumerate(OPTIONS)}).astype(float)
    return X


def _mask(X: pd.DataFrame) -> list[bool]:
    _import_deps()
    import routes_model as R

    return [c in R.CATEGORICAL or c == "option_i" or c.startswith("destination_champion") for c in X.columns]


def _state(X: pd.DataFrame) -> pd.DataFrame:
    """The state only: without the option or what depends on it (for the policy, which has to guess the option)."""
    return X.drop(columns=[c for c in ["option_i", *DESTINATION, *DESTINATION_OMNI] if c in X.columns])


def _to_lane(X: pd.DataFrame) -> np.ndarray:
    return X["destination_kind"].to_numpy() > 0


def _useful(X: pd.DataFrame, sel: np.ndarray) -> list[str]:
    """The columns that change in those rows (those that don't, like the lane's features in options that don't go to a
    lane, break the trees' binning)."""
    return [c for c in X.columns if X.loc[sel, c].nunique(dropna=True) >= 2]


def _fit(df, X, mask, outcomes=OUTCOMES + ("lane_kill",)) -> dict:
    """The models of each outcome, separately for the options that go to a lane (with that lane's features as the
    main thing) and for the rest. `lane_kill`, only for those that go to a lane."""
    line = _to_lane(X)
    models = {"line": {}, "rest": {}}
    for family, sel, leaf in (("line", line, LANE_LEAF), ("rest", ~line, 200)):
        cols = _useful(X, sel)
        cat = [mask[list(X.columns).index(c)] for c in cols]
        models[family]["_columns"] = cols
        for o in outcomes:
            if o == "lane_kill" and family == "rest":
                continue
            y = df[o].to_numpy(float)[sel]
            if o == "lane_kill":  # yes or no: with counts and Poisson, the probability came out 8 points low
                y = (y > 0).astype(float)
            models[family][o] = _model(o, leaf).set_params(categorical_features=cat).fit(X.loc[sel, cols], y)
    return models


def ev(models: dict, v: dict, X) -> tuple[np.ndarray, np.ndarray]:
    """(what it is worth, what is expected of each outcome) for each row of X: the sum of each expected outcome times what
    it is worth, plus what the option is worth by itself in that stretch."""
    line = _to_lane(X)
    expected_values = np.full((len(X), len(OUTCOMES)), np.nan)
    for family, sel in (("line", line), ("rest", ~line)):
        if sel.any():
            Xs = X.loc[sel, models[family]["_columns"]]
            expected_values[sel] = np.column_stack([models[family][o].predict(Xs) for o in OUTCOMES])
    extra = v["extra"][X["option_i"].to_numpy(int), _moment(X["decision"])]
    return expected_values @ v["beta"] + extra, expected_values


def p_kill(models: dict, X) -> np.ndarray:
    """The probability that going to that lane ends in a kill of an enemy of that lane in the GANK_KILL s of arriving
    (nan if the option doesn't go to a lane)."""
    line = _to_lane(X)
    p = np.full(len(X), np.nan)
    if line.any():
        p[line] = np.clip(models["line"]["lane_kill"].predict(X.loc[line, models["line"]["_columns"]]), 0, 1)
    return p


def _high_policy(policy, X) -> np.ndarray:
    """(rows, OPTIONS): what share of Master-and-above junglers choose each option in that state."""
    import routes_model as R

    Xp = _state(X)
    pol = np.zeros((len(X), len(OPTIONS)))
    for league in R.HIGH:
        Xl = Xp.copy()
        Xl["league_i"] = league
        pol[:, policy.classes_.astype(int)] += policy.predict_proba(Xl) / len(R.HIGH)
    return pol


def _measured_diff(df, sel, a: str, b: str, col: str) -> tuple[float, float, int]:
    """What was measured directly: option a minus b in those decisions, with its error, and how many chose a."""
    x = df.loc[sel & (df["option"] == a).to_numpy(), col].dropna()
    y = df.loc[sel & (df["option"] == b).to_numpy(), col].dropna()
    if len(x) < 30 or len(y) < 30:
        return np.nan, np.nan, len(x)
    return x.mean() - y.mean(), float(np.sqrt(x.var() / len(x) + y.var() / len(y))), len(x)


def _f(x, fmt: str = "{:+.2f}") -> str:
    return "" if x is None or np.isnan(x) else fmt.format(x).replace("-", "−")


def _p(x) -> str:
    return "" if x is None or np.isnan(x) else f"{x:.0%}"


ALTERNATIVES = ("camp", "base", "invade", "gank top", "gank mid", "gank bot", "dive top", "dive mid", "dive bot",
                "contragank top", "contragank mid", "contragank bot")
WAVE_STATES = (("rival ahead on arrival", lambda a: a <= 0.45), ("in the middle", lambda a: (a > 0.45) & (a < 0.56)),
               ("clashing at their tower on arrival", lambda a: a >= 0.56))
# what makes a gank harder or easier: (name, lane column, hard value, easy value); "alive" is
# the number of living enemies in that lane (all with flash, all with the R...)
FACTORS = (("the rival's flash", "no_flash_rival", 0, "alive"), ("the rival's R", "r_rival", "alive", 0),
            ("rival's basic abilities", "abilities_rival", 3, 0), ("own wards near", "wards_own", 0, 2),
            ("wave on arrival", "wave_arrives", 0.62, 0.40), ("rival's health", "health_rival", 1.0, 0.3),
            ("levels (own − rival's)", "levels_diff", -1, 1))
GANK_GROUPS = (("the rival with flash", lambda d: d["destination_no_flash_rival"] == 0),
               ("the rival without flash", lambda d: d["destination_no_flash_rival"] >= 1),
               ("with the rival's R ready", lambda d: d["destination_r_rival"] >= 1),
               ("without the rival's R", lambda d: d["destination_r_rival"] == 0),
               ("rival ward on the path", lambda d: d["destination_wards_rival_path"] >= 1),
               ("no rival ward on the path", lambda d: d["destination_wards_rival_path"] == 0),
               ("with own ward near", lambda d: d["destination_wards_own"] >= 1),
               ("without own ward near", lambda d: d["destination_wards_own"] == 0),
               ("the wave clashing at their tower on arrival", lambda d: d["destination_wave_arrives"] >= 0.56),
               ("the rival ahead on arrival", lambda d: d["destination_wave_arrives"] <= 0.45),
               ("the rival at half health or less", lambda d: d["destination_health_rival"] <= 0.5),
               ("with one level less", lambda d: d["destination_levels_diff"] <= -1),
               ("with one level more", lambda d: d["destination_levels_diff"] >= 1))


def cmd_analyse(output: Path, decisions: Path, routes_model_file: Path) -> None:
    from sklearn.model_selection import GroupKFold

    _import_deps()
    import routes_model as R

    df = _join(output, decisions).reset_index(drop=True)
    m = pickle.loads(routes_model_file.read_bytes())
    df = df[df["option"].isin(OPTIONS)].reset_index(drop=True)
    champions = sorted({str(x) for c in LANES for k in CHAMPIONS for x in df[f"{c}_{k}"].fillna("") if str(x)})
    categories, columns = dict(m["categories"]) | {"champion": champions[:250]}, columns_of(m)
    print(f"# The outcomes tree (3rd version)\n\n{len(df):,d} decisions (from the 1st camp to 14:00) from "
          f"{df['game'].nunique():,d} games. Options by intent; outcomes in the next {WINDOW:.0f} s. "
          "A separate model for going to a lane, with what is in that lane (wave, flashes, R, abilities, own wards, "
          "levels, champions) as the main thing.\n")
    print("## The options\n\n| option | decisions | from the 3rd to the 6th camp | takes to start (median) | "
          "the gank ends in a kill (30 s) |\n|---|---|---|---|---|")
    mid = df["decision"].between(3, 6)
    for o in OPTIONS:
        s = df["option"] == o
        kl = df.loc[s, "lane_kill"]
        print(f"| {o} | {s.mean():.1%} | {s[mid].mean():.1%} | {_f(df.loc[s, 'option_t'].median(), '{:.0f} s')} | "
              f"{_p((kl > 0).mean()) if kl.notna().any() else ''} |")

    # 1. what each outcome is worth, and each option by itself
    betas = {h: values(df, col) for h, col in HORIZONS.items()}
    print("\n## What each outcome is worth\n\nNeutral WP points for their team (a kill is about 4.7), over "
          "what is expected in that state. In brackets, the 90% interval.\n")
    print("| outcome | mean per decision | at 90 s | at 5 min |\n|---|---|---|---|")
    for k, o in enumerate(OUTCOMES):
        cells = [NAMES[o], f"{df[o].mean():.3f}"]
        for h in HORIZONS:
            v = betas[h]
            cells.append(f"{v['beta'][k]:+.2f} [{v['it'][k]:+.2f}, {v['hi'][k]:+.2f}]")
        print("| " + " | ".join(cells) + " |")
    print("\n## What each option is worth by itself\n\nAgainst continuing to clear, in the same regression "
          "and by stretches: what comes out extra or missing for whoever chooses that option and is not "
          "explained by its outcomes. At 90 s; in brackets, the 90% interval.\n")
    names_m = [f"camps {a}-{b}" if b < 999 else f"camp {a} onwards" for a, b in MOMENTS]
    print("| option | " + " | ".join(names_m) + " |\n" + "|---" * (len(MOMENTS) + 1) + "|")
    for k, o in enumerate(OPTIONS):
        if o == "camp":
            continue
        v = betas[90]
        print(f"| {o} | " + " | ".join(f"{v['extra'][k, b]:+.2f} [{v['extra_lo'][k, b]:+.2f}, {v['extra_hi'][k, b]:+.2f}]"
                                       for b in range(len(MOMENTS))) + " |")

    # 2. what each option brings in each state, out of fold by match
    X = _X(df, categories, columns)
    mask = _mask(X)
    line = _to_lane(X)
    g = df["game"].to_numpy()
    pred = {h: np.full(len(df), np.nan) for h in HORIZONS}
    against = {a: {h: np.full(len(df), np.nan) for h in HORIZONS} for a in ALTERNATIVES}
    exp_real = np.full((len(df), len(OUTCOMES)), np.nan)
    exp_alt = {a: np.full((len(df), len(OUTCOMES)), np.nan) for a in ALTERNATIVES}
    kill_real, kill_alt = np.full(len(df), np.nan), {a: np.full(len(df), np.nan) for a in ALTERNATIVES}
    # the variant with what happened: the same for going to a lane, knowing where the enemy wards were
    Xo = _X(df, categories, columns, omniscient=True)
    mask_o = _mask(Xo)
    kill_omni, dies_omni = np.full(len(df), np.nan), np.full(len(df), np.nan)
    for tr, te in GroupKFold(FOLDS).split(X, groups=g):
        mods = _fit(df.iloc[tr], X.iloc[tr], mask)
        for h in HORIZONS:
            pred[h][te], exp_real[te] = ev(mods, betas[h], X.iloc[te])
        kill_real[te] = p_kill(mods, X.iloc[te])
        for a in ALTERNATIVES:
            Xa = _X(df.iloc[te], categories, columns, option=a)
            for h in HORIZONS:
                against[a][h][te], exp_alt[a][te] = ev(mods, betas[h], Xa)
            kill_alt[a][te] = p_kill(mods, Xa)
        tr_l, te_l = tr[line[tr]], te[line[te]]
        cols_o = _useful(Xo, np.isin(np.arange(len(Xo)), tr_l))
        cat_o = [mask_o[list(Xo.columns).index(c)] for c in cols_o]
        for o, dest in (("lane_kill", kill_omni), ("he_dies", dies_omni)):
            y = df[o].to_numpy(float)[tr_l]
            mo = _model(o, LANE_LEAF).set_params(categorical_features=cat_o).fit(
                Xo.iloc[tr_l][cols_o], (y > 0).astype(float) if o == "lane_kill" else y)
            dest[te_l] = mo.predict(Xo.iloc[te_l][cols_o])
        print(f"(fold done: {len(te):,d} decisions)", file=sys.stderr, flush=True)
    (output / "outcomes_oof.pkl").write_bytes(pickle.dumps({"exp_real": exp_real, "exp_alt": exp_alt, "pred": pred,
                                                              "against": against, "kill_real": kill_real, "kill_alt": kill_alt,
                                                              "keys": df[["game", "jungler", "decision"]]}))

    print("\n## Does it tell when a gank has more or fewer chances?\n\nThe decisions to go to a lane (gank, "
          "dive or counter-gank), with games the model has not seen, grouped by what there was in that lane "
          "when deciding: how many end in a kill of a rival of that lane within 30 s of arriving and how many "
          "in which he dies (in 90 s), for real and what the model expected. If the model distinguishes, what "
          "is expected moves with what is real. The rival wards are not seen by it (the jungler does not know "
          "where they are): the last column is the variant that does see them.\n")
    print("| in that lane | decisions | real kill | the model | really dies | the model | kill, knowing the "
          "rival wards |\n|---|---|---|---|---|---|---|")
    D = Xo[line].reset_index(drop=True)
    sub = df[line].reset_index(drop=True)
    kr, mr = kill_real[line], exp_real[line][:, OUTCOMES.index("he_dies")]
    ko = np.clip(kill_omni[line], 0, 1)
    rows_g = [("all", np.ones(len(sub), bool))] + [(n, rule(D).to_numpy()) for n, rule in GANK_GROUPS]
    for name, sel in rows_g:
        if sel.sum() < 100:
            continue
        print(f"| {name} | {sel.sum():,d} | {_p((sub.loc[sel, 'lane_kill'] > 0).mean())} | {_p(np.nanmean(kr[sel]))} | "
              f"{_p((sub.loc[sel, 'he_dies'] > 0).mean())} | {_p(np.nanmean(1 - np.exp(-mr[sel])))} | "
              f"{_p(np.nanmean(ko[sel]))} |")
    q = pd.qcut(kr, 5, labels=False, duplicates="drop")
    print("\nAnd from those the model sees as hardest to the easiest (five groups by what it expects): "
          + " · ".join(f"expects {_p(np.nanmean(kr[q == b]))} → happens {_p((sub.loc[q == b, 'lane_kill'] > 0).mean())}"
                       for b in range(int(np.nanmax(q)) + 1)) + ".\n")

    print("\n## Does it hold up state by state?\n\n### Does it get right what it expects from each "
          "outcome?\n\nAll the decisions in five groups by what the model expects from that outcome with the "
          "option chosen, and what really happened in each group.\n")
    print("| outcome | " + " | ".join(f"group {k + 1}: expects → happens" for k in range(5)) + " |\n|---|---|---|---|---|---|")
    for o in ("kills_with_him", "he_dies", "flash_rival", "camps_stolen", "cs_lane", "rival_tower", "gold_spent"):
        k = OUTCOMES.index(o)
        p, y = exp_real[:, k], df[o].to_numpy(float)
        qq = pd.qcut(p, 5, labels=False, duplicates="drop")
        print(f"| {NAMES[o]} | " + " | ".join(f"{_f(p[qq == b].mean(), '{:.2f}')} → {_f(y[qq == b].mean(), '{:.2f}')}"
                                               for b in range(int(qq.max()) + 1)) + " |")

    print("\n### Going to a lane or continuing to clear, outcome by outcome\n\nFrom the 3rd to the 6th camp. "
          "Each decision is placed by the difference the model expects between that option and continuing to "
          "clear in that state; in each group, the real difference between whoever chose it and whoever kept "
          "clearing (± its error).\n")
    print("| option | outcome | low group: expects → happens | medium | high |\n|---|---|---|---|---|")
    mid_ = mid.to_numpy()
    for op in ("gank top", "gank mid", "gank bot", "dive top", "dive mid", "dive bot"):
        for o in ("kills_with_him", "he_dies", "allies_fall_near"):
            k = OUTCOMES.index(o)
            diff = exp_alt[op][:, k] - exp_alt["camp"][:, k]
            sel = mid_ & ~np.isnan(diff)
            cuts = np.quantile(diff[sel], [0, 1 / 3, 2 / 3, 1])
            cells = [op, NAMES[o]]
            for b in range(3):
                at = sel & (diff >= cuts[b]) & (diff <= cuts[b + 1])
                gk = df.loc[at & (df["option"] == op).to_numpy(), o].to_numpy(float)
                cp = df.loc[at & (df["option"] == "camp").to_numpy(), o].to_numpy(float)
                if len(gk) < 40 or len(cp) < 40:
                    cells.append("")
                    continue
                err = np.sqrt(gk.var() / len(gk) + cp.var() / len(cp))
                cells.append(f"{_f(diff[at].mean())} → {_f(gk.mean() - cp.mean())} (±{_f(err, '{:.2f}')})")
            print("| " + " | ".join(cells) + " |")

    # 3. does it reproduce what was measured directly?
    print("\n## Does it reproduce what was measured directly?\n\nWhat the tree expects from each option "
          "against continuing to clear, on average in those decisions (whether or not they chose it), against "
          "what was measured: what came out for whoever chose it minus what came out for whoever kept "
          "clearing in that same state (± its error). WP points.\n")
    print("### Going to a lane, according to where the wave will be on arrival (from the 3rd to the 6th camp)\n")
    print("| lane | state | option | choose it | tree at 90 s | measured at 90 s | tree at 5 min | measured "
          "at 5 min |\n|---|---|---|---|---|---|---|---|")
    for lane in LANES:
        wave = df[f"{lane}_wave_arrives"].to_numpy(float)
        for name, rule in WAVE_STATES:
            sel = mid_ & ~np.isnan(wave) & rule(np.nan_to_num(wave, nan=0.5))
            for op in (f"gank {lane}", f"dive {lane}"):
                n_op = int((sel & (df["option"] == op).to_numpy()).sum())
                cells = [lane, name, op, f"{n_op / max(sel.sum(), 1):.1%} ({n_op:,d})"]
                for h, col in HORIZONS.items():
                    tree = np.nanmean(against[op][h][sel] - against["camp"][h][sel])
                    dm, err, _ = _measured_diff(df, sel, op, "camp", col)
                    cells += [_f(tree), f"{_f(dm)} (±{_f(err, '{:.2f}')})" if not np.isnan(dm) else ""]
                print("| " + " | ".join(cells) + " |")

    print("\n### Ganking, according to the rival's flash (from the 3rd to the 6th camp)\n")
    print("| lane | the rival | option | choose it | tree at 90 s | measured at 90 s |\n|---|---|---|---|---|---|")
    for lane in LANES:
        rival_no_flash = df[f"{lane}_no_flash_rival"].fillna(0).to_numpy()
        for name, sel0 in (("with flash", rival_no_flash == 0), ("without flash", rival_no_flash >= 1)):
            sel = mid_ & sel0
            op = f"gank {lane}"
            n_op = int((sel & (df["option"] == op).to_numpy()).sum())
            tree = np.nanmean(against[op][90][sel] - against["camp"][90][sel])
            dm, err, _ = _measured_diff(df, sel, op, "camp", HORIZONS[90])
            print(f"| {lane} | {name} | {op} | {n_op / max(sel.sum(), 1):.1%} ({n_op:,d}) | {_f(tree)} | "
                  + (f"{_f(dm)} (±{_f(err, '{:.2f}')})" if not np.isnan(dm) else "") + " |")

    print("\n### Going back to base, according to health and gold (from the 7th camp onwards)\n")
    print("| state | go back | tree at 90 s | measured at 90 s | tree at 5 min | measured at 5 min |\n|---|---|---|---|---|---|")
    eb = R._base_states(df)
    late_ = (df["decision"] >= 7).to_numpy()
    for name in R.BASE_STATES:
        sel = late_ & (eb == name)
        n_op = int((sel & (df["option"] == "base").to_numpy()).sum())
        cells = [name, f"{n_op / max(sel.sum(), 1):.1%} ({n_op:,d})"]
        for h, col in HORIZONS.items():
            tree = np.nanmean(against["base"][h][sel] - against["camp"][h][sel])
            dm, err, _ = _measured_diff(df, sel, "base", "camp", col)
            cells += [_f(tree), f"{_f(dm)} (±{_f(err, '{:.2f}')})" if not np.isnan(dm) else ""]
        print("| " + " | ".join(cells) + " |")

    # the policy (what they choose in each state): to keep the options that are really chosen there
    Xp = _state(X)
    policy = R._policy(Xp).fit(Xp, X["option_i"].to_numpy(int))
    pol = _high_policy(policy, X)
    print("\n### What the tree sees best (from the 3rd to the 6th camp)\n\nIn how many decisions each option "
          "comes out as the best at 90 s, among those in the table that at least 5% of Master-and-above "
          "junglers choose in that state, in total and according to where the bot wave will be on arrival.\n")
    vals = np.column_stack([np.where(pol[:, OPTIONS.index(a)] >= R.MINIMUM, against[a][90], np.nan) for a in ALTERNATIVES])
    best = np.array(ALTERNATIVES)[np.argmax(np.where(np.isnan(vals), -np.inf, vals), axis=1)]
    wave_bot = df["bot_wave_arrives"].to_numpy(float)
    groups = [("all", mid_)] + [(n, mid_ & ~np.isnan(wave_bot) & r(np.nan_to_num(wave_bot, nan=0.5)))
                                     for n, r in WAVE_STATES]
    print("| option | " + " | ".join(n for n, _ in groups) + " |\n" + "|---" * (len(groups) + 1) + "|")
    for a in ALTERNATIVES:
        print(f"| {a} | " + " | ".join(f"{(best[s] == a).mean():.0%}" for _, s in groups) + " |")

    # the final model, with everything, and how much each thing in the lane moves a gank
    mods = _fit(df, X, mask)
    (output / "outcomes_model.pkl").write_bytes(pickle.dumps({"models": mods, "betas": betas, "policy": policy,
                                                                 "columns": columns, "categories": categories}))
    print("\n## How much each thing in the lane moves a gank\n\n3,000 random decisions from the 3rd to the "
          "6th camp. In each one only that is changed in the lane it goes to, from the hard value to the easy "
          "one, and the probability that the gank ends in a kill (30 s) and what ganking is worth against "
          "continuing to clear (90 s) are looked at, on average.\n")
    print("| in that lane | top: kill | mid: kill | bot: kill | bot: gank − clear |\n|---|---|---|---|---|")
    sample = df[mid].sample(min(3000, int(mid.sum())), random_state=0).reset_index(drop=True)
    for name, x, hard, easy in FACTORS:
        cells, value_bot = [name], ""
        for lane in LANES:
            res = []
            for fit_ in (hard, easy):
                d2 = sample.copy()
                d2[f"{lane}_{x}"] = d2[f"{lane}_rivals_alive"] if fit_ == "alive" else fit_
                Xg = _X(d2, categories, columns, option=f"gank {lane}")
                Xc = _X(d2, categories, columns, option="camp")
                res.append((np.nanmean(p_kill(mods, Xg)), np.nanmean(ev(mods, betas[90], Xg)[0] - ev(mods, betas[90], Xc)[0])))
            cells.append(f"{_p(res[0][0])} → {_p(res[1][0])}")
            if lane == "bot":
                value_bot = f"{_f(res[0][1])} → {_f(res[1][1])}"
        print("| " + " | ".join(cells + [value_bot]) + " |")


# ---------------------------------------------------------------- each option's value, corrected with what was measured

# The tree gives what each option is worth against continuing to clear as the sum of its outcomes, and state by state that
# came out flattened (2nd version) or moved senselessly (3rd). Here it is corrected with what was measured, with a doubly
# robust estimator: to what the tree says is added what really came out for whoever chose that option minus what the tree
# expected, weighted by how rare it was to choose it in that state (the policy, out of fold). If the tree or the policy
# are right, the mean comes out right. A heavily smoothed model learns that correction state by state; where almost nobody
# chooses it (below FLOOR), the tree is kept.
FLOOR = 0.03
SMOOTH = dict(max_iter=150, learning_rate=0.03, max_leaf_nodes=8, min_samples_leaf=1000, l2_regularization=5.0,
             random_state=0)
CORRECTED = tuple(a for a in ALTERNATIVES if a != "camp")


def _smooth(mask):
    from sklearn.ensemble import HistGradientBoostingRegressor

    return HistGradientBoostingRegressor(**SMOOTH, categorical_features=mask)


def _propensiones(X: pd.DataFrame, games: np.ndarray) -> np.ndarray:
    """(rows, OPTIONS): the probability that that player chooses each option in that state, out of fold."""
    from sklearn.model_selection import GroupKFold

    import routes_model as R

    Xp, y = _state(X), X["option_i"].to_numpy(int)
    pi = np.zeros((len(X), len(OPTIONS)))
    for tr, te in GroupKFold(FOLDS).split(Xp, groups=games):
        m = R._policy(Xp).fit(Xp.iloc[tr], y[tr])
        pi[np.ix_(te, m.classes_.astype(int))] = m.predict_proba(Xp.iloc[te])
        print("(propensities: fold done)", file=sys.stderr, flush=True)
    return pi


def _X_of(df, categories, columns, option) -> pd.DataFrame:
    """The features for the model of an option's correction: the state and those of the lane it goes to."""
    return _X(df, categories, columns, option=option).drop(columns=["option_i"])


def _se_games(v: np.ndarray, games: np.ndarray) -> float:
    """The error of v's mean, grouping by match (the decisions of one match aren't independent)."""
    ok = ~np.isnan(v)
    v, p = v[ok], games[ok]
    if len(v) < 30:
        return np.nan
    total = pd.Series(v - v.mean()).groupby(p).sum().to_numpy()
    return float(np.sqrt((total ** 2).sum()) / len(v))


def cmd_correct(output: Path, decisions: Path) -> None:
    from sklearn.model_selection import GroupKFold

    _import_deps()
    import routes_model as R

    dm = pickle.loads((output / "outcomes_model.pkl").read_bytes())
    oof = pickle.loads((output / "outcomes_oof.pkl").read_bytes())
    categories, columns = dm["categories"], dm["columns"]
    df = _join(output, decisions).reset_index(drop=True)
    df = df[df["option"].isin(OPTIONS)].reset_index(drop=True)
    keys = oof["keys"].reset_index(drop=True)
    assert (keys[["game", "jungler", "decision"]].to_numpy() == df[["game", "jungler", "decision"]].to_numpy()).all()
    games, half = df["game"].to_numpy(), df["game"].map(_half).to_numpy()
    X = _X(df, categories, columns)
    chosen_, moment = X["option_i"].to_numpy(int), _moment(df["decision"])
    pi = _propensiones(X, games)
    ci = OPTIONS.index("camp")

    # what the tree says, with its level (the values' regression doesn't keep its constant: it is taken from what was chosen)
    mu = {}
    for h, col in HORIZONS.items():
        y = df[col].to_numpy(float)
        rest = y - oof["pred"][h]
        level = np.array([np.nanmean(rest[moment == b]) for b in range(len(MOMENTS))])[moment]
        mu[h] = {a: oof["against"][a][h] + level for a in ALTERNATIVES}

    tree, psi, tau, at = {}, {}, {}, {}
    models, halves = {}, {}
    for a in CORRECTED:
        ia = OPTIONS.index(a)
        at[a] = (pi[:, ia] >= FLOOR) & (pi[:, ci] >= FLOOR)
        Xa = _X_of(df, categories, columns, a)
        Xa = Xa[_useful(Xa, at[a])]
        models[a, "_columns"] = list(Xa.columns)
        mask = _mask(Xa)
        for h, col in HORIZONS.items():
            y = df[col].to_numpy(float)
            tree[a, h] = mu[h][a] - mu[h]["camp"]
            p = tree[a, h] + (chosen_ == ia) / np.maximum(pi[:, ia], FLOOR) * (y - mu[h][a]) \
                - (chosen_ == ci) / np.maximum(pi[:, ci], FLOOR) * (y - mu[h]["camp"])
            psi[a, h] = np.where(at[a] & ~np.isnan(y), p, np.nan)
            ok = ~np.isnan(psi[a, h])
            t = tree[a, h].copy()
            idx = np.flatnonzero(ok)
            for tr, te in GroupKFold(FOLDS).split(idx, groups=games[idx]):
                m = _smooth(mask).fit(Xa.iloc[idx[tr]], psi[a, h][idx[tr]])
                t[idx[te]] = m.predict(Xa.iloc[idx[te]])
            tau[a, h] = t
            models[a, h] = _smooth(mask).fit(Xa.iloc[idx], psi[a, h][idx])
            if h == 90:  # stability: each half of the matches on its own
                halves[a] = [np.where(at[a], _smooth(mask).fit(Xa.iloc[idx[half[idx] == k]],
                                                                  psi[a, h][idx[half[idx] == k]]).predict(Xa),
                                       tree[a, h]) for k in (0, 1)]
        print(f"({a}: done)", file=sys.stderr, flush=True)
    (output / "value_model.pkl").write_bytes(pickle.dumps({"models": models, "floor": FLOOR}))

    print("# The value of each option, corrected with what was measured\n\nWhat each option is worth against continuing to clear: the "
          "tree (the sum of its outcomes), corrected with what really came out for whoever chose it and weighted by how rare "
          f"it was to choose it in that state. Where fewer than {FLOOR:.0%} choose it (or continuing to clear), it keeps the "
          "tree. WP points; everything with games the models have not seen.\n")
    print("## Does it reproduce what was measured?\n\n\"Measured\" is the one from before: whoever chose it "
          "minus whoever kept clearing in that group. \"Measured, adjusted\" is the same weighted by the "
          "policy, which removes what separates whoever chooses each thing within the group (± its error, "
          "grouping by game). \"Corrected\" is what the new model gives, on average in the group.\n")
    mid_, late_ = df["decision"].between(3, 6).to_numpy(), (df["decision"] >= 7).to_numpy()
    groups = []
    for lane in LANES:
        wave = df[f"{lane}_wave_arrives"].to_numpy(float)
        for name, rule in WAVE_STATES:
            for op in (f"gank {lane}", f"dive {lane}"):
                groups.append((f"{op}, {name}", op, mid_ & ~np.isnan(wave) & rule(np.nan_to_num(wave, nan=0.5))))
    for lane in LANES:
        rival_no_flash = df[f"{lane}_no_flash_rival"].fillna(0).to_numpy()
        groups += [(f"gank {lane}, the rival with flash", f"gank {lane}", mid_ & (rival_no_flash == 0)),
                   (f"gank {lane}, the rival without flash", f"gank {lane}", mid_ & (rival_no_flash >= 1))]
    eb = R._base_states(df)
    groups += [(f"base, {n}", "base", late_ & (eb == n)) for n in R.BASE_STATES]
    print("| group (from the 3rd to the 6th camp; base, from the 7th) | choose it | tree | measured | "
          "measured, adjusted | corrected | tree at 5 min | adjusted at 5 min | corrected at 5 min "
          "|\n|---|---|---|---|---|---|---|---|---|")
    for name, op, sel in groups:
        n_op = int((sel & (chosen_ == OPTIONS.index(op))).sum())
        cells = [name, f"{n_op:,d}"]
        for h, col in HORIZONS.items():
            dm_, err, _ = _measured_diff(df, sel, op, "camp", col)
            fitted = psi[op, h][sel]
            cells_h = [_f(np.nanmean(tree[op, h][sel])), f"{_f(dm_)} (±{_f(err, '{:.2f}')})" if h == 90 and not np.isnan(dm_) else "",
                        f"{_f(np.nanmean(fitted))} (±{_f(_se_games(fitted, games[sel]), '{:.2f}')})",
                        _f(np.nanmean(tau[op, h][sel]))]
            cells += cells_h if h == 90 else [cells_h[0], cells_h[2], cells_h[3]]
        print("| " + " | ".join(cells) + " |")

    print("\n## Is it stable?\n\nThe correction model made twice, each with one half of the games, and both "
          "applied to all the decisions from the 3rd to the 6th camp: the correlation between what each half "
          "gives, at 90 s. With 1 they would give the same.\n")
    print("| option | decisions with similar cases | correlation between halves |\n|---|---|---|")
    for a in CORRECTED:
        s = mid_ & at[a]
        r = np.corrcoef(halves[a][0][s], halves[a][1][s])[0, 1] if s.sum() > 100 else np.nan
        print(f"| {a} | {s.mean():.0%} | {_f(r, '{:.2f}')} |")

    print("\n## What comes out best\n\nFrom the 3rd to the 6th camp, among the options that at least 5% of "
          "Master-and-above junglers choose in that state, at 90 s; and how many times the two halves agree "
          "on the best.\n")
    pol = _high_policy(dm["policy"], X)
    def best(values):
        v = np.column_stack([np.zeros(len(df))] + [values[a] for a in CORRECTED])
        cand = np.column_stack([pol[:, ci] >= R.MINIMUM] + [pol[:, OPTIONS.index(a)] >= R.MINIMUM for a in CORRECTED])
        return np.array(("camp",) + CORRECTED)[np.argmax(np.where(cand, v, -np.inf), axis=1)]
    m_c, m_a = best({a: tau[a, 90] for a in CORRECTED}), best({a: tree[a, 90] for a in CORRECTED})
    m0, m1 = best({a: halves[a][0] for a in CORRECTED}), best({a: halves[a][1] for a in CORRECTED})
    print("| option | the best, corrected | the best, the tree |\n|---|---|---|")
    for a in ("camp",) + CORRECTED:
        print(f"| {a} | {(m_c[mid_] == a).mean():.0%} | {(m_a[mid_] == a).mean():.0%} |")
    print(f"\nThe two halves agree on the best option in {(m0[mid_] == m1[mid_]).mean():.0%} of the "
          "decisions.")


# ---------------------------------------------------------------- one match's tree

def cmd_game(output: Path, pid: str, champion: str, rows: Path) -> None:
    _import_deps()
    import routes_model as R

    dm = pickle.loads((output / "outcomes_model.pkl").read_bytes())
    categories, columns = dm["categories"], dm["columns"]
    df = pd.read_csv(rows, low_memory=False)
    n = pd.read_csv(output / "outcomes.csv.gz")
    df = df.merge(n[n["game"] == pid], on=["game", "jungler", "decision"], how="inner")
    df = df[df["jungler"] == champion].sort_values("t").reset_index(drop=True)
    pol = _high_policy(dm["policy"], _X(df, categories, columns))
    print(f"## {champion} · {pid}\n")
    print("In each decision, the options that at least 5% of Master-and-above junglers choose in that state. "
          "For each one, what usually happens and what it is worth (WP points at 90 s and 5 min, against the "
          "best of those options). In those that go to a lane, \"the gank ends in a kill\" is a kill of a "
          "rival of that lane within 30 s of arriving; in the rest, \"kill\" is taking part in one within 90 "
          "s. Each lane's wave is where it will be on arrival (0, at their tower; 1, at the rival's).\n")
    for i, f in df.iterrows():
        candidates_ = [o for k, o in enumerate(OPTIONS) if pol[i, k] >= R.MINIMUM]
        for o in (f["option"], "camp"):  # the chosen one and, as a reference, continuing to clear
            if o not in candidates_:
                candidates_.append(o)
        X = pd.concat([_X(df.iloc[[i]], categories, columns, option=o) for o in candidates_], ignore_index=True)
        v90, expected_values = ev(dm["models"], dm["betas"][90], X)
        v300, _ = ev(dm["models"], dm["betas"][300], X)
        pk = p_kill(dm["models"], X)
        health = f"{float(f['health']):.0%}" if pd.notna(f["health"]) else "?"
        waves = " · ".join(f"{c} {_f(f[f'{c}_wave_arrives'], '{:.2f}')}" for c in LANES)
        print(f"- **{R._clock(f['t'])}** · after {f['after']} · level {int(f['level_xp'])} · health {health} · "
              f"{int(f['gold_unspent'])} gold · wave on arrival: {waves}")
        for k, o in sorted(enumerate(candidates_), key=lambda kv: -v90[kv[0]]):
            e = dict(zip(OUTCOMES, expected_values[k]))
            keys = [("he_dies", "died"), ("flash_rival", "flash rival"), ("camps_stolen", "steals camp"),
                      ("allies_fall_near", "an ally falls")]
            # what the model gives is expected counts in 90 s; the probability that it happens at least once is from Poisson
            chunks = [f"the gank ends in a kill {_p(pk[k])}" if not np.isnan(pk[k]) else f"kill {_p(1 - np.exp(-e['kills_with_him']))}"]
            chunks += [f"{nm} {_p(1 - np.exp(-e[x]))}" for x, nm in keys if e[x] >= 0.03]
            did = " ← **did this one**" if o == f["option"] else ""
            print(f"  - {o} ({_p(pol[i, OPTIONS.index(o)])} of the high league): {_c(v90[k] - v90.max())} at 90 s, "
                  f"{_c(v300[k] - v300.max())} at 5 min · {', '.join(chunks)}{did}")


def _c(x: float) -> str:
    return "=" if abs(x) < 0.05 else f"{x:+.1f}".replace("-", "−")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("command", choices=["wave", "extract", "analyse", "correct", "game"])
    ap.add_argument("output", type=Path)
    ap.add_argument("rest", nargs="*")
    ap.add_argument("--timelines", type=Path)
    ap.add_argument("--decisions", type=Path)
    ap.add_argument("--routes-model-file", type=Path)
    ap.add_argument("--rows", type=Path)
    a = ap.parse_args()
    if a.command == "wave":
        cmd_wave(a.output, a.timelines)
    elif a.command == "extract":
        cmd_extract(a.output, a.timelines, a.decisions)
    elif a.command == "analyse":
        cmd_analyse(a.output, a.decisions, a.routes_model_file)
    elif a.command == "correct":
        cmd_correct(a.output, a.decisions)
    else:
        cmd_game(a.output, a.rest[0], a.rest[1], a.rows)


if __name__ == "__main__":
    main()
