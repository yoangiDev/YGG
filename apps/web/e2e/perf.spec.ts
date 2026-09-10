import { mkdirSync, writeFileSync } from "node:fs";

import { expect, test, type Browser, type Page } from "@playwright/test";

import { mockApi } from "./mockApi";

/**
 * Web Vitals de laboratorio sobre el build de producción, con el perfil de
 * "4G lenta" de Lighthouse: 150 ms de RTT, 1,6 Mbps de bajada, 750 kbps de
 * subida y CPU 4x más lenta. Cada página se carga en frío (contexto nuevo, sin
 * caché) tres veces y se toma la mediana. No se ejecuta por defecto:
 *
 *     PERF=1 npm run test:e2e -- perf
 *
 * La API está simulada: se mide el cliente, no el servidor (eso lo hace
 * apps/api/scripts/bench_api.py). Además de LCP y CLS se guarda qué elemento
 * fue el LCP y la cascada de recursos de la última carga, para saber qué optimizar.
 */
test.skip(!process.env.PERF, "Set PERF=1 to measure Web Vitals");

const RUNS = 3;
const BUDGET = { lcp: 2000, cls: 0.05 };

interface Sample {
  lcp: number;
  cls: number;
  lcpElement: string;
  resources: { name: string; start: number; end: number }[];
}

async function throttle(page: Page) {
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("Network.enable");
  await cdp.send("Network.emulateNetworkConditions", {
    offline: false,
    latency: 150,
    downloadThroughput: (1.6 * 1024 * 1024) / 8,
    uploadThroughput: (750 * 1024) / 8,
  });
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
}

// Como cadena: el tsconfig de e2e no incluye los tipos del DOM.
const COLLECT = `new Promise((resolve) => {
  let lcp = 0;
  let lcpElement = "";
  let cls = 0;
  new PerformanceObserver((list) => {
    for (const entry of list.getEntries()) {
      lcp = entry.startTime;
      const el = entry.element;
      lcpElement = el ? (el.tagName.toLowerCase() + " " + (el.textContent || "").trim().slice(0, 40)) : entry.url || "";
    }
  }).observe({ type: "largest-contentful-paint", buffered: true });
  new PerformanceObserver((list) => {
    for (const entry of list.getEntries()) if (!entry.hadRecentInput) cls += entry.value;
  }).observe({ type: "layout-shift", buffered: true });
  setTimeout(() => {
    const resources = performance.getEntriesByType("resource")
      .map((r) => ({ name: r.name.replace(location.origin, ""), start: Math.round(r.startTime), end: Math.round(r.responseEnd) }))
      .sort((a, b) => a.start - b.start);
    resolve({ lcp, cls, lcpElement, resources });
  }, 2000);
})`;

async function measure(browser: Browser, path: string, ready: string, signedIn: boolean) {
  const samples: Sample[] = [];
  for (let run = 0; run < RUNS; run++) {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await context.newPage();
    await mockApi(page, { signedIn });
    await throttle(page);
    await page.goto(path, { waitUntil: "load" });
    await expect(page.getByText(ready).first()).toBeVisible({ timeout: 30_000 });
    samples.push(await page.evaluate<Sample>(COLLECT));
    await context.close();
  }
  const median = (values: number[]) => [...values].sort((a, b) => a - b)[Math.floor(values.length / 2)] ?? 0;
  const last = samples.at(-1);
  return {
    lcp: median(samples.map((s) => s.lcp)),
    cls: median(samples.map((s) => s.cls)),
    lcpElement: last?.lcpElement ?? "",
    resources: last?.resources ?? [],
  };
}

test("Web Vitals under a slow 4G profile", async ({ browser }) => {
  test.setTimeout(240_000);

  const results = {
    login: await measure(browser, "/login", "Welcome back", false),
    players: await measure(browser, "/players", "Faker", true),
    dashboard: await measure(browser, "/players/1/snapshots/42", "Kill participation", true),
  };

  mkdirSync("test-results", { recursive: true });
  writeFileSync("test-results/web-vitals.json", `${JSON.stringify(results, null, 2)}\n`);
  for (const [name, vitals] of Object.entries(results)) {
    console.log(
      `${name.padEnd(10)} LCP ${Math.round(vitals.lcp)} ms · CLS ${vitals.cls.toFixed(3)} · LCP element: ${vitals.lcpElement}`,
    );
    expect.soft(vitals.lcp, `${name} LCP`).toBeLessThan(BUDGET.lcp);
    expect.soft(vitals.cls, `${name} CLS`).toBeLessThan(BUDGET.cls);
  }
});
