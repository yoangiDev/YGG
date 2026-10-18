# YGG → web application

A plan for migrating to the web (React + TypeScript) and hardening the backend, aimed at making the project a main piece of the portfolio.

- **Date:** 10 September 2026
- **Assumed pace:** 4-6 h/day, 3-4 weeks (~20-25 working days, ~110 h)
- **Decisions made:** React 19 + TS + Vite (SPA) frontend · `ygg-core` as an engine package the API consumes · a live public demo with a Riot Personal API Key · a monorepo architecture · data layer: async SQLAlchemy 2.0 + handwritten SQL for analytics + DuckDB in the core

---

## 1. What there is today

### Inventory

| Layer | Stack | Status |
|---|---|---|
| Backend | FastAPI 0.115, SQLAlchemy 2.0 (**synchronous**, psycopg2), Alembic, PostgreSQL (Supabase), python-jose + bcrypt, aiohttp | Deployed on Render (`ygg-tfg.onrender.com`) |
| Frontend | Flutter 3.11, Riverpod 2, Dio, fl_chart, `shared_preferences` | Cross-platform (android/ios/web/windows/linux/macos) |
| CI | GitHub Actions | Only builds Windows / Linux / APK. **It doesn't run the tests or build the web** |
| Tests | pytest + pytest-asyncio (8 files, ~75 KB) + Dart tests | They exist and are decent, but nobody runs them automatically |
| Storage | Supabase Storage (avatars), local disk for the Data Dragon cache | Render's disk is ephemeral |

Heavy pieces: `riot_client.py` (1,286 lines), `dashboard_service.py` (585), and on the front end monolithic files such as `admin_users.dart` (49 KB), `hextech_header.dart` (38 KB), `snapshot_panel.dart` (34 KB), `player_detail_screen.dart` (32 KB).

### What already sells well (keep intact)

1. **A serious Riot API client.** `RiotRateLimiter` is a global sliding-window limiter (10 req/s, 70 req/2 min) with a coordinated global pause on receiving a 429 and respect for `Retry-After`, plus separate semaphores for in-flight connections and for match+timeline pairs. This is exactly the kind of code a technical interviewer values.
2. **Timeline enrichment.** CS/gold/XP differentials at minutes 8/14/25, solo kills, *dragon setups* with detection of the jungler in the zone, an *objective vision score* by radius around the objective, death and ward events with coordinates, and a parser for season 26's Role Quests. It is real domain work, not a CRUD.
3. **An N:M snapshot↔match model** with a bridge table and a uniqueness constraint, reusing games between snapshots instead of duplicating them. And a history cache with a 1-hour TTL.
4. **A dashboard with a per-role normalised radar**, per-position ceilings, Challenger benchmarks and an optional live comparison against another Riot account.
5. **Design already defined.** The Hextech palette of `app_theme.dart` is documented in HSL and, according to the file's own comment, is a "direct translation of the React prototype's HSL values". The design tokens for Tailwind are already done.

### Problems found

Ordered by what worries me, not by where they appear.

#### Data correctness

**P1 — Two of your players in the same game overwrite each other's data.** `match_data.match_id` is globally `UNIQUE` and the row contains the stats *of one specific participant* (`champion`, `kills`, `cs_diff_14`, `player_role`…). `_parse_match(match_data, player.puuid, …)` builds the row with the analysed player's data. When that `match_id` already exists in `stats_runner.run_stats_extraction`, the code does `copy_timeline_fields(existing_match, match)` and **reuses the first player's row**, linking it to the second one's snapshot. Result: if you register two players who played together —a normal scenario in team scouting— the second one shows the first one's champion, KDA and diffs. It is the project's most serious bug and also the one that forces the model to be redesigned.

**P2 — IDOR in the job status.** `GET /snapshots/jobs/{job_id}` requires authentication but doesn't check ownership, and the `jobs` table has no `user_id`. Any authenticated user who guesses or intercepts a `job_id` reads another user's job.

**P3 — Jobs that get lost.** Analyses run with `asyncio.create_task` inside the FastAPI process. Every deploy, restart or *spin-down* of Render's free plan kills the job midway: it stays `processing` forever and the frontend polls indefinitely. `architecture.md` itself acknowledges it as a limitation.

#### Security

**P4 — Misconfigured CORS.** `allow_origins=["*"]` together with `allow_credentials=True` is a combination the browser rejects by specification, and it blocks any migration to cookie authentication.

