# Metrics

Measured numbers, with how they were measured. Where there is no measurement, it says so, and an adjective doesn't take
its place.

**Two measurements, taken on different dates:**

- **October 2026** (after the redesign and the game analysis): tests, coverage and initial JS size. They are repeated
  with the commands in the *Tests* and *Size* sections.
- **September 2026**, branch `feat/web`, locally (Windows 11, embedded Postgres, in-memory Redis): performance (LCP,
  CLS and API latency). **They predate the web redesign and are due to be repeated**; see the warning in each section.

Production figures are pending the deployment (see [`deploy.md`](deploy.md)).

## Summary

| Metric | Before | Now | Target |
|---|---|---|---|
| Static assets (rank badges, role icons, font) | 4,170 KB | **121 KB** | < 200 KB |
| Initial web JS (gzip) | — (Flutter Web, unmeasured) | **125.7 KB** (Oct 2026) | < 200 KB |
| Login LCP (slow 4G, 4x CPU) | — | **1.77 s** (Sep 2026) | < 2.0 s |
| Player list LCP | — | **1.96 s** | < 2.0 s |
| Snapshot dashboard LCP | — | **2.34 s** ⚠️ | < 2.0 s |
| CLS (all three screens) | — | **≤ 0.001** | < 0.05 |
| Dashboard p95, warm cache (local) | — | **4.0 ms** | — |
| Dashboard p95, no cache (local) | — | **11.4 ms** | — |
| `ygg-core` coverage | no CI | **92%** (201 tests, Oct 2026) | — |
| API coverage | no CI | **81%** (191 tests, Oct 2026) | — |
| Lighthouse | — | unmeasured | ≥ 95 |

## Web

### Size

`npm run build && node scripts/bundle-budget.mjs` (in CI, it fails above 200 KB). It counts the entry script and the
`modulepreload`s of `index.html`, gzipped at level 9.

| | Initial JS (gzip) |
|---|---|
| First version of the React client | 156.2 KB |
| With the app shell, dialogs, charts and table in separate chunks | **126.1 KB** |
| After the redesign and the game analysis (October 2026) | **125.7 KB** |

Largest deferred chunks (October 2026, gzip): Recharts (89 KB, only where there are charts), the stats-by-rank screen
(56 KB), zod + react-hook-form (33 KB, when a form opens), Radix components (32 KB), and the replay analysis and
games-table views (18-21 KB each).

The assets come from `apps/web/scripts/optimize_assets.py`: rank badges in WebP at twice the largest displayed size and
DM Sans in WOFF2 with only the Latin glyphs. From 4,170 KB to 121 KB (**P11**).

### Lab Web Vitals

> ⚠️ Measured in September 2026, **before the redesign** of the web app and of the game-analysis screen. They must be
> repeated before being quoted as current.

`PERF=1 npm run test:e2e -- perf` ([`e2e/perf.spec.ts`](../apps/web/e2e/perf.spec.ts)):

- A production build served with compression and caching like a CDN (`scripts/serve-dist.mjs`).
- Chrome with Lighthouse's slow-4G profile: 150 ms RTT, 1.6 Mbps down, 750 kbps up and a 4x slower CPU. A cold load (no
  cache) of each route directly by URL, three times, median.
- Mocked API (the client is what is measured). The session is restored with the refresh cookie, as after a reload.

| Screen | First version | After splitting chunks | CLS |
|---|---|---|---|
| `/login` | 1.91 s | **1.77 s** | 0.001 |
| `/players` | 2.08 s | **1.96 s** | 0.001 |
| `/players/1/snapshots/42` | 3.08 s | **2.34 s** | 0.001 |

The resource waterfall that the test records showed the bottleneck: every page waited to download **all** its
dependencies before requesting its data. The dashboard didn't request the snapshot until it had Recharts (95 KB) and the
games table; the player list waited for zod because of a closed dialog. Splitting them moved the data requests forward by
0.4 to 0.7 s.

⚠️ **The dashboard is still 340 ms above target** in this profile. What remains in its way: the Radix chunk (tabs and
dialogs), the session's two round trips (refresh + `/auth/me`) and rendering 24 games with the CPU slowed down. Possible
next steps: tabs without Radix, requesting `/auth/me` in parallel with the first piece of data, and prerendering the
cards' skeleton.

**Lighthouse has not been run** (it isn't among the dependencies and there is no public URL yet). After deployment:
`npx lighthouse https://ygg.yourdomain.dev --preset=desktop` and on mobile.

## API

`python scripts/bench_api.py --email demo@ygg.gg --password …` against the local API with `DEMO_MODE=true` and the data
from `scripts/seed_demo.py` (3 players, 6 snapshots of 22 and 26 games). Sequential requests from the same machine, with
rate limiting on.

| Endpoint | n | p50 | p95 | max |
|---|---|---|---|---|
| Dashboard with no cache (built from Postgres) | 6 | 9.3 ms | 11.4 ms | 11.5 ms |
| Dashboard with cache | 80 | 3.2 ms | 4.0 ms | 5.0 ms |
| Games of a snapshot (page of 50) | 80 | 7.0 ms | 8.1 ms | 37.0 ms |
| Player list | 80 | 3.3 ms | 4.1 ms | 4.2 ms |

Limits of this measurement: a local database and Redis (no network in between), small snapshots and a single
connection. It is useful for comparing versions, not as production latency. The real p95 will be measured against
Fly.io + Supabase + Upstash.

## Game analysis

**Not measured end to end**: it needs a live Riot key. What can be said with data:

- Analysing N new games is `1 + 2N` requests to Riot (the id list, the match and the timeline). With the development
  key (100 requests every 2 minutes), 100 new games is 201 requests: the global limiter spreads them over **at least ~4
  minutes**, and the time is set by the quota, not by processing.
- Games already stored **for that player** aren't downloaded again: repeating or overlapping a period only requests the
  new ones.
- Saving an analysis is a few `INSERT … ON CONFLICT` statements in batches of 500 rows, regardless of the number of
  games; before, it was one query per game (**P8**).

## Tests

| Suite | Tests | Coverage | Where it runs |
|---|---|---|---|
| `ygg-core` (pytest, strict mypy) | 201 | 92% | CI, no services |
| API (pytest against Postgres and Redis) | 191 | 81% | CI with services |
| Web unit tests (Vitest + Testing Library) | 111 | 47% of lines | CI |
| Web e2e against a mocked API (Playwright) | 12 | — | CI |
| Web e2e against the real API | 3 | — | Manual (`E2E_REAL_API=1`) |

October 2026. The API coverage was measured without the 8 tests that call Riot's CDN (`test_ddragon.py` and
`test_runes.py`), which need network access; in CI they all run.

The web's unit coverage is low on purpose: the unit tests cover the riskiest logic (the HTTP client and session refresh,
the SSE parser and job tracking, forms, colours and calculations) and the screens are tested end to end in a browser,
which V8 doesn't count.

Commands: `pytest --cov=ygg_core` (core), `pytest --cov=app` (API), `npm run test:coverage` (web).
