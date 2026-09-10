# Despliegue y demo pública

Guía de la Fase 6. La configuración está en el repositorio; **las cuentas, los
secretos, el dominio y el primer despliegue los haces tú** (nada de esto se
ejecuta solo hasta que configures el entorno `production` en GitHub).

## Arquitectura

| Pieza | Dónde | Configuración |
|---|---|---|
| Web (estático) | Vercel | [`apps/web/vercel.json`](../apps/web/vercel.json): SPA, caché inmutable de `/assets`, CSP, HSTS |
| API | Fly.io, app `ygg-api` | [`infra/fly.api.toml`](../infra/fly.api.toml): migraciones como `release_command`, 1 máquina siempre encendida |
| Worker | Fly.io, app `ygg-worker` | [`infra/fly.worker.toml`](../infra/fly.worker.toml): `arq app.jobs.worker.WorkerSettings` |
| Postgres | Supabase | `DATABASE_URL` con `?sslmode=require` |
| Redis | Upstash | `REDIS_URL` con `rediss://` |
| Pipeline | GitHub Actions | [`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml): CI verde en `main` → API → worker → web |

### Por qué hace falta un dominio propio

El refresh token viaja en una cookie `httpOnly; SameSite=Lax; Path=/auth`. El
navegador solo la envía si la web y la API son del mismo *site* (mismo dominio
registrable):

- ✅ `ygg.tudominio.dev` (Vercel) + `api.ygg.tudominio.dev` (Fly)
- ❌ `ygg.vercel.app` + `ygg-api.fly.dev`: son sites distintos y la sesión se perdería al recargar.

Sustituye `ygg.example.dev` en tres sitios: `CORS_ORIGINS` de `infra/fly.api.toml`,
`connect-src` de la CSP en `apps/web/vercel.json` y la variable `API_URL` del entorno de GitHub.

## Puesta en marcha (una vez)

1. **Base de datos y Redis.** Crea el proyecto en Supabase y la base de Upstash. Apunta
   `DATABASE_URL` y `REDIS_URL`.
2. **Fly.io.**
   ```bash
   flyctl apps create ygg-api
   flyctl apps create ygg-worker
   flyctl secrets set -a ygg-api    DATABASE_URL=... REDIS_URL=... SECRET_KEY=... RIOT_API_KEY=...
   flyctl secrets set -a ygg-worker DATABASE_URL=... REDIS_URL=... SECRET_KEY=... RIOT_API_KEY=...
   flyctl certs add -a ygg-api api.ygg.tudominio.dev
   ```
   `SECRET_KEY` debe tener al menos 32 bytes (la API no arranca en producción con menos):
   `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
3. **Vercel.** Importa el repo con *Root Directory* `apps/web`, añade el dominio
   `ygg.tudominio.dev` y define `VITE_API_URL=https://api.ygg.tudominio.dev`.
4. **GitHub.** Crea el entorno `production` con:
   - secrets: `FLY_API_TOKEN` (`flyctl tokens create deploy`), `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`
   - variables: `API_URL`, y para la demo `DEMO_EMAIL` y `DEMO_PASSWORD`
   
   Añade una regla de aprobación manual al entorno si quieres revisar cada despliegue.
5. **Primer despliegue.** Lanza *Deploy* con `workflow_dispatch` y comprueba
   `https://api.ygg.tudominio.dev/health` (Postgres y Redis en `ok`).

## Modo demo

La clave de desarrollo de Riot caduca cada 24 h, así que la demo del CV no puede depender de ella.

- `DEMO_MODE=true` en `ygg-api` convierte la API en **solo lectura**: rechaza con 403 cualquier
  escritura salvo login, refresh y logout, y cualquier lectura que llamaría a Riot
  (`sync`, `live`, `refresh`, `compare_*`). El historial y los cortes de rango se sirven
  siempre de la base de datos. Implementación: `DemoModeMiddleware` en `app/core/middleware.py`.
- La cuenta y sus datos se siembran con un script idempotente (datos sintéticos con la forma
  exacta de los reales; el análisis y el dashboard son el código de producción):
  ```bash
  flyctl ssh console -a ygg-api -C "sh -c 'DEMO_PASSWORD=... python scripts/seed_demo.py'"
  ```
- Con `VITE_DEMO_EMAIL` y `VITE_DEMO_PASSWORD` definidas, el login muestra las credenciales
  y un botón «Enter the demo», y la app enseña un aviso de solo lectura.

Usa una base de datos propia para la demo: `DEMO_MODE` bloquea las escrituras de **todos** los
usuarios de esa API, no solo las de la cuenta demo.

## Rollback

- **API y worker.** `flyctl releases -a ygg-api` lista las versiones con su imagen; para volver:
  `flyctl deploy -a ygg-api --config infra/fly.api.toml --image registry.fly.io/ygg-api:deployment-<id>`
  (y lo mismo para `ygg-worker`).
- **Web.** En Vercel, *Deployments* → versión anterior → *Promote to Production*
  (o `vercel rollback`).
- **Migraciones.** Se escriben en modo *expand/contract*: cada migración es compatible con el código
  de la versión anterior, así que un rollback de la API no necesita tocar el esquema. Solo si una
  migración concreta hay que revertirla: `flyctl ssh console -a ygg-api -C "alembic downgrade -1"`.

## Clave de Riot

1. Solicita la **Personal API Key** en <https://developer.riotgames.com>: descripción del proyecto,
   URL pública funcionando (la demo sirve) y cumplimiento de la política (sin monetización y con el
   aviso legal de Riot, que ya aparece en el login).
2. Cuando llegue, cámbiala en los dos apps: `flyctl secrets set -a ygg-api RIOT_API_KEY=...`
   (y en `ygg-worker`). Fly reinicia las máquinas con el secreto nuevo.
3. Ajusta `RATE_LIMIT_SNAPSHOTS_PER_HOUR` para no agotar la cuota diaria.

## Comprobaciones tras desplegar

```bash
curl -fsS https://api.ygg.tudominio.dev/health
curl -fsSI https://ygg.tudominio.dev | grep -i -E "content-security-policy|strict-transport"
E2E_REAL_API=1 E2E_BASE_URL=https://ygg.tudominio.dev npx playwright test real-api   # desde apps/web, fuera de la demo
```

El objetivo de arranque en frío (< 3 s) se cumple manteniendo `min_machines_running = 1`; mídelo
con `curl -w "%{time_total}\n" -o /dev/null -s https://api.ygg.tudominio.dev/health/live` tras un
`flyctl machine restart`.
