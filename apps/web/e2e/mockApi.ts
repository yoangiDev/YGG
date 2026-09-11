import { expect, type Page, type Route } from "@playwright/test";

import * as data from "./fixtures";

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

function page<T>(items: T[], url: URL) {
  const limit = Number(url.searchParams.get("limit") ?? 50);
  const offset = Number(url.searchParams.get("offset") ?? 0);
  return { items: items.slice(offset, offset + limit), total: items.length, limit, offset };
}

export interface MockOptions {
  /** Inicia sesión como administrador. */
  admin?: boolean;
  /** Deja pasar las imágenes del CDN de Riot (para capturas); por defecto se bloquean. */
  allowCdn?: boolean;
  /** Sesión ya iniciada (cookie de refresh válida), para abrir rutas profundas directamente. */
  signedIn?: boolean;
}

/**
 * API simulada con page.route. La web se construye con VITE_API_URL=/api, así
 * que todas las llamadas son del mismo origen y no hay CORS de por medio.
 */
export async function mockApi(target: Page, { admin = false, allowCdn = false, signedIn = false }: MockOptions = {}) {
  let session = signedIn;
  const me = admin ? data.adminUser : data.user;

  await target.route("**/api/**", (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace(/^\/api/, "");
    const key = `${request.method()} ${path}`;

    const dashboardMatch = /^GET \/snapshots\/(\d+)\/dashboard$/.exec(key);
    if (dashboardMatch) {
      const dashboard = data.dashboards[Number(dashboardMatch[1])];
      return dashboard ? json(route, dashboard) : json(route, { detail: "Snapshot not found" }, 404);
    }
    if (/^GET \/matches\/snapshot\/\d+$/.test(key)) return json(route, page(data.matches, url));
    const detailsMatch = /^GET \/matches\/([^/]+)\/details$/.exec(key);
    if (detailsMatch) return json(route, data.matchDetails(detailsMatch[1]));

    switch (key) {
      case "POST /auth/refresh":
        return session ? json(route, data.token) : route.fulfill({ status: 401 });
      case "POST /auth/login":
        session = true;
        return json(route, data.token);
      case "POST /auth/logout":
        session = false;
        return route.fulfill({ status: 204 });
      case "GET /auth/me":
        return json(route, me);
      case "GET /ddragon/version":
        return json(route, "16.10.1");
      case "GET /ddragon/spells":
        return json(route, data.ddragonSpells);
      case "GET /ddragon/runes":
        return json(route, data.ddragonRunes);
      case "GET /players/":
        return json(route, page(data.players, url));
      case "GET /players/1":
        return json(route, data.player);
      case "GET /players/1/summary":
        return json(route, data.roleSummary);
      case "GET /matches/player/1": {
        const offset = Number(url.searchParams.get("offset") ?? 0);
        return json(route, data.matches.slice(offset, offset + Number(url.searchParams.get("limit") ?? 20)));
      }
      case "GET /matches/player/1/champions":
        return json(route, data.championStats);
      case "GET /snapshots/player/1":
        return json(route, page(data.snapshots, url));
      case "POST /snapshots/":
        return json(route, { job_id: "job-1", status: "queued" }, 202);
      case "GET /snapshots/jobs/job-1/stream":
        return route.fulfill({ status: 200, headers: { "Content-Type": "text/event-stream" }, body: data.jobStream });
      case "GET /league/cutoffs":
        return json(route, data.cutoffs((url.searchParams.get("region") ?? "EUW").toUpperCase()));
      case "GET /admin/stats/":
        return json(route, data.adminStats);
      case "GET /admin/users/":
        return json(route, page(data.adminUsers, url));
      case "GET /admin/players/":
        return json(route, page(data.adminPlayers, url));
      default:
        return json(route, { detail: `Not mocked: ${key}` }, 404);
    }
  });

  if (!allowCdn) {
    await target.route("https://ddragon.leagueoflegends.com/**", (route) => route.fulfill({ status: 404 }));
  }
}

export async function signIn(target: Page) {
  await target.goto("/login");
  await target.getByLabel("Email").fill(data.user.email);
  await target.getByLabel("Password").fill("correct horse battery");
  await target.getByRole("button", { name: "Sign in" }).click();
  await expect(target).toHaveURL(/\/players$/);
}
