# Métricas

Números medidos, con cómo se midieron. Donde no hay medida se dice, y no se sustituye por un adjetivo.

**Última medición:** septiembre de 2026, rama `feat/web`, en local (Windows 11, Postgres embebido,
Redis en memoria). Las cifras de producción quedan pendientes del despliegue (ver [`deploy.md`](deploy.md)).

## Resumen

| Métrica | Antes | Ahora | Objetivo |
|---|---|---|---|
| Assets estáticos (insignias de rango, iconos de rol, fuente) | 4.170 KB | **121 KB** | < 200 KB |
| JS inicial de la web (gzip) | — (Flutter Web, sin medir) | **126 KB** | < 200 KB |
| LCP del login (4G lenta, CPU 4x) | — | **1,77 s** | < 2,0 s |
| LCP de la lista de jugadores | — | **1,96 s** | < 2,0 s |
| LCP del dashboard de un snapshot | — | **2,34 s** ⚠️ | < 2,0 s |
| CLS (las tres pantallas) | — | **≤ 0,001** | < 0,05 |
| p95 del dashboard, caché caliente (local) | — | **4,0 ms** | — |
| p95 del dashboard, sin caché (local) | — | **11,4 ms** | — |
| Cobertura `ygg-core` | sin CI | **90 %** (121 tests) | — |
| Cobertura API | sin CI | **82 %** (151 tests) | — |
| Lighthouse | — | sin medir | ≥ 95 |

## Web

### Tamaño

`npm run build && node scripts/bundle-budget.mjs` (en CI, falla por encima de 200 KB). Cuenta el script de
entrada y los `modulepreload` de `index.html`, comprimidos con gzip nivel 9.

| | JS inicial (gzip) |
|---|---|
| Primera versión del cliente React | 156,2 KB |
| Con el marco de la app, los diálogos, las gráficas y la tabla en chunks aparte | **126,1 KB** |

Chunks diferidos más grandes: Recharts (88 KB, solo en el dashboard y la comparación), zod +
react-hook-form (32 KB, al abrir un formulario), componentes de Radix (32 KB) y TanStack Table (20 KB, solo
en la pestaña de partidas).

Los assets vienen de `apps/web/scripts/optimize_assets.py`: insignias de rango en WebP al doble del tamaño
máximo mostrado y DM Sans en WOFF2 con solo los glifos latinos. De 4.170 KB a 121 KB (**P11**).

### Web Vitals de laboratorio

`PERF=1 npm run test:e2e -- perf` ([`e2e/perf.spec.ts`](../apps/web/e2e/perf.spec.ts)):

- Build de producción servido con compresión y caché como un CDN (`scripts/serve-dist.mjs`).
- Chrome con el perfil de 4G lenta de Lighthouse: 150 ms de RTT, 1,6 Mbps de bajada, 750 kbps de subida y
  CPU 4x más lenta. Carga en frío (sin caché) de cada ruta directamente por URL, tres veces, mediana.
- API simulada (se mide el cliente). La sesión se restaura con la cookie de refresh, como tras recargar.

| Pantalla | Primera versión | Tras dividir chunks | CLS |
|---|---|---|---|
| `/login` | 1,91 s | **1,77 s** | 0,001 |
| `/players` | 2,08 s | **1,96 s** | 0,001 |
| `/players/1/snapshots/42` | 3,08 s | **2,34 s** | 0,001 |

La cascada de recursos que guarda la prueba mostró el cuello de botella: cada página esperaba a descargar
**todas** sus dependencias antes de pedir sus datos. El dashboard no pedía el snapshot hasta tener
Recharts (95 KB) y la tabla de partidas; la lista de jugadores esperaba a zod por un diálogo cerrado.
Separarlos adelantó las peticiones de datos entre 0,4 y 0,7 s.

⚠️ **El dashboard sigue 340 ms por encima del objetivo** en este perfil. Lo que queda en su camino: el
chunk de Radix (pestañas y diálogos), las dos idas y vueltas de la sesión (refresh + `/auth/me`) y el
render de 24 partidas con la CPU ralentizada. Siguientes pasos posibles: pestañas sin Radix, pedir
`/auth/me` en paralelo al primer dato y prerenderizar el esqueleto de las tarjetas.

**Lighthouse no se ha ejecutado** (no está entre las dependencias y no hay URL pública todavía). Tras el
despliegue: `npx lighthouse https://ygg.tudominio.dev --preset=desktop` y en móvil.

## API

`python scripts/bench_api.py --email demo@ygg.gg --password …` contra la API local con `DEMO_MODE=true` y los
datos de `scripts/seed_demo.py` (3 jugadores, 6 snapshots de 22 y 26 partidas). Peticiones secuenciales
desde la misma máquina, con el rate limiting activado.

| Endpoint | n | p50 | p95 | máx. |
|---|---|---|---|---|
| Dashboard sin caché (se construye desde Postgres) | 6 | 9,3 ms | 11,4 ms | 11,5 ms |
| Dashboard con caché | 80 | 3,2 ms | 4,0 ms | 5,0 ms |
| Partidas de un snapshot (página de 50) | 80 | 7,0 ms | 8,1 ms | 37,0 ms |
| Lista de jugadores | 80 | 3,3 ms | 4,1 ms | 4,2 ms |

Límites de esta medida: base de datos y Redis locales (sin red de por medio), snapshots pequeños y una
sola conexión. Sirve para comparar versiones, no como latencia de producción. El p95 real se medirá
contra Fly.io + Supabase + Upstash.

## Análisis de partidas

**Sin medir de extremo a extremo**: requiere una clave de Riot en vigor. Lo que se puede decir con datos:

- Analizar N partidas nuevas son `1 + 2N` peticiones a Riot (lista de ids, partida y timeline). Con la clave de
  desarrollo (100 peticiones cada 2 minutos) 100 partidas nuevas son 201 peticiones: el limitador global las
  reparte en **al menos ~4 minutos**, y el tiempo lo marca la cuota, no el procesamiento.
- Las partidas ya guardadas **de ese jugador** no se vuelven a descargar: repetir o solapar un período solo pide
  las nuevas.
- Guardar un análisis son unas pocas sentencias `INSERT … ON CONFLICT` en lotes de 500 filas, independientemente
  del número de partidas; antes, una consulta por partida (**P8**).

## Tests

| Suite | Tests | Cobertura | Dónde corre |
|---|---|---|---|
| `ygg-core` (pytest, mypy estricto) | 121 | 90 % | CI, sin servicios |
| API (pytest contra Postgres y Redis) | 151 | 82 % | CI con servicios |
| Web unitarios (Vitest + Testing Library) | 60 | 31 % de líneas | CI |
| Web e2e con API simulada (Playwright) | 4 | — | CI |
| Web e2e contra la API real | 3 | — | Manual (`E2E_REAL_API=1`) |

La cobertura unitaria de la web es baja a propósito: los unitarios cubren la lógica con más riesgo (cliente
HTTP y refresco de sesión, parser SSE y seguimiento de trabajos, formularios, colores y cálculos) y las
pantallas se prueban de extremo a extremo en navegador, lo que V8 no cuenta.

Comandos: `pytest --cov=ygg_core` (core), `pytest --cov=app` (API), `npm run test:coverage` (web).
