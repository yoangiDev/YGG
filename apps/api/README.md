# apps/api

YGG's API: async FastAPI, a job worker and replay analysis. It uses [`ygg-core`](../../packages/ygg-core) as its engine.
The overall picture is in [`docs/architecture.md`](../../docs/architecture.md).

## Running

```bash
pip install -e ../../packages/ygg-core -r requirements.txt   # + -r requirements-replays.txt to analyse replays
cp .env.example .env                                          # every variable is documented inside
alembic upgrade head
uvicorn main:app --reload                                     # http://localhost:8000/docs
```

With `REDIS_URL=memory://` you need neither Redis nor a worker: the queue runs in the process itself
(`InlineJobQueue`). With Redis, the worker is `arq app.jobs.worker.WorkerSettings`.

Demo data (the `demo@ygg.gg` account, one synthetic player, two snapshots and 48 games):

```bash
DEMO_PASSWORD=demo-password-123 python scripts/seed_demo.py
```

## Layout

```
main.py            the application: middlewares, routers and startup
app/
  core/            configuration, logging, ASGI middlewares, rate limiting, Redis, Sentry
  auth/            sign-up, login, short-lived JWTs and refresh tokens rotated in an httpOnly cookie
  routers/         players, matches, snapshots, games, league, ddragon, admin, health
  schemas/         Pydantic input and output models (every route declares a response_model)
  service/         business logic: dashboard and its cache, rank, Claude's review, replay analysis…
  crud/, queries/  data access: batch upserts and handwritten SQL for analytics
  db/models/       SQLAlchemy 2.0 models
  jobs/            queue (ARQ or inline), worker, heartbeat and progress in Redis
alembic/versions/  24 migrations: Alembic is the only owner of the schema
scripts/           demo seeding, OpenAPI export, benchmark, ladder harvest and maintenance
tests/             191 tests against real Postgres and Redis
openapi.json       the versioned contract: the web client is generated from it, and CI checks they don't drift
```

## Endpoints

56 operations in `/docs`. The ones that matter:

| Group | What it does |
|---|---|
| `/auth/*` | Sign-up, login, rotated refresh, logout, profile |
| `/players/*` | Link a Riot account, verify it with the profile icon, rank, LP history |
| `/matches/*` | History, the detail of a game with its ten players, the player's champions |
| `/snapshots/*` | Create a snapshot (a background job), its progress over SSE, the dashboard and comparison |
| `/games/*` | Upload the replay of a game and query its analysis and your quota |
| `/league/*`, `/ddragon/*` | Grandmaster and Challenger cutoffs, static game data |
| `/admin/*` | Users, roles and global statistics |

## Tests

```bash
DATABASE_URL=postgresql://ygg:ygg@localhost:5432/ygg_test SECRET_KEY=test pytest -q
```

They need Postgres and Redis (`docker compose -f ../../infra/docker-compose.yml up -d postgres redis`). The tests in
`test_ddragon.py` and `test_runes.py` call Riot's CDN and need network access.

To regenerate the contract after changing the API: `python scripts/export_openapi.py` and, in `apps/web`,
`npm run api:types`.
