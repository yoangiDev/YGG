// Servidor estático mínimo para las pruebas e2e y de rendimiento. Sirve dist/ como el CDN de
// producción: brotli o gzip, caché inmutable en /assets y fallback de SPA a index.html.
// `vite preview` no comprime, así que mediría una web bastante más lenta de lo que es.
//
//   npm run build && node scripts/serve-dist.mjs        (PORT y HOST opcionales)
import { createReadStream, existsSync, statSync } from "node:fs";
import { createServer } from "node:http";
import { extname, join, normalize, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { constants, createBrotliCompress, createGzip } from "node:zlib";

const ROOT = resolve(fileURLToPath(new URL("../dist/", import.meta.url)));
const PORT = Number(process.env.PORT ?? 4173);
const HOST = process.env.HOST ?? "127.0.0.1";

const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json",
  ".map": "application/json",
  ".svg": "image/svg+xml",
  ".webp": "image/webp",
  ".png": "image/png",
  ".woff2": "font/woff2",
};
const COMPRESSIBLE = new Set([".html", ".js", ".css", ".json", ".map", ".svg"]);

function fileFor(pathname) {
  const relative = normalize(decodeURIComponent(pathname)).replace(/^[/\\]+/, "");
  const candidate = join(ROOT, relative);
  if (!candidate.startsWith(ROOT + sep)) return null; // fuera de dist/
  return existsSync(candidate) && statSync(candidate).isFile() ? candidate : null;
}

createServer((request, response) => {
  const { pathname } = new URL(request.url ?? "/", "http://localhost");
  const isAsset = pathname.startsWith("/assets/");
  let file = fileFor(pathname);

  if (!file) {
    // Un fichero que no existe es un 404; una ruta de la SPA (/players/1) recibe index.html.
    if (isAsset || extname(pathname)) {
      response.writeHead(404).end();
      return;
    }
    file = join(ROOT, "index.html");
  }

  const extension = extname(file);
  const headers = {
    "Content-Type": TYPES[extension] ?? "application/octet-stream",
    "Cache-Control": isAsset ? "public, max-age=31536000, immutable" : "no-cache",
    Vary: "Accept-Encoding",
  };

  let body = createReadStream(file);
  const accepted = String(request.headers["accept-encoding"] ?? "");
  if (COMPRESSIBLE.has(extension)) {
    if (/\bbr\b/.test(accepted)) {
      headers["Content-Encoding"] = "br";
      body = body.pipe(createBrotliCompress({ params: { [constants.BROTLI_PARAM_QUALITY]: 5 } }));
    } else if (/\bgzip\b/.test(accepted)) {
      headers["Content-Encoding"] = "gzip";
      body = body.pipe(createGzip());
    }
  }

  response.writeHead(200, headers);
  body.pipe(response);
}).listen(PORT, HOST, () => {
  console.log(`Serving ${ROOT} at http://${HOST}:${PORT}`);
});
