# Engineering notes

Four real problems that came up while rewriting YGG (from a TFG with a Flutter client to a monorepo with a hardened API
and a web client) and how they were solved. The figures come from [`metrics.md`](metrics.md); the decisions, with their
alternatives, are in [`adr/`](adr/README.md).

Format of each one: context → problem → decision → result.

### 1. The bug that raised no errors (data model)

- **Context.** The TFG stored each game as a row tied to the analysed player, and reused already-downloaded games to avoid
  spending Riot quota.
- **Problem.** The cache looked up by `match_id`. If two consecutively tracked players had played the same game, the
  second one inherited the first one's stats: another champion, another KDA, other deaths. Nothing failed; the numbers
  were simply someone else's.
- **Decision.** Split `matches` from `match_participants` with a unique key `(match_id, puuid)`, and make the cache always
  look up by player. A three-step migration (create, copy, verify counts before dropping) so no data is lost.
  [ADR 0001](adr/0001-match-and-participant.md)
- **Result.** A test pins the case of two players in the same game. As a side effect, writes moved to batches with
  `ON CONFLICT` and an analysis reuses any already-stored game of that player.

### 2. Riot's 429s (global limiter)

- **Context.** Riot limits per key: 20 requests per second and 100 every two minutes with the development key. An
  analysis downloads each game's match and timeline in parallel.
- **Problem.** If every download manages its own pace, several in parallel exceed the limit together. 429s arrive in a
  cascade and immediate retries make it worse.
- **Decision.** A single limiter in `ygg-core`, shared by the whole process, with two sliding windows (1 s and 2 min) that
  reserve a slot *before* requesting. On a 429, a coordinated global pause using the `Retry-After`, instead of each
  request retrying on its own.
- **Result.** Downloads are spread within the quota instead of colliding with it. The time of a large analysis is set by
  the quota (100 new games ≈ 4 minutes with the development key) and is predictable.

### 3. The jobs that got lost (external queue)

- **Context.** Analyses were launched with `asyncio.create_task` inside the API and the client asked for their status
  every few seconds.
- **Problem.** Any restart or deployment left jobs in "processing" forever. Also, knowing an id you could query another
  user's job.
- **Decision.** A separate ARQ worker, with Postgres as the source of truth: a heartbeat every 10 s, a cron that marks
  jobs with no heartbeat as interrupted, idempotency with a partial unique index and retries only on Riot errors.
  Progress goes over Redis pub/sub and SSE. [ADR 0004](adr/0004-arq-not-celery.md),
  [ADR 0005](adr/0005-sse-not-websockets.md)
- **Result.** Killing the worker midway no longer leaves zombies: the user sees the error and retries. The API isn't
  affected while analysing, and progress arrives as it happens instead of at each polling interval.

### 4. Measure before optimising (web performance)

- **Context.** The rewrite's budget: LCP under 2 s on slow 4G.
- **Problem.** The first measurement gave 3.1 s on the dashboard. Compressing the files barely changed anything.
- **Decision.** Record in the performance test which element is the LCP and the resource waterfall. It showed that each
  page didn't request its data until it had downloaded all its dependencies, including Recharts and zod for a closed
  dialog. I split the app shell, the dialogs, the charts and the table into chunks.
- **Result.** Dashboard from 3.08 s to 2.34 s, player list from 2.08 s to 1.96 s and initial JS from 156 KB to 126 KB. The
  dashboard is still 340 ms above target, and what is missing is documented.
