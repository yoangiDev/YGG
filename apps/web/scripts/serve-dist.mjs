// Minimal static server for the e2e and performance tests. Serves dist/ like the production
// CDN: brotli or gzip, immutable caching on /assets and SPA fallback to index.html.
// `vite preview` doesn't compress, so it would measure a site quite a bit slower than it is.
//
//   npm run build && node scripts/serve-dist.mjs        (PORT and HOST optional)
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
  if (!candidate.startsWith(ROOT + sep)) return null; // outside dist/
  return existsSync(candidate) && statSync(candidate).isFile() ? candidate : null;
}

createServer((request, response) => {
  const { pathname } = new URL(request.url ?? "/", "http://localhost");
  const isAsset = pathname.startsWith("/assets/");
  let file = fileFor(pathname);

  if (!file) {
    // A file that doesn't exist is a 404; an SPA route (/players/1) gets index.html.
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
