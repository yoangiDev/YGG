# Deployment and public demo

> **Status: planned, not carried out.** The configuration in this document (Vercel, Fly.io, Supabase, Upstash) is in the
> repository and the deployment flow is manual (`workflow_dispatch`), but YGG **is not deployed**. After public replay
> access closed in patch 16.20 the API needs real CPU to decode replays, so the hosting has to be rethought. What follows is
> still valid for the read-only demo.

Guide to Phase 6 of the [original plan](history/plan-web.md). The configuration is in the repository; **you set up the
accounts, the secrets, the domain and the first deployment** (none of this runs by itself until you configure the
`production` environment on GitHub).

## Architecture

| Piece | Where | Configuration |
|---|---|---|
| Web (static) | Vercel | [`apps/web/vercel.json`](../apps/web/vercel.json): SPA, immutable cache for `/assets`, CSP, HSTS |
| API | Fly.io, app `ygg-api` | [`infra/fly.api.toml`](../infra/fly.api.toml): migrations as the `release_command`, 1 machine always on |
| Worker | Fly.io, app `ygg-worker` | [`infra/fly.worker.toml`](../infra/fly.worker.toml): `arq app.jobs.worker.WorkerSettings` |
| Postgres | Supabase | `DATABASE_URL` with `?sslmode=require` |
| Redis | Upstash | `REDIS_URL` with `rediss://` |
| Pipeline | GitHub Actions | [`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml): API → worker → web |

### Why a domain of your own is needed

The refresh token travels in an `httpOnly; SameSite=Lax; Path=/auth` cookie. The browser only sends it if the web app and
the API are on the same *site* (the same registrable domain):

- ✅ `ygg.yourdomain.dev` (Vercel) + `api.ygg.yourdomain.dev` (Fly)
- ❌ `ygg.vercel.app` + `ygg-api.fly.dev`: they are different sites and the session would be lost on reload.

Replace `ygg.example.dev` in three places: `CORS_ORIGINS` in `infra/fly.api.toml`, `connect-src` of the CSP in
`apps/web/vercel.json` and the `API_URL` variable of the GitHub environment.

## Setup (once)

1. **Database and Redis.** Create the Supabase project and the Upstash database. Note down `DATABASE_URL` and
   `REDIS_URL`.
2. **Fly.io.**
   ```bash
   flyctl apps create ygg-api
   flyctl apps create ygg-worker
   flyctl secrets set -a ygg-api    DATABASE_URL=... REDIS_URL=... SECRET_KEY=... RIOT_API_KEY=...
   flyctl secrets set -a ygg-worker DATABASE_URL=... REDIS_URL=... SECRET_KEY=... RIOT_API_KEY=...
   flyctl certs add -a ygg-api api.ygg.yourdomain.dev
   ```
   `SECRET_KEY` must be at least 32 bytes (the API won't start in production with less):
   `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
3. **Vercel.** Import the repo with *Root Directory* `apps/web`, add the domain `ygg.yourdomain.dev` and set
   `VITE_API_URL=https://api.ygg.yourdomain.dev`.
4. **GitHub.** Create the `production` environment with:
   - secrets: `FLY_API_TOKEN` (`flyctl tokens create deploy`), `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`
   - variables: `API_URL`, and for the demo `DEMO_EMAIL` and `DEMO_PASSWORD`

   Add a manual approval rule to the environment if you want to review each deployment.
5. **First deployment.** Run *Deploy* with `workflow_dispatch` and check
   `https://api.ygg.yourdomain.dev/health` (Postgres and Redis `ok`).

## Demo mode

Riot's development key expires every 24 h, so a demo for a CV can't depend on it.

- `DEMO_MODE=true` on `ygg-api` makes the API **read-only**: it rejects with a 403 any write except login, refresh and
  logout, and any read that would call Riot (`sync`, `live`, `refresh`, `compare_*`). The history and the rank cutoffs
  are always served from the database. Implementation: `DemoModeMiddleware` in `app/core/middleware.py`.
- The account and its data are seeded with an idempotent script (synthetic data with the exact shape of the real data;
  the analysis and the dashboard are the production code):
  ```bash
  flyctl ssh console -a ygg-api -C "sh -c 'DEMO_PASSWORD=... python scripts/seed_demo.py'"
  ```
- With `VITE_DEMO_EMAIL` and `VITE_DEMO_PASSWORD` set, the login shows the credentials and an "Enter the demo" button,
  and the app shows a read-only notice.

Use a database of its own for the demo: `DEMO_MODE` blocks the writes of **all** the users of that API, not just those of
the demo account.

## Rollback

- **API and worker.** `flyctl releases -a ygg-api` lists the versions with their image; to go back:
  `flyctl deploy -a ygg-api --config infra/fly.api.toml --image registry.fly.io/ygg-api:deployment-<id>` (and the same
  for `ygg-worker`).
- **Web.** In Vercel, *Deployments* → previous version → *Promote to Production* (or `vercel rollback`).
- **Migrations.** They are written in *expand/contract* style: each migration is compatible with the previous version's
  code, so rolling back the API doesn't need to touch the schema. Only if a specific migration has to be reverted:
  `flyctl ssh console -a ygg-api -C "alembic downgrade -1"`.

## Riot key

1. Request the **Personal API Key** at <https://developer.riotgames.com>: a project description, a working public URL (the
   demo will do) and compliance with the policy (no monetisation and with Riot's legal notice, which already appears on
   the login).
2. When it arrives, change it in both apps: `flyctl secrets set -a ygg-api RIOT_API_KEY=...` (and on `ygg-worker`). Fly
   restarts the machines with the new secret.
3. Adjust `RATE_LIMIT_SNAPSHOTS_PER_HOUR` so as not to exhaust the daily quota.

## Checks after deploying

```bash
curl -fsS https://api.ygg.yourdomain.dev/health
curl -fsSI https://ygg.yourdomain.dev | grep -i -E "content-security-policy|strict-transport"
E2E_REAL_API=1 E2E_BASE_URL=https://ygg.yourdomain.dev npx playwright test real-api   # from apps/web, outside the demo
```

The cold-start target (< 3 s) is met by keeping `min_machines_running = 1`; measure it with
`curl -w "%{time_total}\n" -o /dev/null -s https://api.ygg.yourdomain.dev/health/live` after a
`flyctl machine restart`.