**P5 — A weak authentication chain.** `python-jose` 3.3.0 is no longer actively maintained; there is no refresh token or revocation (only a 30-minute access token, so the session dies midway through a work session); `/auth/register` doesn't validate a minimum password length while the password change does require 6 characters; and there is no limit on attempts at `/auth/login`. In the Flutter app the token lives in `shared_preferences`, which on the web is `localStorage`: readable by any XSS.

**P6 — No rate limiting of its own.** The limiter protects Riot from us, but nothing protects the API from an abusive client. A `POST /snapshots/` in a loop fires off expensive jobs at no cost to the attacker.

#### Performance

**P7 — Synchronous ORM inside async endpoints.** The engine is `create_engine` + psycopg2 (pool of 5), and it is used from `async def` functions. Every query blocks the event loop, which is the same one that serves the concurrent Riot downloads. It is the structural cause of the latency spikes.

**P8 — N+1 in the persistence loops.** `stats_runner` and `match_history.update_history_cache` query `Match` by `match_id` once per game. With 200 games that is 200 extra *round trips*. `get_history_from_cache` also has no `LIMIT`, and the history refresh deletes all of the player's rows and reinserts them.

**P9 — A dashboard with no cache or contract.** `GET /snapshots/{id}/dashboard` doesn't declare a `response_model` (it falls outside the OpenAPI schema, precisely the most complex endpoint), recomputes the whole dashboard on every request and embeds the entire list of games in the response.

**P10 — Data Dragon cache on an ephemeral disk.** It is written to `./data/ddragon` and mounted as `StaticFiles`. On Render that disk disappears on every deploy, so the cache is born cold and hits Riot again.

**P11 — Impossible assets for the web.** The rank badges are PNGs of 300-670 KB each (`grandmaster_badge.png` 674 KB, `challenger_badge.png` 653 KB): almost 4 MB in badges alone. In a desktop app that is tolerated; on the web it is unacceptable.

#### Web-specific blockers

**P12 — No routing.** `_AuthGate` does a `switch` on the auth state and navigation is `Navigator.push`. There are no URLs, no deep links, no browser back button, nothing to share. A link to "that player's snapshot" doesn't exist.

**P13 — Flutter Web as a portfolio vehicle.** There is already a `frontend/docs/flutter_web_performance_baseline.md` measuring *janky frames* in the charts section, which confirms that the problem showed up in practice. Added to the CanvasKit bundle and the absence of SEO, it is the underlying reason to rewrite the client.

#### Operations

**P14 — A double source of truth for the schema.** `Base.metadata.create_all(bind=engine)` in the `lifespan` coexisting with Alembic: startup can create tables that no migration describes.

**P15 — No observability.** There is no structured logging, no request-id, no error capture, no metrics. `/health` returns a constant without checking the database.

**P16 — Running it locally is a journey.** There is no Dockerfile or `docker-compose`: you need Postgres installed, Python with a venv and the Flutter SDK. For whoever reviews your repo, that is pure friction.

**P17 — Naive `datetime.utcnow`** in `RankCutoff.fetched_at` (deprecated in Python 3.12 and a mix of *aware* and *naive* in the same database).

**P18 — The local folder isn't a git repo.** `C:\Users\<user>\Projects\YGG` contains no `.git` although there is a `.github/workflows`. Before starting you have to find the real repo (or initialise it and push it), because the whole plan assumes working with branches and PRs.

---

## 2. Target architecture

```
ygg/
├─ packages/ygg-core/          # Pure Python package: domain, Riot, metrics
│  ├─ src/ygg_core/
│  │  ├─ domain/               # Dataclasses: Match, Participant, Snapshot, Metrics
│  │  ├─ riot/                 # client, rate_limiter, routing, parsers
│  │  ├─ timeline/             # enrichment, dragon_setups, objective_vision, quests
│  │  ├─ metrics/              # aggregates, radar, benchmarks, semantic thresholds
│  │  ├─ store/                # DuckDB: game cache and analytical queries
│  │  └─ cli.py                # ygg fetch / ygg stats → JSON
│  └─ tests/
├─ apps/api/                   # FastAPI: HTTP, auth, persistence, jobs
│  ├─ app/{routers,schemas,db,auth,jobs}
│  └─ tests/
├─ apps/web/                   # React 19 + TS + Vite
│  └─ src/{routes,features,components,lib,styles}
├─ infra/
│  ├─ docker-compose.yml       # postgres + redis + api + worker + web
│  └─ Dockerfile.{api,web}
└─ docs/                       # architecture.md, adr/, metrics.md
```

