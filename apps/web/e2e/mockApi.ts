import { expect, type Page, type Route } from "@playwright/test";

import * as data from "./fixtures";
import { GAME_ANALYSIS_ID, gameAnalysisResponse } from "./gameAnalysis";

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

function page<T>(items: T[], url: URL) {
  const limit = Number(url.searchParams.get("limit") ?? 50);
  const offset = Number(url.searchParams.get("offset") ?? 0);
  return { items: items.slice(offset, offset + limit), total: items.length, limit, offset };
}

export interface MockOptions {
  /** Signs in as an administrator. */
  admin?: boolean;
  /** Lets through the Riot CDN images (for screenshots); blocked by default. */
  allowCdn?: boolean;
  /** Already signed-in session (valid refresh cookie), to open deep routes directly. */
  signedIn?: boolean;
}

/**
 * Simulated API with page.route. The web is built with VITE_API_URL=/api, so
 * all calls are same-origin and there is no CORS in between.
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
    const wpaMatch = /^GET \/matches\/snapshot\/\d+\/([^/]+)\/wpa$/.exec(key);
    if (wpaMatch) return json(route, data.matchWpa(wpaMatch[1]));
    const playerUpdate = /^PUT \/players\/(\d+)$/.exec(key);
    if (playerUpdate) {
      const current = data.players.find((p) => p.id === Number(playerUpdate[1]));
      return current ? json(route, { ...current, ...(request.postDataJSON() as object) }) : json(route, { detail: "Player not found." }, 404);
    }
    const analysisMatch = /^GET \/games\/analyses\/([^/]+)$/.exec(key);
    if (analysisMatch) {
      return analysisMatch[1] === GAME_ANALYSIS_ID
        ? json(route, gameAnalysisResponse)
        : json(route, { detail: "You haven't analysed this game." }, 404);
    }
    const detailsMatch = /^GET \/matches\/([^/]+)\/details$/.exec(key);
    if (detailsMatch) return json(route, data.matchDetails(detailsMatch[1]));
    if (/^GET \/matches\/[^/]+\/lobby-rank$/.test(key)) return json(route, data.lobbyRank);

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
      case "GET /games/analyses":
        return json(route, { quota: { limit: null, used: 0, next_at: null }, items: [] });
      case "GET /players/":
        return json(route, page(data.players, url));
      case "GET /players/1":
        return json(route, data.player);
      case "GET /players/1/summary":
        return json(route, data.roleSummary);
      case "GET /players/1/elo":
        return json(route, data.eloHistory);
      case "GET /matches/player/1": {
        const offset = Number(url.searchParams.get("offset") ?? 0);
        return json(route, data.matches.slice(offset, offset + Number(url.searchParams.get("limit") ?? 20)).map(data.withPlacement));
      }
      case "GET /matches/player/1/champions":
        return json(route, url.searchParams.get("season") === "true" ? data.championStats.slice(0, 3) : data.championStats);
      case "POST /players/1/season-sync":
        return json(route, { downloaded: 42, stored_games: 42, done: true, next_offset: 42 });
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
  await expect(target).toHaveURL(/\/account$/);
}
