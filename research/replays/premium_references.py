"""The replay analysis references: how each column of `players.csv` is distributed in each league and role.

    python research/replays/premium_references.py research/ladder/data/harvest-16.19/features/players.csv \
        apps/api/app/service/premium_reference.json [grades.json]

The third argument, if passed, is what `grades.py` produces: how a match's grade is distributed in each league and
position, which is how the analysis converts it into a 1-100. It goes in the same reference, under `grades`.

It is the rule by which the replay analysis measures a player (their percentile in each column) and by which the
review knows what matters to their league: for each numeric column, per (league, position), the 10th, 25th, 50th,
75th and 90th percentiles, the mean, and **the mean of those who win and that of those who lose**. That difference says what distinguishes
whoever wins in that position, which is what deserves a sentence in the review; a column in which winning and losing give
the same may be curious, but it isn't advice.

Only matches that match their statsJson (`adds_up = 1`). The identity columns (match, champion,
team…) and the result aren't metrics and are left out.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb

OUTSIDE = {"game", "champion", "position", "team", "wins", "adds_up", "league",
         # they don't say how one plays: how long the match lasts, at what second each back falls and concept parameters
         "duration", "back1_time", "back2_time", "idle_period", "idle_margin", "recall_when_max"}
QUANTILES = (0.10, 0.25, 0.50, 0.75, 0.90)
ABSURD = 1e7  # no measurement of a match reaches this (the damage or gold of a long match, tens of thousands)


def references(players: Path) -> dict:
    with_ = duckdb.connect()
    # an in-memory table: a view would read the CSV (22 MB) again on every query
    with_.execute(f"CREATE TABLE j AS SELECT * FROM read_csv_auto('{players.as_posix()}', sample_size=-1) "
                "WHERE adds_up = 1 AND league IS NOT NULL")
    kinds = with_.execute("DESCRIBE j").fetchall()
    # the `*_team` columns are the player's team (100 or 200) that each concept repeats, not a measurement
    columns = [name for name, kind, *_ in kinds
                if name not in OUTSIDE and not name.endswith("_team")
                and kind in ("BIGINT", "INTEGER", "DOUBLE", "FLOAT", "HUGEINT", "SMALLINT")]
    out: dict = {"columns": columns, "quantiles": list(QUANTILES), "leagues": {}}
    for league, position, n in with_.execute("SELECT league, position, count(*) FROM j GROUP BY ALL").fetchall():
        out["leagues"].setdefault(league, {})[position] = {"games": n, "columns": {}}
    for c in columns:  # one query per column, grouped by league and position
        q = f'quantile_cont("{c}", [{", ".join(map(str, QUANTILES))}])'
        # without the impossible values (|x| ≥ ABSURD): uninitialised memory that the decoder lets through very occasionally;
        # the percentiles withstand it, but a single one is enough to drag a mean down to -7e21
        for league, position, cuts, mean, wins, loses, n in with_.execute(
                f'SELECT league, position, {q}, avg("{c}"), avg("{c}") FILTER (wins = 1), avg("{c}") FILTER (wins = 0), '
                f'count("{c}") FROM j WHERE abs("{c}") < {ABSURD} GROUP BY ALL').fetchall():
            if n:  # with not a single value in that position (e.g. the marksman's in a top), it isn't stored
                values = [*cuts, mean, wins, loses]
                out["leagues"][league][position]["columns"][c] = [
                    round(v, 4) if v is not None else None for v in values] + [n]
    return out


def percentile(value: float, cuts: list[float]) -> float:
    """The approximate percentile of `value` given the QUANTILES cuts: interpolated between them and extrapolated to
    the sides with the same slope, without leaving 1-99."""
    xs, ps = cuts, [100 * p for p in QUANTILES]
    if value <= xs[0]:
        stretch, i = xs[1] - xs[0], 0
    elif value >= xs[-1]:
        stretch, i = xs[-1] - xs[-2], len(xs) - 2
    else:
        i = max(j for j in range(len(xs) - 1) if xs[j] <= value)
        stretch = xs[i + 1] - xs[i]
    if stretch <= 0:
        return 50.0 if value == xs[i] else (1.0 if value < xs[i] else 99.0)
    p = ps[i] + (value - xs[i]) / stretch * (ps[i + 1] - ps[i])
    return max(1.0, min(99.0, p))


if __name__ == "__main__":
    if len(sys.argv) == 1:  # the minimal check of `percentile`
        cuts = [10.0, 20.0, 30.0, 40.0, 50.0]
        assert percentile(30, cuts) == 50 and percentile(20, cuts) == 25 and percentile(45, cuts) == 82.5
        assert percentile(-100, cuts) == 1 and percentile(1000, cuts) == 99
        assert percentile(5, [5.0, 5.0, 5.0, 5.0, 5.0]) == 50
        print("ok")
    else:
        output = Path(sys.argv[2])
        data = references(Path(sys.argv[1]))
        if len(sys.argv) > 3:
            data["grades"] = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
        output.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        n = sum(len(p) for p in data["leagues"].values())
        print(f"{output}: {len(data['columns'])} columns, {n} groups (league, position), "
              f"{output.stat().st_size / 1e3:.0f} KB")
