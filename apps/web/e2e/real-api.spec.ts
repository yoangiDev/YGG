import { expect, test } from "@playwright/test";

/**
 * Contra la API de verdad (sin mocks): cookies httpOnly, CORS entre
 * localhost:5173 y localhost:8000 y refresco silencioso tras recargar.
 * No toca la Riot API, así que no necesita clave.
 *
 *     make up   (o la API con uvicorn y la web con npm run dev)
 *     E2E_REAL_API=1 E2E_BASE_URL=http://localhost:5173 npm run test:e2e -- real-api
 */
test.skip(!process.env.E2E_REAL_API, "Set E2E_REAL_API=1 and E2E_BASE_URL with the API running");

test("register, keep the session across reloads and sign out", async ({ page }) => {
  const id = `${Date.now().toString(36)}${test.info().workerIndex}`;

  await page.goto("/login");
  await page.getByRole("button", { name: "Create an account" }).click();
  await page.getByLabel("Username").fill(`e2e_${id}`);
  await page.getByLabel("Email").fill(`e2e_${id}@example.com`);
  await page.getByLabel("Password").fill(`e2e-password-${id}`);
  await page.getByRole("button", { name: "Create account" }).click();

  await expect(page).toHaveURL(/\/players$/);
  await expect(page.getByText("No players yet")).toBeVisible();

  const refresh = (await page.context().cookies()).find((cookie) => cookie.name === "ygg_refresh");
  expect(refresh).toMatchObject({ httpOnly: true, path: "/auth", sameSite: "Lax" });

  // Sin token en memoria tras recargar: la sesión vuelve gracias a la cookie de refresh.
  await page.reload();
  await expect(page.getByText("No players yet")).toBeVisible();

  await page.getByRole("button", { name: /Account menu/ }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login$/);

  await page.reload();
  await expect(page).toHaveURL(/\/login$/);
});

test.describe("public demo", () => {
  // API con DEMO_MODE=true y la cuenta sembrada con scripts/seed_demo.py.
  test.skip(!process.env.E2E_DEMO_PASSWORD, "Set E2E_DEMO_PASSWORD (and E2E_DEMO_EMAIL) for a seeded demo API");

  test("browses the seeded analysis and cannot change anything", async ({ page }) => {
    // Capturas de tamaño de pantalla (las del README salen de aquí).
    const shots = "test-results/screenshots";
    const settle = async () => {
      await page.waitForLoadState("networkidle");
      // Iconos de campeón con loading="lazy": se espera a que terminen (o fallen) antes de capturar.
      await page.evaluate(
        "Promise.all([document.fonts.ready, ...Array.from(document.images).filter((i) => !i.complete).map((i) => new Promise((r) => { i.addEventListener('load', r); i.addEventListener('error', r); }))])",
      );
    };
    await page.setViewportSize({ width: 1440, height: 1000 });

    await page.goto("/login");
    await page.getByLabel("Email").fill(process.env.E2E_DEMO_EMAIL ?? "demo@ygg.gg");
    await page.getByLabel("Password").fill(process.env.E2E_DEMO_PASSWORD ?? "");
    await page.getByRole("button", { name: "Sign in" }).click();

    const mid = page.getByRole("link", { name: "Demo Mid#DEMO" });
    await expect(mid).toBeVisible();
    await settle();
    await page.screenshot({ path: `${shots}/real-01-players.png` });

    await mid.click();
    await expect(page.getByText("Last 30 days")).toBeVisible();
    await settle();
    await page.screenshot({ path: `${shots}/real-02-player.png` });

    // Cualquier escritura se rechaza con un mensaje legible.
    await page.getByRole("button", { name: "Update rank" }).click();
    const readOnly = page.getByText("The public demo is read-only.");
    await expect(readOnly).toBeVisible();
    await expect(readOnly).toBeHidden({ timeout: 10_000 });

    const snapshotLink = page.getByRole("link", { name: /Last 30 days/ });
    const href = await snapshotLink.getAttribute("href");
    await snapshotLink.click();
    await expect(page.getByRole("img", { name: /Radar chart/ })).toBeVisible();
    await settle();
    await page.screenshot({ path: `${shots}/real-03-dashboard.png` });
    await page.screenshot({ path: `${shots}/real-03-dashboard-full.png`, fullPage: true });

    await page.goto(`${href ?? ""}?tab=matches`);
    await expect(page.getByRole("region", { name: "Matches table" }).getByRole("row")).not.toHaveCount(0);
    await settle();
    await page.screenshot({ path: `${shots}/real-04-matches.png` });
  });
});

test("wrong credentials show the API error", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill("nobody@example.com");
  await page.getByLabel("Password").fill("definitely-not-the-password");
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(page.getByRole("alert")).toBeVisible();
  await expect(page).toHaveURL(/\/login$/);
});
