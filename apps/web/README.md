# apps/web

YGG's client: a React 19 and TypeScript SPA, built with Vite. It consumes the API through a typed client generated from
its OpenAPI contract. The interface is in English.

## Running

```bash
npm ci
cp .env.example .env     # VITE_API_URL=http://localhost:8000
npm run dev              # http://localhost:5173
```

The web app and the API have to share a *site* (the same registrable domain) for the refresh cookie to travel:
`localhost:5173` and `localhost:8000` do.

## Scripts

| Command | What it does |
|---|---|
| `npm run dev` / `npm run build` | Dev server / production build (`tsc -b` and Vite) |
| `npm run lint` | ESLint, with the React Hooks and React Compiler rules |
| `npm test` | 111 unit tests (Vitest and Testing Library) |
| `npm run test:e2e` | User flows in Chromium against the mocked API (`e2e/mockApi.ts`); no backend needed |
| `npm run api:types` | Regenerates `src/lib/api/schema.d.ts` from `../api/openapi.json` |
| `node scripts/bundle-budget.mjs` | Fails if the initial JS exceeds 200 KB gzip (after `npm run build`) |

With `PERF=1` the `perf` e2e measures LCP with Lighthouse's slow-4G profile; with `SCREENSHOTS=1`, the screenshot one
(`make screenshots` from the root writes them to `docs/img`).

## Layout

```
src/
  app/          router (one chunk per screen), layout, header and menus
  components/   base UI (Button, Card, Overlay…) and charts (radar, trend, heat map)
  features/     one folder per area
    auth/       session: in-memory access token and a silent refresh on a 401
    players/    account, linking and verifying, history, game detail
    games/      game analysis: moments, map, coach cards and replay upload
    snapshots/  dashboard, comparison, WPA timeline and background jobs
    ranks/      stats by rank
    cutoffs/    LP cutoffs
    admin/      admin panel
    legal/      terms, privacy and cookies
  lib/          API client, cache keys, SSE, formatting, palette, pure tested utilities
e2e/            Playwright: fixtures, mocked API and flows
scripts/        JS budget, a dist server with compression and asset optimisation
```

## Decisions

- **Generated contract.** `src/lib/api/schema.d.ts` comes from `openapi.json`; CI regenerates it and fails on any
  difference.
- **Data.** TanStack Query with hierarchical keys (`src/lib/queryKeys.ts`); a screen's state (tab, filter, comparison)
  lives in the URL.
- **Performance.** Every route is a chunk (`route.lazy`), and Recharts, the table and the dialogs load on use. Figures
  and method in [`docs/metrics.md`](../../docs/metrics.md).
- **Design.** Dark, square corners and a single accent. Reference in [`docs/design/`](../../docs/design).
- **Accessibility.** Visible focus, charts described for screen readers and `prefers-reduced-motion`.
