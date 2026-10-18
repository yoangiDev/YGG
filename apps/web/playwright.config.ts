import { defineConfig, devices } from "@playwright/test";

const PORT = 4173;
const externalBaseUrl = process.env.E2E_BASE_URL;
const isCI = Boolean(process.env.CI);

/**
 * By default the tests build the web with VITE_API_URL=/api and simulate the
 * API with page.route: they are deterministic and need no Postgres, Redis or
 * Riot key. With E2E_BASE_URL they are launched against a real deployment.
 *
 * The build is served with scripts/serve-dist.mjs (compression and caching as in
 * production) and not with `vite preview`, which doesn't compress.
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: isCI,
  retries: isCI ? 1 : 0,
  reporter: isCI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: externalBaseUrl ?? `http://127.0.0.1:${PORT}`,
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      // Locally the installed Chrome is used; in CI, the Chromium that Playwright downloads.
      use: { ...devices["Desktop Chrome"], ...(isCI ? {} : { channel: "chrome" }) },
    },
  ],
  ...(externalBaseUrl
    ? {}
    : {
        webServer: {
          command: "npm run build && node scripts/serve-dist.mjs",
          url: `http://127.0.0.1:${PORT}`,
          env: { VITE_API_URL: "/api", PORT: String(PORT) },
          reuseExistingServer: !isCI,
          timeout: 180_000,
        },
      }),
});
