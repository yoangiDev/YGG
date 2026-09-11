import { expect, test, type Page } from "@playwright/test";

import { mockApi, signIn } from "./mockApi";

/**
 * Capturas de las pantallas principales con datos de demostración, para el
 * README y para revisar el diseño. No se ejecuta por defecto:
 *
 *     SCREENSHOTS=1 npm run test:e2e -- screenshots
 */
const OUT = process.env.SCREENSHOTS_DIR ?? "test-results/screenshots";

test.skip(!process.env.SCREENSHOTS, "Set SCREENSHOTS=1 to capture screenshots");
test.use({ viewport: { width: 1440, height: 900 }, colorScheme: "dark" });

async function settle(target: Page) {
  await target.waitForLoadState("networkidle");
  // Como cadena: el tsconfig de e2e no incluye los tipos del DOM.
  await target.evaluate("document.fonts.ready");
}

test("desktop screens", async ({ page }) => {
  await mockApi(page, { admin: true, allowCdn: true });

  await page.goto("/login");
  await settle(page);
  await page.screenshot({ path: `${OUT}/01-login.png` });

  await signIn(page);
  await settle(page);
  await page.screenshot({ path: `${OUT}/02-players.png` });

  await page.goto("/players/1");
  await expect(page.getByText("After bootcamp")).toBeVisible();
  await settle(page);
  await page.screenshot({ path: `${OUT}/03-player.png`, fullPage: true });

  await page.getByRole("button", { name: /Show details/ }).first().click();
  await expect(page.getByText("Keria")).toBeVisible();
  await settle(page);
  await page.screenshot({ path: `${OUT}/03b-match-details.png`, fullPage: true });

  await page.goto("/players/1/snapshots/42");
  await expect(page.getByRole("img", { name: /Radar chart/ })).toBeVisible();
  await settle(page);
  await page.screenshot({ path: `${OUT}/04-dashboard.png`, fullPage: true });

  await page.goto("/players/1/snapshots/42?tab=matches");
  await settle(page);
  await page.screenshot({ path: `${OUT}/05-matches.png` });

  await page.goto("/players/1/snapshots/compare?a=41&b=42");
  await expect(page.getByText("Gold diff @14")).toBeVisible();
  await settle(page);
  await page.screenshot({ path: `${OUT}/06-compare.png`, fullPage: true });

  await page.goto("/cutoffs?region=KR");
  await settle(page);
  await page.screenshot({ path: `${OUT}/07-cutoffs.png` });

  await page.goto("/admin/stats");
  await settle(page);
  await page.screenshot({ path: `${OUT}/08-admin.png` });
});

test("mobile dashboard", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockApi(page, { allowCdn: true });
  await signIn(page);

  await page.goto("/players/1/snapshots/42");
  await expect(page.getByRole("img", { name: /Radar chart/ })).toBeVisible();
  await settle(page);
  await page.screenshot({ path: `${OUT}/09-mobile-dashboard.png`, fullPage: true });
});
