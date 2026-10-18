# Architecture Decision Records

One decision per file, on one page: context, decision, alternatives and consequences.
Problems `P1`…`P17` are those of the initial diagnosis in [`docs/history/plan-web.md`](../history/plan-web.md).

| ADR | Decision | Status |
|---|---|---|
| [0001](0001-match-and-participant.md) | Separate match and participant in the data model | Accepted |
| [0002](0002-sqlalchemy-2-and-handwritten-sql.md) | Async SQLAlchemy 2.0 for the application and handwritten SQL for analytics | Accepted |
| [0003](0003-duckdb-in-the-core.md) | DuckDB as `ygg-core`'s local store, alongside Postgres | Accepted |
| [0004](0004-arq-not-celery.md) | ARQ as the analysis queue, with Postgres as the source of truth | Accepted |
| [0005](0005-sse-not-websockets.md) | Server-Sent Events for analysis progress | Accepted |
| [0006](0006-httponly-cookie-not-localstorage.md) | In-memory access token and an httpOnly-cookie refresh token | Accepted |
