# 0004 · ARQ as the analysis queue

**Status:** accepted · **Phase:** 4 · **Resolves:** P2, P3

## Context

Creating a snapshot downloads dozens of games and timelines while respecting Riot's limits: minutes of work. It was
launched with `asyncio.create_task` inside the API process. A restart or a deployment lost the jobs in progress, which
stayed in `processing` forever (P3). Also, anyone who knew a `job_id` could query its status (P2).

## Decision

- **ARQ over Redis** runs the analyses in a separate process (`arq app.jobs.worker.WorkerSettings`).
- **Postgres's `jobs` table is the source of truth**, not Redis: it stores parameters, owner, attempts, progress and a
  `heartbeat_at` that the worker updates every 10 s.
- **Orphan recovery**: a cron every minute marks as interrupted the jobs with no heartbeat for 60 s and re-enqueues the
  ones Redis lost. The user sees the error and can retry.
- **Idempotency**: a partial unique index over the active jobs makes asking twice for the same analysis (same player and
  range) return the same job.
- **Retries** with growing waits only on `RiotUnavailableError` (up to 3 attempts): a Riot 5xx is retried; a data error
  isn't.
- All the job endpoints check the owner.
- In development without Redis, `InlineJobQueue` runs the job in the process itself with the same interface.

## Alternatives

- **Celery.** The standard, but designed for synchronous code: the Riot client is `aiohttp` and every task would have to
  be wrapped in an event loop. It also adds a broker, a results backend and quite a lot of configuration.
- **RQ / Dramatiq.** Lighter than Celery, also synchronous.
- **A Postgres table with `SELECT … FOR UPDATE SKIP LOCKED`.** No Redis, but the polling, the retries and the cron would
  have to be written by hand.

## Consequences

- Killing the worker midway through an analysis no longer leaves zombie jobs (`tests/test_jobs.py`).
- The API and the worker scale separately; a heavy analysis doesn't affect the API's latency.
- ARQ has a small community. The `JobQueue` interface (`app/jobs/queue.py`) isolates the change if it ever had to be
  replaced.
- Redis becomes mandatory in production (it already was for caching and rate limiting).
