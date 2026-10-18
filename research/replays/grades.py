"""How the grade of a match is distributed in each league and position, so it can be set from 1 to 100.

The replay analysis grade comes from what that match's moments add and subtract (`coach.grade`): each hit
adds and each mistake subtracts, in neutral WP points. To convert that sum into a grade we need to know what it is compared with,
so this computes it over a sample of the harvest and stores the 10th, 35th, 50th, 65th and 90th percentiles of each
(league, position) —the same anchors as the app's match grade, `ygg_core.metrics.match_score`—.

    python research/replays/grades.py <harvest> <output.json> --leagues matches.jsonl.gz [--value model.json] \
        [--openings model.json] [--games 400] [--processes 6]

With `--value` the matches bring their WP curve, which is where the points of the fights and swings come from; without
it the moments measured in WP don't add up, so it should be passed (it is what the real analysis uses).
"""

from __future__ import annotations

import collections
import functools
import gzip
import json
import os
import statistics
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import coach
import features
import wp_per_second as W

QUANTILES = (10, 35, 50, 65, 90)  # the grade's anchors (match_score.ANCHOR_SCORES)
MINIMUM = 40  # matches per (league, position) to store their percentiles


@functools.cache
def _openings(path: str) -> dict | None:
    """The openings model, once per process: the grade has to come out the same as in the real analysis."""
    return json.loads(Path(path).read_text(encoding="utf-8")) if path else None


def _task(pair: tuple) -> dict:
    """What the moments of each of a match's ten players add up to: [(position, total), ...]."""
    state, events, record, model, openings = pair
    game = Path(state).name.split(".")[0]
    try:
        raw: dict = {}
        features.one_game(Path(state), Path(events), record, Path(model) if model else None, raw=raw)
        out = []
        for j in raw["events"]["players"]:
            r = coach.analyse(raw, record, j["champion"], _openings(openings))
            out.append((j["position"], r["rating"]["total"]))
        return {"game": game, "totals": out}
    except Exception as exc:
        return {"game": game, "error": f"{type(exc).__name__}: {exc}"}


def main() -> None:
    harvest, output = Path(sys.argv[1]), Path(sys.argv[2])
    rest = sys.argv[3:]

    def option(name: str, default: str) -> str:
        return rest[rest.index(name) + 1] if name in rest else default

    counts = int(option("--games", "400"))
    processes = int(option("--processes", str(max(1, (os.cpu_count() or 4) // 2))))
    with gzip.open(option("--leagues", ""), "rt", encoding="utf-8") as fh:
        leagues = {(m := json.loads(line))["match_id"].replace("_", "-"): m["tier"] for line in fh}

    pairs = []
    for state in sorted(harvest.glob("*.state.csv*")):
        game = state.name.split(".")[0]
        events = next(iter(harvest.glob(f"{game}.events.json*")), None)
        if events and leagues.get(game):
            pairs.append((str(state), str(events)))
    # spread by league: a sample of the first ones would be almost all from the same one
    by_league: dict[str, list] = collections.defaultdict(list)
    for e, v in pairs:
        by_league[leagues[Path(e).name.split(".")[0]]].append((e, v))
    sample = [x for items in by_league.values() for x in items[:: max(1, len(items) // max(1, counts // len(by_league)))]]
    print(f"{len(sample)} games from {len(by_league)} leagues · {processes} processes", flush=True)

    model, openings = option("--value", ""), option("--openings", "")
    records = W.records(Path(option("--leagues", "")), {Path(e).name.split(".")[0] for e, _ in sample}) if model else {}
    tasks = [(e, v, records.get(Path(e).name.split(".")[0]), model, openings) for e, v in sample]

    totals: dict[tuple[str, str], list[float]] = collections.defaultdict(list)
    bad_ones = 0
    with ProcessPoolExecutor(processes) as pool:
        for i, r in enumerate(pool.map(_task, tasks), 1):
            if "error" in r:
                bad_ones += 1
                print(f"  ERROR  {r['game']}: {r['error']}", flush=True)
                continue
            league = leagues.get(r["game"], "")
            for position, total in r["totals"]:
                totals[(league, position)].append(total)
            if i % 20 == 0 or i == len(tasks):
                print(f"  {i}/{len(tasks)} · {sum(len(v) for v in totals.values()):,d} grades", flush=True)

    out: dict[str, dict[str, list[float]]] = {}
    print("\n| league | position | games | p10 | p35 | p50 | p65 | p90 |")
    print("|" + "---|" * 8)
    for (league, position), values in sorted(totals.items()):
        if len(values) < MINIMUM:
            continue
        cuts = [round(_percentile(sorted(values), q), 2) for q in QUANTILES]
        out.setdefault(league, {})[position] = cuts
        print(f"| {league} | {position} | {len(values)} | " + " | ".join(f"{c:+.1f}" for c in cuts) + " |")
    output.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    mean = statistics.mean([v for items in totals.values() for v in items])
    print(f"\n{output}: {sum(len(v) for v in out.values())} groups, mean {mean:+.2f}"
          + (f", {bad_ones} games left out" if bad_ones else ""))


def _percentile(ordered: list[float], q: float) -> float:
    """The `q` percentile (0-100) of an already sorted list, interpolating between the two values that surround it."""
    if len(ordered) == 1:
        return ordered[0]
    i = (len(ordered) - 1) * q / 100
    under, high = int(i), min(int(i) + 1, len(ordered) - 1)
    return ordered[under] + (ordered[high] - ordered[under]) * (i - under)


if __name__ == "__main__":
    if len(sys.argv) == 1:  # the minimal percentile check
        assert _percentile([0, 10], 50) == 5 and _percentile([0, 10, 20], 50) == 10
        assert _percentile([1, 2, 3, 4, 5], 10) == 1.4 and _percentile([7], 90) == 7
        print("ok")
    else:
        main()
