"""The grade of each of the ten players in a sample of harvested matches, to fit the history grade.

The history grade only has what Riot's API gives (match and timeline); the analyses' comes from the replay. To bring the first closer to the
second, both things are needed per player: here the second comes out (`coach.analyse(...)["rating"]["total"]`, the points their
moments add and subtract, brought to 30 minutes) and `fit_history.py` supplies the first.

    python research/replays/grade_history.py <harvest> <output.jsonl> --leagues matches.jsonl.gz --value model.json --openings model.json \
        [--games 600] [--processes 8]
"""

from __future__ import annotations

import collections
import gzip
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import coach
import grades
import features
import wp_per_second as W


def _task(pair: tuple) -> dict:
    state, events, record, model, openings = pair
    game = Path(state).name.split(".")[0]
    try:
        raw: dict = {}
        features.one_game(Path(state), Path(events), record, Path(model) if model else None, raw=raw)
        players = []
        for j in raw["events"]["players"]:
            r = coach.analyse(raw, record, j["champion"], grades._openings(openings))
            players.append({"champion": j["champion"], "position": j["position"], "team": j["team"], "total": r["rating"]["total"]})
        return {"game": game, "players": players}
    except Exception as exc:
        return {"game": game, "error": f"{type(exc).__name__}: {exc}"}


def main() -> None:
    harvest, output = Path(sys.argv[1]), Path(sys.argv[2])
    rest = sys.argv[3:]

    def option(name: str, default: str) -> str:
        return rest[rest.index(name) + 1] if name in rest else default

    counts, processes = int(option("--games", "600")), int(option("--processes", "8"))
    with gzip.open(option("--leagues", ""), "rt", encoding="utf-8") as fh:
        leagues = {(m := json.loads(line))["match_id"].replace("_", "-"): m["tier"] for line in fh}
    pairs = []
    for state in sorted(harvest.glob("*.state.csv*")):
        game = state.name.split(".")[0]
        events = next(iter(harvest.glob(f"{game}.events.json*")), None)
        if events and leagues.get(game):
            pairs.append((str(state), str(events)))
    by_league: dict[str, list] = collections.defaultdict(list)
    for e, v in pairs:
        by_league[leagues[Path(e).name.split(".")[0]]].append((e, v))
    sample = [x for items in by_league.values() for x in items[:: max(1, len(items) // max(1, counts // len(by_league)))]]
    print(f"{len(sample)} games from {len(by_league)} leagues · {processes} processes", flush=True)
    model, openings = option("--value", ""), option("--openings", "")
    records = W.records(Path(option("--leagues", "")), {Path(e).name.split(".")[0] for e, _ in sample})
    tasks = [(e, v, records.get(Path(e).name.split(".")[0]), model, openings) for e, v in sample]
    done = bad_ones = 0
    with ProcessPoolExecutor(processes) as pool, output.open("w", encoding="utf-8") as out:
        for r in pool.map(_task, tasks):
            if "error" in r:
                bad_ones += 1
                print(f"  ERROR  {r['game']}: {r['error']}", flush=True)
                continue
            r["league"] = leagues.get(r["game"], "")
            out.write(json.dumps(r, ensure_ascii=False) + "\n")
            done += 1
            if done % 25 == 0:
                out.flush()
                print(f"  {done}/{len(tasks)}", flush=True)
    print(f"{output}: {done} games, {bad_ones} with errors", flush=True)


if __name__ == "__main__":
    main()
