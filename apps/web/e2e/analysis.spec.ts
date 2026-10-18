import { expect, test } from "@playwright/test";

import { user } from "./fixtures";
import { GAME_ANALYSIS_ID } from "./gameAnalysis";
import { mockApi, signIn } from "./mockApi";

test("sign in, run an analysis and open its dashboard", async ({ page }) => {
  await mockApi(page);

  await page.goto("/account");
  await expect(page).toHaveURL(/\/login$/);

  await page.getByLabel("Email").fill(user.email);
  await page.getByLabel("Password").fill("correct horse battery");
  await page.getByRole("button", { name: "Sign in" }).click();

  // one account per user: "Account" opens its page directly
  await expect(page).toHaveURL(/\/account$/);
  await expect(page.getByRole("heading", { name: "Faker#KR1" })).toBeVisible();
  await page.getByRole("button", { name: "New snapshot" }).click();
  // the history in one-day sessions: one is chosen and launched
  await page.getByRole("dialog").locator("button[aria-pressed]").first().click();
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

  await expect(page).toHaveURL(/\/account$/);
  await expect(page.getByRole("heading", { name: "Faker#KR1" })).toBeVisible();
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
  await expect(page.getByText("Grandmaster · 601 LP")).toBeVisible();
  await expect(page.getByText("Challenger · 1284 LP")).toBeVisible(); // Faker's rank in its row
  await expect(page.getByRole("region", { name: /Victory/ }).getByText(/^(MVP|1st|2nd|3rd|\d+th)$/).first()).toBeVisible();
  await expect(page.getByRole("list", { name: "Match history" }).getByTitle(/^(MVP|ACE):/).first()).toBeVisible();
});

test("charts the elo of a verified player", async ({ page }) => {
  await mockApi(page);
  await signIn(page);

  await page.goto("/players/1");
  await expect(page.getByRole("img", { name: /Elo from Diamond I · 50 LP .* to Master · \d+ LP/ })).toBeVisible();
  // Fixture: 3084 at the end, 2834 30 days ago and 3007 7 days ago.
  await expect(page.getByText("+250 LP")).toBeVisible();
  await expect(page.getByText("+77 LP")).toBeVisible();
});

test("each match of a snapshot unfolds into its win probability timeline", async ({ page }) => {
  await mockApi(page);
  await signIn(page);

  await page.goto("/players/1/snapshots/42?tab=matches");
  const table = page.getByRole("region", { name: "Matches table" });
  await expect(table.getByRole("columnheader", { name: "Grade" })).toBeVisible();
  await table.getByRole("button", { name: "Show win probability timeline" }).first().click();

  const plays = page.getByRole("list", { name: "Plays" });
  await expect(plays.getByText("Killed Renekton")).toBeVisible();
  await expect(plays.getByText("1st dragon after your kill")).toBeVisible();
  await expect(plays.getByText("Mid outer turret lost while you were dead")).toBeVisible();

  // Each event explains its value: what moved it and what part falls to it.
  await plays.getByText("Killed Renekton").click();
  await expect(plays.getByText("Split between the 2 teammates who took part: yours is 1/2.")).toBeVisible();
  await expect(plays.getByRole("list", { name: "Why" }).first()).toContainText("Numbers advantage +1");
  await expect(plays.getByText("Your team collected a 300 gold bounty and a 1,000 gold shutdown.")).toBeVisible();
});

test("champion stats unfold each champion's games, and matches lists them all", async ({ page }) => {
  await mockApi(page);
  await signIn(page);

  await page.goto("/players/1/snapshots/42?tab=champions");
  await page.getByRole("button", { name: /Orianna/ }).click();
  const orianna = page.getByRole("cell", { name: "Orianna games" }).getByRole("region", { name: "Matches table" });
  await expect(orianna.getByRole("row")).toHaveCount(1 + 4); // header + its 4 fixture matches

  await page.getByRole("tab", { name: "Matches (24)" }).click();
  const all = page.getByRole("region", { name: "Matches table" });
  await expect(all.getByRole("row").nth(10)).toBeVisible(); // all of them, not only those of one champion
});

test("an analysis closed half-way keeps its progress in the corner of every page", async ({ page }) => {
  await mockApi(page);
  await signIn(page);
  // The analysis stays at 40% until `finished`; the stream is cut with no final state and the app queries again.
  let finished = false;
  const job = () => ({
    job_id: "job-1",
    status: finished ? "done" : "processing",
    progress: finished ? 100 : 40,
    snapshot_id: finished ? 42 : null,
    error: null,
    attempts: 1,
  });
  await page.route("**/api/snapshots/jobs/job-1**", (route) =>
    route.request().url().endsWith("/stream")
      ? route.fulfill({ headers: { "Content-Type": "text/event-stream" }, body: `event: progress\ndata: ${JSON.stringify(job())}\n\n` })
      : route.fulfill({ json: job() }),
  );

  await page.goto("/players/1");
  await page.getByRole("button", { name: "New snapshot" }).click();
  await page.getByRole("dialog").locator("button[aria-pressed]").first().click();
  await page.getByRole("dialog").getByRole("button", { name: "Start analysis" }).click();
  await expect(page.getByRole("dialog").getByText("40%")).toBeVisible();
  await page.getByRole("button", { name: "Run in background" }).click();

  await page.goto("/players"); // another screen, and reloading: it comes from localStorage
  const corner = page.getByRole("complementary", { name: "Analyses in progress" });
  await expect(corner).toContainText("Faker#KR1");
  await expect(corner).toContainText("40%");

  finished = true;
  const open = corner.getByRole("link", { name: "Open analysis" });
  await expect(open).toBeVisible({ timeout: 15_000 });
  await open.click();
  await expect(page).toHaveURL(/\/players\/1\/snapshots\/42$/);
  await expect(corner).toBeHidden();
});

test("unknown routes inside the app show a not-found page", async ({ page }) => {
  await mockApi(page);
  await signIn(page);

  await page.goto("/does-not-exist");
  await expect(page.getByText("Page not found")).toBeVisible();
});

test("new analysis lists the games of the current patch and asks for the replay of the one you pick", async ({ page }) => {
  await mockApi(page);
  await signIn(page);

  await page.getByRole("button", { name: "New analysis" }).click();
  await page.getByRole("button", { name: /^Analyse .* game$/ }).first().click();
  await expect(page.getByRole("button", { name: "Choose the file" })).toBeVisible();
});

test("a finished game analysis shows its moments and the coach review", async ({ page }) => {
  await mockApi(page, { signedIn: true });

  await page.goto(`/analysis/${GAME_ANALYSIS_ID}`);

  await expect(page.getByRole("heading", { name: "Kaisa analysis" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "What to work on" })).toBeVisible();
  await expect(page.getByText("Recall as soon as the wave is pushed, and count who you have not seen")).toBeVisible();
  await expect(page.getByText("Died to Qiyana without seeing her").first()).toBeVisible();
});

test("an analysis the user never ran is a not-found page", async ({ page }) => {
  await mockApi(page, { signedIn: true });

  await page.goto("/analysis/EUW1_999999999");

  await expect(page.getByText("Page not found")).toBeVisible();
});
