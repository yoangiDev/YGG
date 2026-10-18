"""The per-league and role references YGG evaluates with: match grade, cards, radar and trends.

    python research/replays/references.py <harvest> --leagues <matches.jsonl.gz>
        [--output packages/ygg-core/src/ygg_core/metrics/rank_reference.json]

It replaces the tables written by hand (ygg_core/metrics/benchmarks.py): for each player of each
harvest match, the same metrics the API computes from Riot's match, with the same fields and
formulas (ygg_core/riot/parsers.py), but taken from the .rofl's statsJson. And besides:

- gold and CS **against the lane opponent at minute 14**, from the per-second table (the API's @14
  differences come from the timeline);
- deaths **before and after minute 14**, from the `Death` events without the revivals.

Per league and role the mean and the 10th, 35th, 50th, 65th and 90th percentiles of a match are stored. The mean is what a
player of that league does (radar and trends); the percentiles are the bands by which they are judged.
"""
from __future__ import annotations

import collections
import csv
import gzip
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import moments as M
import numpy as np

LEAGUES = ["GOLD", "PLATINUM", "EMERALD", "DIAMOND", "MASTER", "GRANDMASTER", "CHALLENGER"]
ROLE = {"TOP": "TOP", "JUNGLE": "JUNGLE", "MIDDLE": "MID", "BOTTOM": "ADC", "UTILITY": "SUPPORT"}
PERCENTILES = [10, 35, 50, 65, 90]  # the grade's anchors: 40, 55, (median), 70 and 85
LANING_END = 840.0  # minute 14: end of the laning phase, like ygg_core's LANE_PHASE_SEC
PER_CAMP = 4  # each jungle camp gives 4 CS (ygg_core's CS_PER_CAMP)


def share(value: float, total: float) -> float:
    """% of their team, like ygg_core's `_share`."""
    return round(value / total * 100, 1) if total > 0 else 0.0


def at_14(state: Path) -> dict[str, tuple[float, float]]:
    """(total gold, minion + jungle CS) of each champion at second 840."""
    out = {}
    with M.open_file(state) as fh:
        for row in csv.DictReader(fh):
            if row["time"] == "840.0" and row["total_gold"]:
                out[row["net_id"]] = (float(row["total_gold"]),
                                         float(row["cs"] or 0) + float(row["jungle_minions"] or 0))
    return out


def one_game(pair: tuple[str, str]) -> list[dict]:
    events_path, state_path = pair
    with M.open_file(Path(events_path)) as fh:
        ev = M.drop_revived(json.load(fh))
    minutes = ev["game_length"] / 60
    fifteen = at_14(Path(state_path)) if ev["game_length"] > LANING_END else {}
    deaths = collections.defaultdict(lambda: [0, 0])
    for e in ev["events"]:
        if e["type"] == "Death":
            deaths[e["net_id"]][e["time"] >= LANING_END] += 1

    rows = list(zip(ev["players"], ev["stats"], strict=True))
    team = collections.defaultdict(lambda: collections.Counter())
    for p, s in rows:
        team[p["team"]]["kills"] += int(s["CHAMPIONS_KILLED"])
        team[p["team"]]["damage"] += int(s["TOTAL_DAMAGE_DEALT_TO_CHAMPIONS"])
        team[p["team"]]["gold"] += int(s["GOLD_EARNED"])
    rival = {(p["team"], p["position"]): p["net_id"] for p, _ in rows}

    out = []
    for p, s in rows:
        role = ROLE.get(p["position"])
        if role is None:
            continue
        k, d, a = int(s["CHAMPIONS_KILLED"]), int(s["NUM_DEATHS"]), int(s["ASSISTS"])
        damage, gold = int(s["TOTAL_DAMAGE_DEALT_TO_CHAMPIONS"]), int(s["GOLD_EARNED"])
        damage_share = share(damage, team[p["team"]]["damage"])
        gold_share = share(gold, team[p["team"]]["gold"])
        m = {
            "kills": k, "deaths": d, "assists": a,
            "kda": (k + a) / max(d, 1),
            "cs_per_min": (int(s["MINIONS_KILLED"]) + int(s["NEUTRAL_MINIONS_KILLED"])) / minutes,
            "damage_per_min": damage / minutes,
            "kill_participation": share(k + a, team[p["team"]]["kills"]),
            "damage_share": damage_share,
            "efficiency": damage_share / gold_share if gold_share else None,
            "vision_score": int(s["VISION_SCORE"]),
            "vision_per_min": int(s["VISION_SCORE"]) / minutes,
            "control_wards": int(s["VISION_WARDS_BOUGHT_IN_GAME"]),
            "damage_structures": int(s["TOTAL_DAMAGE_DEALT_TO_BUILDINGS"]),
            "enemy_jg_camps": int(s.get("NEUTRAL_MINIONS_KILLED_ENEMY_JUNGLE") or 0) / PER_CAMP,
            "laning_deaths": deaths[p["net_id"]][0],
            "post14_deaths": deaths[p["net_id"]][1],
        }
        against = rival.get(("200" if p["team"] == "100" else "100", p["position"]))
        if p["net_id"] in fifteen and against in fifteen:
            m["gold_diff_14"] = fifteen[p["net_id"]][0] - fifteen[against][0]
            m["cs_diff_14"] = fifteen[p["net_id"]][1] - fifteen[against][1]
        out.append({"game": Path(events_path).name.split(".")[0], "role": role, "kills_game":
                      sum(team[t]["kills"] for t in team), **m})
    return out


