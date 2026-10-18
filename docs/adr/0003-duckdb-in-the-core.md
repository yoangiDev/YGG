# 0003 · DuckDB in `ygg-core`, alongside Postgres

**Status:** accepted · **Phase:** 1

## Context

The analysis (Riot client, timeline enrichment, metrics) was spread across FastAPI services. To test it or experiment with
a new metric you had to bring up the API and Postgres and authenticate. Extracting it to `packages/ygg-core` (a pure
Python package, with no FastAPI or SQLAlchemy) required somewhere to keep games while working outside the application.

## Decision

`ygg-core` includes `MatchStore` (`store/duckdb_store.py`), a single-file DuckDB store that:

- caches Riot's raw JSON (match and timeline), so a change in the parsers is applied with `ygg reparse` without spending
  API quota again;
- stores the `ParticipantStats` in a table whose schema is derived from the dataclass's annotations, so it can't get out
  of sync;
- supports ad hoc SQL, a per-role summary and Parquet export/import.

The CLI (`ygg fetch | stats | store | reparse`) works on that file. Postgres remains the web application's transactional
database: users, players, snapshots and jobs.

## Alternatives

- **Postgres in the core too.** It forces having a server for any experiment and mixes the domain with the API's
  infrastructure.
- **SQLite.** Just as portable, but row-oriented: worse for aggregations over thousands of participants and without
  Parquet.
- **Loose Parquet files with pandas.** Good for analysis, bad as an incremental cache with upserts.

## Consequences

- The core is tested without services (201 tests, strict mypy) and works as a tool by itself.
- There are two storage engines, with different roles: local, analytical DuckDB and shared, transactional Postgres.
  Metrics are computed with the same Python code in both cases.
- DuckDB is an optional dependency of the core: the API doesn't import it.
