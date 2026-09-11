import { expect, test } from "@playwright/test";

import { user } from "./fixtures";
import { mockApi, signIn } from "./mockApi";

test("sign in, run an analysis and open its dashboard", async ({ page }) => {
  await mockApi(page);

  await page.goto("/players");
  await expect(page).toHaveURL(/\/login$/);

  await page.getByLabel("Email").fill(user.email);
  await page.getByLabel("Password").fill("correct horse battery");
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(page).toHaveURL(/\/players$/);
  await page.getByRole("link", { name: "Faker#KR1" }).click();

  await expect(page.getByRole("heading", { name: "Faker#KR1" })).toBeVisible();
  await page.getByRole("button", { name: "New analysis" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Start analysis" }).click();

  await expect(page).toHaveURL(/\/players\/1\/snapshots\/42$/);
  await expect(page.getByRole("heading", { name: "Faker", exact: true })).toBeVisible();
  await expect(page.getByText("Kill participation")).toBeVisible();
  await expect(page.getByRole("img", { name: /Radar chart/ })).toBeVisible();

  await page.getByRole("tab", { name: /Matches/ }).click();
  await expect(page).toHaveURL(/tab=matches/);
  await expect(page.getByRole("region", { name: "Matches table" }).getByRole("row")).not.toHaveCount(0);
});

test("the session survives a full page reload", async ({ page }) => {
  await mockApi(page);
  await signIn(page);

  await page.reload();

  await expect(page).toHaveURL(/\/players$/);
  await expect(page.getByRole("link", { name: "Faker#KR1" })).toBeVisible();
});

test("compares two snapshots side by side", async ({ page }) => {
  await mockApi(page);
  await signIn(page);

  await page.goto("/players/1");
  await page.getByRole("checkbox", { name: /Jul 2026/ }).check();
  await page.getByRole("checkbox", { name: /Aug 2026 – 11 Sept 2026|Aug 2026 – 11 Sep 2026/ }).check();
  await page.getByRole("link", { name: "Compare" }).click();

  await expect(page).toHaveURL(/compare\?a=41&b=42/);
  await expect(page.getByRole("row", { name: /Gold diff @14/ })).toContainText("(better)");
});

test("expands a match of the history with its ten players", async ({ page }) => {
  await mockApi(page);
  await signIn(page);

  await page.goto("/players/1");
  const toggle = page.getByRole("button", { name: /Show details/ }).first();
  await toggle.click();

  await expect(page.getByRole("button", { name: /Hide details/ }).first()).toHaveAttribute("aria-expanded", "true");
  await expect(page.getByRole("region", { name: /Victory/ })).toBeVisible();
  await expect(page.getByRole("region", { name: /Defeat/ })).toBeVisible();
  await expect(page.getByText("Keria")).toBeVisible();
  await expect(page.getByText("MVP", { exact: true })).toBeVisible();
});

test("unknown routes inside the app show a not-found page", async ({ page }) => {
  await mockApi(page);
  await signIn(page);

  await page.goto("/does-not-exist");
  await expect(page.getByText("Page not found")).toBeVisible();
});
