import { expect, test, type Page } from "@playwright/test";

import { GAME_ANALYSIS_ID } from "./gameAnalysis";
import { mockApi, signIn } from "./mockApi";

/**
 * Screenshots of the main screens with demo data, for the
 * README and for reviewing the design. It does not run by default:
 *
 *     make screenshots            (from the root: leaves them in docs/img)
 *     SCREENSHOTS=1 npm run test:e2e -- screenshots
 *
 * The art for champions, items and map comes from Riot's CDN. With a network, use
 * the real one (SCREENSHOTS_CDN=1); without it a neutral placeholder of the same
 * size is served so the screenshots don't come out with broken images.
 */
const OUT = process.env.SCREENSHOTS_DIR ?? "test-results/screenshots";

test.skip(!process.env.SCREENSHOTS, "Set SCREENSHOTS=1 to capture screenshots");
test.use({ viewport: { width: 1440, height: 900 }, colorScheme: "dark" });

async function stubRiotArt(target: Page) {
  if (process.env.SCREENSHOTS_CDN) return;
  await target.route("https://ddragon.leagueoflegends.com/**", (route) => {
    const file = new URL(route.request().url()).pathname.split("/").pop() ?? "";
    const name = file.replace(/\.\w+$/, "");
    const isMap = route.request().url().includes("/img/map/");
    const label = isMap || /^\d+$/.test(name) ? "" : name.slice(0, 2);
    const body = isMap
      ? `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><rect width="512" height="512" fill="#0d1112"/>` +
        `<path d="M0 512 L512 0" stroke="#17323a" stroke-width="34"/><rect x="1" y="1" width="510" height="510" fill="none" stroke="#c8f53f" stroke-opacity=".25"/></svg>`
      : `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" fill="#1b2022"/>` +
        `<rect x="1" y="1" width="62" height="62" fill="none" stroke="#c8f53f" stroke-opacity=".35" stroke-width="2"/>` +
        `<text x="32" y="41" text-anchor="middle" font-family="sans-serif" font-size="24" font-weight="700" fill="#c8f53f">${label}</text></svg>`;
    return route.fulfill({ contentType: "image/svg+xml", body });
  });
}

async function setup(target: Page) {
  await mockApi(target, { allowCdn: true });
  await stubRiotArt(target);
}

/** Only the top of the page: on a full page some screens come out at 3,000 px and don't fit in a README. */
const top = (height: number) => ({ fullPage: true, clip: { x: 0, y: 0, width: 1440, height } });

async function settle(target: Page) {
  await target.waitForLoadState("networkidle");
  // As a string: the e2e tsconfig does not include the DOM types.
  await target.evaluate("document.fonts.ready");
}

test("desktop screens", async ({ page }) => {
  await setup(page);

  await signIn(page);
  await expect(page.getByRole("heading", { name: "Faker#KR1" })).toBeVisible();
  await settle(page);
  await page.screenshot({ path: `${OUT}/account.png`, ...top(1000) });

  await page.goto(`/analysis/${GAME_ANALYSIS_ID}`);
  await expect(page.getByRole("heading", { name: "What to work on" })).toBeVisible();
  await settle(page);
  await page.screenshot({ path: `${OUT}/analysis.png`, ...top(1250) });

  await page.goto("/players/1/snapshots/42");
  await expect(page.getByRole("img", { name: /Radar chart/ })).toBeVisible();
  await settle(page);
  await page.screenshot({ path: `${OUT}/dashboard.png`, ...top(1200) });

  await page.goto("/players/1/snapshots/compare?a=41&b=42");
  await expect(page.getByText("Gold diff @14")).toBeVisible();
  await settle(page);
  await page.screenshot({ path: `${OUT}/compare.png`, ...top(1000) });

  await page.goto("/cutoffs?region=KR");
  await settle(page);
  await page.screenshot({ path: `${OUT}/cutoffs.png` });
});

test("mobile screens", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await setup(page);
  await signIn(page);

  await page.goto("/players/1/snapshots/42");
  await expect(page.getByRole("img", { name: /Radar chart/ })).toBeVisible();
  await settle(page);
  await page.screenshot({ path: `${OUT}/mobile-dashboard.png`, fullPage: true, clip: { x: 0, y: 0, width: 390, height: 1700 } });

  await page.goto(`/analysis/${GAME_ANALYSIS_ID}`);
  await expect(page.getByRole("heading", { name: "What to work on" })).toBeVisible();
  await settle(page);
  await page.screenshot({ path: `${OUT}/mobile-analysis.png`, fullPage: true, clip: { x: 0, y: 0, width: 390, height: 1700 } });
});

test("stats by rank", async ({ page }) => {
  await setup(page);
  await signIn(page);

  await page.getByRole("link", { name: "Stats by rank" }).click();
  await expect(page.getByRole("heading", { name: "6 habits of Challenger players" })).toBeVisible();
  await settle(page);
  await page.screenshot({ path: `${OUT}/ranks.png`, ...top(1000) });
});
