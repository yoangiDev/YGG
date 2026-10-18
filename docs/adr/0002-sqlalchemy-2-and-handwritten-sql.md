# 0002 · Async SQLAlchemy 2.0 and handwritten SQL for analytics

**Status:** accepted · **Phase:** 3 · **Resolves:** P7, P8

## Context

The API used the synchronous ORM inside `async` endpoints: every query blocked the event loop, and a long analysis froze
the rest of the users (P7). Also, saving a snapshot made one query per game (P8).

## Decision

- **SQLAlchemy 2.0 with typed models** (`Mapped[...]`, `mapped_column`) and `AsyncSession` over asyncpg. Alembic remains
  the only owner of the schema.
- **Batch writes** with `INSERT … ON CONFLICT` from `sqlalchemy.dialects.postgresql`, in chunks of 500 rows: a few
  statements per analysis, however many games it has.
- **Analytical queries in handwritten SQL** (`app/queries/*.sql`): per-role summaries and snapshot aggregates with
  `FILTER`, `percentile_cont` and windows. `tests/test_queries.py` checks that they give the same results as `ygg-core`'s
  formulas.

## Alternatives

- **SQLModel.** It joins the table model and the API schema in one class. Comfortable at first, but here the API
  contracts (pagination, computed fields) and the tables diverge, and it lags behind SQLAlchemy 2.0 in typing and async
  support.
- **Tortoise ORM.** Async from birth, but with a smaller ecosystem and migrations with Aerich instead of Alembic, which
  was already in the project.
- **Everything with the ORM.** Aggregations with `func.percentile_cont` and `FILTER` are harder to read in Python than in
  SQL, and SQL is what is later reviewed with `EXPLAIN`.

## Consequences

- The API doesn't block the loop; the warm dashboard responds in milliseconds ([`metrics.md`](../metrics.md)).
- With `AsyncSession` there is no lazy loading: the relationships that are used are loaded explicitly (`lazy="joined"`,
  `selectinload`). It is more code, but it makes every query visible.
- The handwritten SQL is tested against a real Postgres; the tests can't use SQLite.