def main() -> None:
    harvest = Path(sys.argv[1])
    rest = sys.argv[2:]
    with gzip.open(rest[rest.index("--leagues") + 1], "rt", encoding="utf-8") as fh:
        leagues = {(m := json.loads(line))["match_id"].replace("_", "-"): m["tier"] for line in fh}
    output = Path(rest[rest.index("--output") + 1] if "--output" in rest else
                  Path(__file__).resolve().parents[2] / "packages/ygg-core/src/ygg_core/metrics/rank_reference.json")

    pairs = []
    for events in sorted(harvest.glob("*.events.json.gz")):
        game = events.name.split(".")[0]
        if game in leagues and (state := harvest / f"{game}.state.csv.gz").exists():
            pairs.append((str(events), str(state)))
    print(f"{len(pairs)} games with league")
    with ProcessPoolExecutor(max(1, (os.cpu_count() or 4) // 2)) as pool:
        rows = [f for batch in pool.map(one_game, pairs, chunksize=8) for f in batch]
    assert len(rows) == 10 * len(pairs), f"{len(rows)} rows for {len(pairs)} games"

    groups = collections.defaultdict(list)
    games = collections.defaultdict(dict)
    for f in rows:
        groups[(leagues[f["game"]], f["role"])].append(f)
        games[leagues[f["game"]]][f["game"]] = f["kills_game"]

    metrics = [k for k in rows[0] if k not in ("game", "role", "kills_game")] + ["gold_diff_14", "cs_diff_14"]
    table: dict = {}
    rng = np.random.default_rng(1619)  # fixed: the same harvest always gives the same references
    for league in LEAGUES:
        for role in ROLE.values():
            fs = groups[(league, role)]
            table.setdefault(league, {})[role] = {}
            for metric in dict.fromkeys(metrics):
                if metric == "enemy_jg_camps" and role != "JUNGLE":  # outside the jungler it is almost always 0
                    continue
                xs = np.array([f[metric] for f in fs if f.get(metric) is not None], float)
                # counts (kills, deaths, wards) repeat value across several percentiles and would leave bands of
                # width 0: ±0.5 is spread at random, the usual continuity correction. The mean doesn't change
                jittered = xs + rng.uniform(-0.5, 0.5, len(xs)) if np.all(xs == np.round(xs)) else xs
                table[league][role][metric] = {"mean": round(float(xs.mean()), 3), "n": len(xs),
                                             "p": [round(float(v), 3) for v in np.percentile(jittered, PERCENTILES)]}
    data = {
        "source": "research/replays/references.py over the 16.19 harvest (EUW, since 2026-09-23)",
        "games": {league: len(games[league]) for league in LEAGUES},
        "percentiles": PERCENTILES,
        # kills of both sides in an average match: the pace against which kills and deaths are normalised
        "kills_per_game": {league: round(float(np.mean(list(games[league].values()))), 2) for league in LEAGUES},
        "metrics": table,
    }
    output.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    ch = table["CHALLENGER"]
    print(f"wrote {output} · Challenger ADC: mean CS/min {ch['ADC']['cs_per_min']['mean']}, "
          f"p65 {ch['ADC']['cs_per_min']['p'][3]} · mean deaths {ch['ADC']['deaths']['mean']}")


if __name__ == "__main__":
    main()
