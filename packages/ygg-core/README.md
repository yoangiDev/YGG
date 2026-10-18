# ygg-core

YGG's analysis engine. A pure Python package: it **doesn't import FastAPI or SQLAlchemy**. It takes Riot API payloads and
returns domain objects and metrics, so it is tested without a database and used the same way from the API, a worker or
the terminal.

```
ygg_core/
├─ domain/     ParticipantStats, PlayerRef, RankInfo, roles, season
├─ riot/       HTTP client, global limiter, routing, parsers and a compact game record
├─ timeline/   diffs @8/14/25, deaths and wards with coordinates, objective vision, Role Quests, map zones
├─ metrics/    semantic status, per-role radar, dashboard, aggregates, trends, game grade and WPA
├─ ddragon/    Data Dragon with swappable storage
├─ store/      DuckDB: raw-payload cache and local SQL analytics
└─ cli.py      ygg fetch / ygg stats / ygg store / ygg reparse
```

`metrics/wpa_model.py` and the `*.json` files in `metrics/` are **generated** by the scripts in
[`research/`](../../research); they aren't edited by hand.

## Installation

```bash
pip install -e "packages/ygg-core[dev]"
```

## CLI

```bash
# Download games (needs RIOT_API_KEY) and store them in the DuckDB cache
ygg fetch "Player#EUW" --region euw --from 2026-08-01 --to 2026-09-01 --out games.json

# Dashboard metrics from the file, with no network or database
ygg stats games.json --role JUNGLE

# Local analytics over everything downloaded
ygg store roles
ygg store query "select champion, count(*) from participants group by 1 order by 2 desc"
ygg store export games.parquet

# Recompute the metrics from the cached payloads, without spending Riot quota
ygg reparse <puuid>
```

## Tests

```bash
pytest packages/ygg-core        # 201 tests, 92% coverage
mypy --config-file packages/ygg-core/pyproject.toml   # strict
```

The fixtures in `tests/fixtures/match_v5/` are synthetic: they follow the match-v5 and timeline-v5 format, with made-up
identifiers.