**Guiding principle:** `ygg-core` imports nothing from FastAPI or SQLAlchemy. It receives data and returns domain objects and metrics. That allows testing it without a database, using it from the CLI, and having the API be a thin layer of HTTP + persistence. It is also the short, convincing answer to "tell me your project's architecture".

**The flow of an analysis, already corrected:**

```
POST /snapshots  ──▶  creates a job (with user_id) in Postgres  ──▶  enqueues in Redis
                                                                         │
   SSE /snapshots/jobs/{id}/stream  ◀── progress ──┐                ARQ worker
                                                    └──  ygg-core: Riot + timeline + metrics
                                                                         │
                                                              persists matches + participants
```

### Data layer

A decision taken after evaluating alternatives (SQLModel, Tortoise, Piccolo, bare asyncpg): **we stay with SQLAlchemy, but with the 2.0 and async API.** The current code uses the 1.x style of almost twenty years ago —`Column(Integer, primary_key=True)`, `db.query(Match).filter(...).first()`, a synchronous `Session`—, and that is where both the discomfort of writing it and the `DetachedInstanceError` commented in `snapshots.py` are born. The installed version (2.0.35) already allows something else:

```python
class MatchParticipant(Base):
    __tablename__ = "match_participants"
    id:         Mapped[int] = mapped_column(primary_key=True)
    match_id:   Mapped[str] = mapped_column(ForeignKey("matches.match_id"), index=True)
    puuid:      Mapped[str] = mapped_column(index=True)
    champion:   Mapped[str]
    cs_diff_14: Mapped[int | None]

stmt = select(MatchParticipant).where(MatchParticipant.puuid == puuid)
participants = (await session.scalars(stmt)).all()
```

Typing that mypy and the editor really understand, `select()` instead of `.query()`, and `AsyncSession`. Changing ORM would cost two days and leave a less employable stack: SQLAlchemy is the one that appears in job postings, and the only one with a truly mature migration system (Alembic).

**Three layers with separate responsibilities:**

| Layer | Tool | What it does |
|---|---|---|
| Transactional CRUD | SQLAlchemy 2.0 ORM + `AsyncSession` | Users, players, snapshots, jobs. The boring code where the ORM wins |
| Analytical queries | **Handwritten SQL** (`text()` or asyncpg directly) | Per-role aggregates, percentiles, time series, bulk `INSERT ... ON CONFLICT`. Where the ORM gets in the way and generates bad queries |
| Local analysis | **DuckDB** inside `ygg-core` | Columnar, aggregates over thousands of games in milliseconds, Parquet reading/writing, embedded with no server |

Postgres remains the application's database; DuckDB is the core's analytical engine, not a replacement. That separation between transactional and analytical storage is an architecture concept with weight in an interview, and handwritten SQL differentiates quite a bit more than knowing how to use an ORM.

The analytical queries go in versioned `.sql` files under `apps/api/app/queries/`, loaded by name and with a test of their own: they are reviewable in PRs and not buried in strings inside the Python code.

---

## 3. Phases

Each phase ends in a mergeable branch, with green tests and CI passing. The order isn't negotiable on one point: **Phase 2 goes before the frontend**, because rewriting the UI on top of a data model that attributes stats to the wrong player is wasted work.

### Phase 0 — Safety net (day 1)

