import { defineConfig, devices } from "@playwright/test";

const PORT = 4173;
const externalBaseUrl = process.env.E2E_BASE_URL;
const isCI = Boolean(process.env.CI);

/**
 * Por defecto las pruebas construyen la web con VITE_API_URL=/api y simulan la
 * API con page.route: son deterministas y no necesitan Postgres, Redis ni una
 * clave de Riot. Con E2E_BASE_URL se lanzan contra un despliegue real.
 *
 * El build se sirve con scripts/serve-dist.mjs (compresión y caché como en
 * producción) y no con `vite preview`, que no comprime.
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
      // En local se usa el Chrome instalado; en CI, el Chromium que descarga Playwright.
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
