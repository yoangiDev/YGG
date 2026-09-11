// Comprueba el presupuesto de JS inicial (PLAN_WEB.md, Fase 5) sobre dist/:
// cuenta el script de entrada y los modulepreload de index.html, comprimidos con gzip.
//
//   npm run build && node scripts/bundle-budget.mjs
import { readdirSync, readFileSync } from "node:fs";
import { gzipSync } from "node:zlib";

const DIST = new URL("../dist/", import.meta.url);
const BUDGET_KB = Number(process.env.BUDGET_KB ?? 200);

const gzipKb = (path) => gzipSync(readFileSync(new URL(path, DIST)), { level: 9 }).length / 1024;
const format = (kb) => `${kb.toFixed(1).padStart(7)} KB`;

const html = readFileSync(new URL("index.html", DIST), "utf8");
const initial = [...new Set([...html.matchAll(/(?:src|href)="\/(assets\/[^"]+\.js)"/g)].map((match) => match[1]))];

const rows = initial.map((file) => [file, gzipKb(file)]);
const total = rows.reduce((sum, [, kb]) => sum + kb, 0);

console.log("Initial JS (entry + modulepreload):");
for (const [file, kb] of rows) console.log(`${format(kb)}  ${file}`);
console.log(`${format(total)}  total, budget ${BUDGET_KB} KB\n`);

const lazy = readdirSync(new URL("assets/", DIST))
  .filter((file) => file.endsWith(".js") && !initial.includes(`assets/${file}`))
  .map((file) => [file, gzipKb(`assets/${file}`)])
  .sort((a, b) => b[1] - a[1]);

console.log("Largest lazy chunks:");
for (const [file, kb] of lazy.slice(0, 8)) console.log(`${format(kb)}  assets/${file}`);

if (total > BUDGET_KB) {
  console.error(`\nInitial JS is ${total.toFixed(1)} KB gzip, over the ${BUDGET_KB} KB budget.`);
  process.exit(1);
}