| Task | Detail |
|---|---|
| Repo | **A single repo, the one that already exists, renamed to `ygg`** — the history since the TFG is part of the portfolio and two repos would break the generation of TS types from the OpenAPI. Find the remote or `git init` + a first commit with the current code. Protected `main` branch, work on `feat/*` branches. |
| Preserve the TFG | `git tag -a v1.0-tfg` + a GitHub release before touching anything. The delivered state stays consultable forever without needing a second repository. |
| Secrets audit | `gitleaks detect` / `trufflehog git file://.` over the whole history **before making the repo public**. If the Riot key, the JWT `SECRET_KEY` or Supabase's *service key* were ever committed, rotate them and evaluate `git filter-repo`. |
| Monorepo | Move to the structure above with `git mv` (don't copy and delete, so that `git log --follow` follows the trail). Only move: without touching code yet. |
| Cleanup | The Flutter client leaves `main` when the React one works (Phase 5); it stays preserved at the `v1.0-tfg` tag. Two frontends in the active repo read as clutter. |
| Docker | `docker-compose.yml` with postgres + redis; `make up` brings everything up. |
| CI | Rewrite the workflow: lint → backend tests → web tests → build. The desktop/APK build is kept, but stops being the only thing. |
| Quality | `ruff` + `mypy` in gradual mode over `ygg-core`, `pre-commit` with both. |
| Config | `pydantic-settings` with a per-environment `Settings`; a complete `.env.example`; document every variable. |
| Quick wins | Remove `Base.metadata.create_all` (P14) · CORS with an explicit list of origins (P4) · `datetime.now(timezone.utc)` in `RankCutoff` (P17) · add `LIMIT` to `get_history_from_cache` (P8). |

**Done when:** `git clone && make up` starts the API with a database and Redis, and CI runs the ~75 KB of tests nobody runs today.

**For the CV:** "A monorepo with CI on GitHub Actions, a reproducible environment with Docker Compose and verified static typing."

### Phase 1 — Extract `ygg-core` (days 2-4)

Move, don't rewrite: `riot_client.py`, `riot_rate_limiter.py`, `role_quest_parser.py`, `ddragon_client.py` and the calculation part of `dashboard_service.py` go to `packages/ygg-core`, and their SQLAlchemy dependencies are removed.

- Define domain dataclasses (`MatchData`, `ParticipantStats`, `TimelineMetrics`, `RadarProfile`) that today are implicit in the ORM model.
- The Riot client stops returning ORM `Match` objects: it returns domain. The domain→ORM mapping lives in `apps/api`.
- `dashboard_service` is split: the calculation (radar, per-role ceilings, `check_status`, benchmarks) goes to the core; data loading stays in the API.
- A minimal CLI: `ygg fetch <riot-id> --from --to --json` and `ygg stats <file.json>`. It is your debugging tool and also makes the package demonstrable without starting anything.
- **Local cache and analytics with DuckDB** in `ygg_core/store/`: downloaded games are stored in Parquet and queried with columnar SQL. You iterate on the metrics without requesting anything from Riot again and without spending quota, and an aggregate over thousands of games takes milliseconds. The radar formulas and the semantic thresholds are validated here before touching the API.
- Core tests **without a database**, with JSON fixtures of anonymised real games.

**Done when:** `pytest packages/ygg-core` passes without Postgres running and the API imports the core instead of having the logic inside.

**For the CV:** "I extracted the analysis engine into an independent, testable Python package, with its own CLI and DuckDB as an embedded analytical engine; the API became a transport layer."

### Phase 2 — Fix the data model (days 5-7)

The central change of the whole plan: split the wide ~70-column table.

```
matches                    # the game: match_id, creation_time, duration, patch, queue_id
match_participants         # one participant: (match_id, puuid) UNIQUE
                           #   champion, role, kills/deaths/assists, cs, gold, damage,
                           #   diffs 8/14/25, solo_kills, quest_*, death_events, ward_events
match_snapshots            # N:M snapshot ↔ participant (not ↔ game)
```

- A three-step Alembic migration: create the new tables → copy data (`match_data` → `matches` + `match_participants`, using the existing `player_role`/`champion`) → drop the old one. With a count-verification script before the `drop`.
- **Rewrite the models in SQLAlchemy 2.0 style** taking advantage of the fact that you are going to touch them anyway: `Mapped[type]` + `mapped_column()` instead of `Column()`, and `select()` instead of `db.query()` in all the CRUD. With this mypy starts catching type errors in queries, and the class of `DetachedInstanceError` failures disappears.
- **Decide what to do with the JSONs.** `death_events`, `ward_events` and `dragon_setups` are today JSON columns. Keeping them as `JSONB` is fine if you only read them whole to draw the heat map; if you want to query them (for example "deaths at minute 8 in the blue side's river"), they need their own `match_events (match_id, puuid, type, minute, x, y)` table with an index. My recommendation: `JSONB` now, and an events table only if you get to the pattern-detection improvement.
- Remove `copy_timeline_fields` as a mechanism for reuse between players: now each player has their own participant row and the enriched timeline is shared at the game level.
- Add `user_id` to `jobs` and check ownership in the status endpoint (**P2**).
- Indexes: `(puuid, creation_time DESC)` for history, `(snapshot_id)` on the N:M, `(match_id)` on participants.
- Batch persistence: `INSERT ... ON CONFLICT DO UPDATE` instead of the per-game `db.query` loop (**P8**).
- An explicit regression test: two registered players, the same game, each sees their own stats. That test is the proof that **P1** is closed.

**Done when:** the test of the two players in the same game passes, and the existing data survives the migration.

**For the CV:** This is your best technical story. "I detected that the data model collapsed the stats of several players in the same game; I redesigned the schema separating match and participant, with a verified production data migration and a regression test that pins the behaviour."

### Phase 3 — A hardened API (days 8-10)

| Area | Change |
|---|---|
| Real async | `create_async_engine` + `asyncpg` + `AsyncSession`; every endpoint `async`. Goodbye to blocking the event loop (**P7**). A pool sized according to the hosting plan, not the default 5. |
| Analytical SQL | The aggregate queries leave the ORM for `.sql` files in `app/queries/`, run with `text()` and with a test of their own that compares their result against `ygg-core`'s calculation. The bulk `INSERT ... ON CONFLICT` go there too. |
| Auth | PyJWT instead of python-jose. A short access token (15 min) + a **refresh token in an `httpOnly`, `Secure`, `SameSite=Lax` cookie** with rotation and a revocation table. The frontend stops touching the token (**P5**). |
| Passwords | A single shared policy: a minimum of 10 characters, validated on sign-up and on change. |
| Rate limiting | `slowapi` or a custom middleware with Redis: global per IP, and a strict limit on `/auth/login` (**P6**) and on `POST /snapshots/`. |
| Contracts | `response_model` on **all** endpoints, including the dashboard (**P9**). Pagination on history and listings. |
| Cache | The dashboard in Redis with the key `snapshot_id + schema version`, invalidated when games are added to the snapshot. |
| Data Dragon | A cache in Redis + direct URLs to Riot's CDN, removing the `StaticFiles` over an ephemeral disk (**P10**). |
| Observability | `structlog` with JSON and request-id, Sentry for errors, `/health` checking Postgres and Redis, `/metrics` in Prometheus format (**P15**). |
| OpenAPI | A complete, clean schema; it becomes the source of the frontend's TypeScript types. |

**Done when:** the OpenAPI describes 100% of the API, `ab`/`k6` show stable latency under concurrency, and `/health` really fails if Postgres goes down.

**For the CV:** "I migrated to async SQLAlchemy 2.0 with the analytical queries in handwritten SQL, replaced the JWT in localStorage with refresh tokens in an httpOnly cookie with rotation, and added rate limiting, a Redis cache and structured logging with per-request traceability."

### Phase 4 — Jobs outside the process (days 11-12)

- A worker with **ARQ** (async, fits the stack; Celery is heavier and adds nothing here) over Redis.
- `POST /snapshots/` enqueues and returns a `job_id`; the worker runs `ygg-core` and writes progress to Redis + Postgres.
- Retries with backoff, a *heartbeat*, and recovery of orphan jobs when the worker starts: if a job was left `processing` with no heartbeat, it is marked `failed` and can be retried (**P3**).
- **Progress over SSE** (`GET /snapshots/jobs/{id}/stream`) replacing the polling every 2 s. SSE and not WebSockets: the flow is unidirectional, it reconnects by itself and works over normal HTTP.
- Idempotency: enqueuing the same (player, range) twice reuses the running job.

**Done when:** you kill the API container midway through an analysis, the job survives and the browser keeps receiving progress.

**For the CV:** "I moved processing to a worker with a Redis queue, with retries, recovery of orphan jobs and real-time progress via Server-Sent Events."

### Phase 5 — React frontend (days 13-19)

**Stack**

| Piece | Choice | Why |
|---|---|---|
| Base | React 19 + TypeScript (`strict`) + Vite | What the junior job postings ask for |
| Routing | React Router 7 with nested routes and `lazy` | Solves **P12**: real URLs and shareable links |
| Data | TanStack Query | Caching, retries, invalidation and loading states without writing them by hand |
| Types | `openapi-typescript` + `openapi-fetch` from the API's OpenAPI | A generated typed client: if you change the backend, the front end stops compiling |
| Styles | Tailwind v4 with the Hextech tokens as CSS variables | The palette is already documented in HSL |
| Components | shadcn/ui (Radix) | Accessibility out of the box in dialogs, tooltips and menus |
| Charts | Recharts for radar/lines/bars; custom SVG for the heat map | Equivalents of `fl_chart` with better DOM performance |
| Tables | TanStack Table + virtualisation | The history and the admin panel are large tables |
| Tests | Vitest + Testing Library; Playwright for the critical flow | |

**Route map**

```
/login                                  public
/players                                players table
/players/:id                            detail: history, champions, rank
/players/:id/snapshots/:snapshotId      snapshot dashboard (radar, metrics, games)
/players/:id/snapshots/compare?a=&b=    compare two snapshots
/cutoffs                                rank cutoffs
/admin/(users|players|stats)            admin role only
/s/:publicToken                         shareable public snapshot (optional, Phase 6)
```

All the visible state —open snapshot, filtered role, selected metric, tab— goes in the URL as *search params*. It is what turns the app into something you can show with a link.

**Order of work**

1. **Days 13-14 — Foundations.** Vite, Tailwind with tokens, layout, router, generated client, an auth layer with a cookie and silent refresh, `ProtectedRoute`, a login form with validation (`react-hook-form` + `zod`).
2. **Day 15 — Players.** A table with sorting and virtualisation, adding a player with validation against Riot, rank badges, role chips, rank refresh.
3. **Days 16-17 — Snapshot dashboard.** The star screen: a radar with datasets (player / challenger / compared account), metric cards coloured by the backend's semantic `status` —the helper in `docs/design/color-guide.md` translates as-is to TypeScript—, a games table with item and rune tooltips, and a heat map of deaths and wards in SVG over the minimap.
4. **Day 18 — Snapshot creation and admin.** A date-range selector, a progress bar fed by SSE with reconnection, and an admin panel (users, players, global statistics) split into small components: the 49 KB of `admin_users.dart` aren't replicated in a single file.
5. **Day 19 — Web polish.** Loading states with *skeletons*, empty and error states with retry, `prefers-reduced-motion`, keyboard navigation, `aria` on the charts with an alternative data table, and real responsiveness from 360 px to 2560 px.

**Performance budget** (you measure it and put it in the README):

- Initial JS < 200 KB compressed; routes in separate *chunks*.
- LCP < 2.0 s and CLS < 0.05 on simulated 4G.
- Lighthouse ≥ 95 in Performance, Accessibility and Best Practices.
- The rank badges go to WebP/AVIF with an SVG sprite for the roles: from ~4 MB to under 200 KB (**P11**).

**Done when:** the four screens work against the real API, Playwright covers login → create snapshot → see dashboard, and the performance budget is met.

**For the CV:** "I rewrote the client in React 19 + TypeScript with an HTTP client generated from OpenAPI, server state with TanStack Query, deep routes and a performance budget verified with Lighthouse."

### Phase 6 — Deploy and public demo (days 20-22)

**Infrastructure**

| Component | Where | Notes |
|---|---|---|
| Web | Vercel or Cloudflare Pages | Static + cache headers and CSP |
| API + worker | Fly.io or Railway | Render free puts the instance to sleep; if you stay, pay for the plan that doesn't sleep or accept the cold start |
| Postgres | Supabase (you already use it) | |
| Redis | Upstash | The free plan is enough for the queue and cache |

- A domain of your own (`ygg.yourdomain.dev`) with HTTPS. A domain of your own on a CV shows.
- A strict CSP, `Strict-Transport-Security`, `X-Content-Type-Options`, `Referrer-Policy`.
- A deploy pipeline: merge to `main` → tests → migrations → deploy API → deploy web, with a documented *rollback*.

**Riot key**

The development key expires every 24 hours, so the demo can't depend on it:

1. Request the **Personal API Key** on Riot's developer portal: it requires describing the project, having a working public URL and complying with its usage policy (no monetisation, correct attribution). Approval takes days or weeks, so **this step is started on day 1, not in Phase 6**.
2. Until it arrives (and as a permanent safety net if it is revoked): **demo mode**. A database seeded with anonymised real snapshots, a read-only `demo` user with credentials visible on the landing page, and a `DEMO_MODE` flag that disables the calls to Riot by serving the seeded data. The CV's link never goes down in the middle of an interview.
3. Quota and cost: with the personal key, limit to N analyses per user and day so as not to burn the quota, aggressively reusing the game cache you already have.

**Done when:** a public link opens the app, the demo user logs in and sees a complete dashboard, and the cold start doesn't exceed 3 s.

### Phase 7 — Packaging for the portfolio (days 23-25)

This phase is the one that turns technical work into interviews. Don't cut it.

1. **The README as a showcase:** a screenshot or GIF at the top, a link to the demo with credentials, what problem it solves and for whom, an architecture diagram, technical decisions with their why, and `docker compose up` as the only instruction to bring it up.
2. **`docs/adr/`:** five or six decisions of one page each (why separate match and participant, why SQLAlchemy 2.0 instead of SQLModel or Tortoise and why handwritten SQL in the analytics, why DuckDB in the core alongside Postgres, why ARQ and not Celery, why SSE and not WebSockets, why an httpOnly cookie and not localStorage). A junior who documents decisions stands out immediately.
3. **`docs/metrics.md` with measured before/after:** dashboard p95 latency, analysis time for 100 games, initial JS, Lighthouse, test coverage. Concrete numbers, not adjectives.
4. **A 60-90 s video** with no audio, with subtitles: login → add a player → create a snapshot with live progress → dashboard → compare. It goes in the README and on LinkedIn.
5. **The CV entry**, in two lines and with figures:

   > **YGG — A League of Legends performance analysis platform** · React 19, TypeScript, FastAPI, SQLAlchemy 2.0 async, PostgreSQL, DuckDB, Redis, Docker · [demo] [code]
   > Game analysis over the Riot API with timeline enrichment (gold/CS/XP differentials, objective vision control, heat maps). I redesigned the data schema to support several players per game, moved processing to a worker with a Redis queue and SSE progress, and rewrote the client in React with an HTTP client generated from OpenAPI. Lighthouse 95+, dashboard p95 under X ms.

6. **Prepare three stories** for the interview, each with context → problem → decision → result: the data-model bug, the global rate limiter against Riot's 429s, and the migration of in-process jobs to an external queue.

---

## 4. Product improvements (optional, by value/effort)

If there is time left or you want to continue afterwards. The first on the list is what impresses most for how little it costs.

| Improvement | Effort | Why it is worth it |
|---|---|---|
| **Compare two snapshots of the same player** (evolution between dates) | Low | The backend already computes everything; it is a route and a radar with two datasets. And it is *the* question a coach asks |
| **A shareable public snapshot** (`/s/:token`, read-only) | Low | It makes the project virally demonstrable: you paste a link in the CV that opens real data without a login |
| **Temporal trend of metrics** (a per-game series with a moving average) | Medium | It turns still photos into progression; it is what makes the tool useful |
| **A PDF report of the snapshot** | Medium | A tangible deliverable for a team; and it makes you touch document generation |
| **Team view** (5 players, strengths and gaps by role) | High | The natural step from individual to competitive scouting — and it is only possible **after** fixing P1 |
| **Pattern detection** (repeated deaths in the same zone and minute) | High | It uses the `death_events` with coordinates that you already store; it is real analysis |

---

## 5. Risks

| Risk | Mitigation |
|---|---|
| Riot's Personal API Key takes long or is denied | Request it on day 1 and build the demo mode with seeded data as the guaranteed path |
| The Phase 2 data migration corrupts what exists | A three-step migration, a count-verification script before the `drop`, a prior *dump* of the database |
| The frontend rewrite drags on | Freeze the scope at the 4 current screens; the product improvements are explicitly later |
| Riot changes the game format (patches, season 27) | Versioned JSON fixtures in `ygg-core` and parsing tolerant of missing fields (you already do it with the Role Quests) |
| Running out of API quota during the demo | Aggressive caching, a per-user-per-day limit, and `DEMO_MODE` serving seeded data |
| Abandoning midway and being left with a repo worse than the current one | Each phase ends in a mergeable branch with green tests: if you stop, you stop in a publishable state |

---

## 6. First concrete actions

To start today, in this order:

1. **Request Riot's Personal API Key.** It is the only thing with external latency; every day you take to ask for it you lose at the end.
2. **Find the git repository.** The local folder has no `.git` despite having GitHub workflows: confirm where the remote is, or initialise it and push it.
3. **Dump the production database** to a local file. It is Phase 2's safety net and you need it before touching anything.
4. **Create the `feat/monorepo` branch** and execute Phase 0.
5. **Measure the baseline before changing anything:** dashboard p95, analysis time for 100 games, the current web bundle size. Without these numbers, Phase 7's "after" means nothing.
