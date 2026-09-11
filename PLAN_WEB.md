# YGG → aplicación web

Plan de migración a web (React + TypeScript) y endurecimiento del backend, orientado a que el proyecto sirva como pieza principal del portfolio.

- **Fecha:** 10 de septiembre de 2026
- **Ritmo asumido:** 4-6 h/día, 3-4 semanas (~20-25 jornadas, ~110 h)
- **Decisiones tomadas:** frontend React 19 + TS + Vite (SPA) · `ygg-core` como paquete motor que la API consume · demo pública en vivo con Personal API Key de Riot · arquitectura monorepo · capa de datos: SQLAlchemy 2.0 asíncrono + SQL a mano en analítica + DuckDB en el core

---

## 1. Qué hay hoy

### Inventario

| Capa | Stack | Estado |
|---|---|---|
| Backend | FastAPI 0.115, SQLAlchemy 2.0 (**síncrono**, psycopg2), Alembic, PostgreSQL (Supabase), python-jose + bcrypt, aiohttp | Desplegado en Render (`ygg-tfg.onrender.com`) |
| Frontend | Flutter 3.11, Riverpod 2, Dio, fl_chart, `shared_preferences` | Multiplataforma (android/ios/web/windows/linux/macos) |
| CI | GitHub Actions | Solo compila Windows / Linux / APK. **No ejecuta los tests ni construye web** |
| Tests | pytest + pytest-asyncio (8 ficheros, ~75 KB) + tests Dart | Existen y son decentes, pero nadie los ejecuta automáticamente |
| Storage | Supabase Storage (avatares), disco local para caché de Data Dragon | El disco de Render es efímero |

Piezas de peso: `riot_client.py` (1.286 líneas), `dashboard_service.py` (585), y en el front ficheros monolíticos como `admin_users.dart` (49 KB), `hextech_header.dart` (38 KB), `snapshot_panel.dart` (34 KB), `player_detail_screen.dart` (32 KB).

### Lo que ya vende bien (conservar intacto)

1. **Cliente de Riot API serio.** `RiotRateLimiter` es un limitador global de ventana deslizante (10 req/s, 70 req/2 min) con pausa global coordinada al recibir un 429 y respeto de `Retry-After`, más semáforos separados para conexiones en vuelo y para pares match+timeline. Esto es exactamente el tipo de código que un entrevistador técnico valora.
2. **Enriquecimiento con timeline.** Diferenciales de CS/oro/XP a los minutos 8/14/25, solo kills, *dragon setups* con detección de jungla en zona, *objective vision score* por radio alrededor del objetivo, eventos de muerte y wards con coordenadas, y parser de Role Quests de la temporada 26. Es trabajo de dominio real, no un CRUD.
3. **Modelo N:M snapshot↔match** con tabla intermedia y constraint de unicidad, reutilizando partidas entre snapshots en vez de duplicarlas. Y caché de historial con TTL de 1 hora.
4. **Dashboard con radar normalizado por rol**, techos por posición, benchmarks de Challenger y comparación opcional contra otra cuenta de Riot en vivo.
5. **Diseño ya definido.** La paleta Hextech de `app_theme.dart` está documentada en HSL y, según el propio comentario del fichero, es «traducción directa de los valores HSL del prototipo React». Los tokens de diseño para Tailwind ya están hechos.

### Problemas encontrados

Ordenados por lo que me preocupa, no por dónde aparecen.

#### Corrección de datos

**P1 — Dos jugadores tuyos en la misma partida se pisan los datos.** `match_data.match_id` es `UNIQUE` global y la fila contiene las estadísticas *de un participante concreto* (`champion`, `kills`, `cs_diff_14`, `player_role`…). `_parse_match(match_data, player.puuid, …)` construye la fila con los datos del jugador analizado. Cuando en `stats_runner.run_stats_extraction` ya existe esa `match_id`, el código hace `copy_timeline_fields(existing_match, match)` y **reutiliza la fila del primer jugador**, enlazándola al snapshot del segundo. Resultado: si registras a dos jugadores que jugaron juntos —escenario normal en scouting de equipos— el segundo muestra el campeón, el KDA y los diffs del primero. Es el bug más grave del proyecto y además es el que obliga a rediseñar el modelo.

**P2 — IDOR en el estado de los jobs.** `GET /snapshots/jobs/{job_id}` exige autenticación pero no comprueba propiedad, y la tabla `jobs` no tiene `user_id`. Cualquier usuario autenticado que adivine o intercepte un `job_id` lee el job de otro.

**P3 — Jobs que se pierden.** Los análisis corren con `asyncio.create_task` dentro del proceso de FastAPI. Cada deploy, reinicio o *spin-down* del plan gratuito de Render mata el job a medias: queda `processing` para siempre y el frontend hace polling indefinido. El propio `architecture.md` lo reconoce como limitación.

#### Seguridad

**P4 — CORS mal configurado.** `allow_origins=["*"]` junto a `allow_credentials=True` es una combinación que el navegador rechaza por especificación, y bloquea cualquier migración a autenticación por cookie.

**P5 — Cadena de autenticación débil.** `python-jose` 3.3.0 está sin mantenimiento activo; no hay refresh token ni revocación (solo un access token de 30 min, así que la sesión muere a media sesión de trabajo); `/auth/register` no valida longitud mínima de contraseña mientras que el cambio de contraseña sí exige 6 caracteres; y no hay ningún límite de intentos en `/auth/login`. En la app Flutter el token vive en `shared_preferences`, que en web es `localStorage`: legible por cualquier XSS.

**P6 — Sin rate limiting propio.** El limitador protege a Riot de nosotros, pero nada protege la API de un cliente abusivo. Un `POST /snapshots/` en bucle dispara trabajos caros sin coste para el atacante.

#### Rendimiento

**P7 — ORM síncrono dentro de endpoints async.** El motor es `create_engine` + psycopg2 (pool de 5), y se usa desde funciones `async def`. Cada consulta bloquea el event loop, que es el mismo que atiende las descargas concurrentes de Riot. Es la causa estructural de los picos de latencia.

**P8 — N+1 en los bucles de persistencia.** `stats_runner` y `match_history.update_history_cache` consultan `Match` por `match_id` una vez por partida. Con 200 partidas son 200 *round-trips* extra. `get_history_from_cache` además no tiene `LIMIT`, y el refresco del historial borra todas las filas del jugador y las reinserta.

**P9 — Dashboard sin caché ni contrato.** `GET /snapshots/{id}/dashboard` no declara `response_model` (queda fuera del esquema OpenAPI, justo el endpoint más complejo), recalcula el dashboard completo en cada petición y embute la lista entera de partidas en la respuesta.

**P10 — Caché de Data Dragon en disco efímero.** Se escribe en `./data/ddragon` y se monta como `StaticFiles`. En Render ese disco desaparece en cada deploy, así que la caché nace fría y vuelve a golpear Riot.

**P11 — Assets imposibles para web.** Las insignias de rango son PNG de 300-670 KB cada una (`grandmaster_badge.png` 674 KB, `challenger_badge.png` 653 KB): casi 4 MB solo en badges. En una app de escritorio se tolera; en web es inaceptable.

#### Bloqueantes específicos de web

**P12 — No hay routing.** `_AuthGate` hace un `switch` sobre el estado de auth y la navegación es `Navigator.push`. No hay URLs, ni enlaces profundos, ni botón atrás del navegador, ni nada que compartir. Un enlace a «el snapshot de tal jugador» no existe.

**P13 — Flutter Web como vehículo de portfolio.** Ya hay un `frontend/docs/flutter_web_performance_baseline.md` midiendo *janky frames* en la sección de gráficas, lo que confirma que el problema apareció en la práctica. Sumado al bundle de CanvasKit y a la ausencia de SEO, es la razón de fondo para reescribir el cliente.

#### Operación

**P14 — Doble fuente de verdad del esquema.** `Base.metadata.create_all(bind=engine)` en el `lifespan` conviviendo con Alembic: el arranque puede crear tablas que ninguna migración describe.

**P15 — Sin observabilidad.** No hay logging estructurado, ni request-id, ni captura de errores, ni métricas. `/health` devuelve una constante sin comprobar la base de datos.

**P16 — Arrancarlo en local es un viaje.** No hay Dockerfile ni `docker-compose`: hace falta Postgres instalado, Python con venv y el SDK de Flutter. Para quien revise tu repo, eso es fricción pura.

**P17 — `datetime.utcnow` naive** en `RankCutoff.fetched_at` (deprecado en Python 3.12 y mezcla de *aware* y *naive* en la misma base).

**P18 — La carpeta local no es un repo git.** `C:\Users\orell\Proyectos\YGG` no contiene `.git` aunque sí hay `.github/workflows`. Antes de empezar hay que localizar el repo real (o inicializarlo y subirlo), porque todo el plan asume trabajo con ramas y PRs.

---

## 2. Arquitectura destino

```
ygg/
├─ packages/ygg-core/          # Paquete Python puro: dominio, Riot, métricas
│  ├─ src/ygg_core/
│  │  ├─ domain/               # Dataclasses: Match, Participant, Snapshot, Metrics
│  │  ├─ riot/                 # client, rate_limiter, routing, parsers
│  │  ├─ timeline/             # enrichment, dragon_setups, objective_vision, quests
│  │  ├─ metrics/              # agregados, radar, benchmarks, umbrales semánticos
│  │  ├─ store/                # DuckDB: caché de partidas y consultas analíticas
│  │  └─ cli.py                # ygg fetch / ygg stats → JSON
│  └─ tests/
├─ apps/api/                   # FastAPI: HTTP, auth, persistencia, jobs
│  ├─ app/{routers,schemas,db,auth,jobs}
│  └─ tests/
├─ apps/web/                   # React 19 + TS + Vite
│  └─ src/{routes,features,components,lib,styles}
├─ infra/
│  ├─ docker-compose.yml       # postgres + redis + api + worker + web
│  └─ Dockerfile.{api,web}
└─ docs/                       # architecture.md, adr/, metrics.md
```

**Principio rector:** `ygg-core` no importa nada de FastAPI ni de SQLAlchemy. Recibe datos, devuelve objetos de dominio y métricas. Eso permite testearlo sin base de datos, usarlo desde la CLI, y que la API sea una capa fina de HTTP + persistencia. Es también la respuesta corta y convincente a «cuéntame la arquitectura de tu proyecto».

**Flujo de un análisis, ya corregido:**

```
POST /snapshots  ──▶  crea job (con user_id) en Postgres  ──▶  encola en Redis
                                                                    │
   SSE /snapshots/jobs/{id}/stream  ◀── progreso ──┐            worker ARQ
                                                    └──  ygg-core: Riot + timeline + métricas
                                                                    │
                                                          persiste matches + participants
```

### Capa de datos

Decisión tomada tras evaluar alternativas (SQLModel, Tortoise, Piccolo, asyncpg a pelo): **seguimos con SQLAlchemy, pero con la API 2.0 y asíncrona.** El código actual usa el estilo 1.x de hace casi veinte años —`Column(Integer, primary_key=True)`, `db.query(Match).filter(...).first()`, `Session` síncrona—, y ahí nacen tanto la incomodidad al escribirlo como el `DetachedInstanceError` que hay comentado en `snapshots.py`. La versión instalada (2.0.35) ya permite otra cosa:

```python
class MatchParticipant(Base):
    __tablename__ = "match_participants"
    id:         Mapped[int] = mapped_column(primary_key=True)
    match_id:   Mapped[str] = mapped_column(ForeignKey("matches.match_id"), index=True)
    puuid:      Mapped[str] = mapped_column(index=True)
    champion:   Mapped[str]
    cs_diff_14: Mapped[int | None]

stmt = select(MatchParticipant).where(MatchParticipant.puuid == puuid)
participants = (await session.scalars(stmt)).all()
```

Tipado que mypy y el editor entienden de verdad, `select()` en lugar de `.query()`, y `AsyncSession`. Cambiar de ORM costaría dos días y dejaría un stack menos empleable: SQLAlchemy es el que aparece en las ofertas, y el único con un sistema de migraciones realmente maduro (Alembic).

**Tres capas con responsabilidades separadas:**

| Capa | Herramienta | Qué hace |
|---|---|---|
| CRUD transaccional | SQLAlchemy 2.0 ORM + `AsyncSession` | Usuarios, jugadores, snapshots, jobs. El código aburrido donde el ORM gana |
| Consultas analíticas | **SQL escrito a mano** (`text()` o asyncpg directo) | Agregados por rol, percentiles, series temporales, `INSERT ... ON CONFLICT` masivos. Donde el ORM estorba y genera consultas malas |
| Análisis local | **DuckDB** dentro de `ygg-core` | Columnar, agregados sobre miles de partidas en milisegundos, lectura/escritura de Parquet, embebido sin servidor |

Postgres sigue siendo la base de datos de la aplicación; DuckDB es el motor analítico del core, no un reemplazo. Esa separación entre almacenamiento transaccional y analítico es un concepto de arquitectura con peso en una entrevista, y el SQL a mano diferencia bastante más que saber manejar un ORM.

Las consultas analíticas van en ficheros `.sql` versionados bajo `apps/api/app/queries/`, cargados con nombre y con test propio: quedan revisables en los PRs y no enterradas en cadenas dentro del código Python.

---

## 3. Fases

Cada fase termina en una rama mergeable, con tests en verde y CI pasando. El orden no es negociable en un punto: **la Fase 2 va antes del frontend**, porque reescribir la UI sobre un modelo de datos que atribuye estadísticas al jugador equivocado es trabajo tirado.

### Fase 0 — Red de seguridad (día 1)

| Tarea | Detalle |
|---|---|
| Repo | **Un solo repo, el que ya existe, renombrado a `ygg`** — el historial desde el TFG es parte del portfolio y dos repos romperían la generación de tipos TS desde el OpenAPI. Localizar el remoto o `git init` + primer commit con el código actual. Rama `main` protegida, trabajo en ramas `feat/*`. |
| Conservar el TFG | `git tag -a v1.0-tfg` + release en GitHub antes de tocar nada. El estado entregado queda consultable para siempre sin necesidad de un segundo repositorio. |
| Auditoría de secretos | `gitleaks detect` / `trufflehog git file://.` sobre todo el historial **antes de hacer público el repo**. Si alguna vez se commiteó la clave de Riot, el `SECRET_KEY` del JWT o la *service key* de Supabase, rotarlas y evaluar `git filter-repo`. |
| Monorepo | Mover a la estructura de arriba con `git mv` (no copiar y borrar, para que `git log --follow` siga el rastro). Solo mover: sin tocar código todavía. |
| Limpieza | El cliente Flutter sale de `main` cuando el de React funcione (Fase 5); queda preservado en la etiqueta `v1.0-tfg`. Dos frontends en el repo activo leen como desorden. |
| Docker | `docker-compose.yml` con postgres + redis; `make up` levanta todo. |
| CI | Reescribir el workflow: lint → tests backend → tests web → build. El build de escritorio/APK se mantiene, pero deja de ser lo único. |
| Calidad | `ruff` + `mypy` en modo gradual sobre `ygg-core`, `pre-commit` con ambos. |
| Config | `pydantic-settings` con `Settings` por entorno; `.env.example` completo; documentar cada variable. |
| Quick wins | Quitar `Base.metadata.create_all` (P14) · CORS con lista explícita de orígenes (P4) · `datetime.now(timezone.utc)` en `RankCutoff` (P17) · añadir `LIMIT` a `get_history_from_cache` (P8). |

**Hecho cuando:** `git clone && make up` arranca la API con base de datos y Redis, y el CI ejecuta los ~75 KB de tests que hoy nadie corre.

**Para el CV:** «Monorepo con CI en GitHub Actions, entorno reproducible con Docker Compose y tipado estático verificado.»

### Fase 1 — Extraer `ygg-core` (días 2-4)

Mover, no reescribir: `riot_client.py`, `riot_rate_limiter.py`, `role_quest_parser.py`, `ddragon_client.py` y la parte de cálculo de `dashboard_service.py` pasan a `packages/ygg-core`, y se les quitan las dependencias de SQLAlchemy.

- Definir dataclasses de dominio (`MatchData`, `ParticipantStats`, `TimelineMetrics`, `RadarProfile`) que hoy están implícitas en el modelo ORM.
- El cliente de Riot deja de devolver objetos `Match` del ORM: devuelve dominio. El mapeo dominio→ORM vive en `apps/api`.
- `dashboard_service` se divide: el cálculo (radar, techos por rol, `check_status`, benchmarks) va al core; la carga de datos se queda en la API.
- CLI mínima: `ygg fetch <riot-id> --from --to --json` y `ygg stats <fichero.json>`. Es tu herramienta de depuración y además hace el paquete demostrable sin arrancar nada.
- **Caché y analítica local con DuckDB** en `ygg_core/store/`: las partidas descargadas se guardan en Parquet y se consultan con SQL columnar. Iteras sobre las métricas sin volver a pedir nada a Riot y sin gastar cuota, y un agregado sobre miles de partidas tarda milisegundos. Las fórmulas del radar y los umbrales semánticos se validan aquí antes de tocar la API.
- Tests del core **sin base de datos**, con fixtures JSON de partidas reales anonimizadas.

**Hecho cuando:** `pytest packages/ygg-core` pasa sin Postgres levantado y la API importa el core en vez de tener la lógica dentro.

**Para el CV:** «Extraje el motor de análisis a un paquete Python independiente y testeable, con CLI propia y DuckDB como motor analítico embebido; la API quedó como capa de transporte.»

### Fase 2 — Corregir el modelo de datos (días 5-7)

El cambio central de todo el plan: partir la tabla ancha de ~70 columnas.

```
matches                    # la partida: match_id, creation_time, duration, patch, queue_id
match_participants         # un participante: (match_id, puuid) UNIQUE
                           #   champion, rol, kills/deaths/assists, cs, oro, daño,
                           #   diffs 8/14/25, solo_kills, quest_*, death_events, ward_events
match_snapshots            # N:M snapshot ↔ participante (no ↔ partida)
```

- Migración Alembic en tres pasos: crear tablas nuevas → copiar datos (`match_data` → `matches` + `match_participants`, usando `player_role`/`champion` existentes) → eliminar la vieja. Con script de verificación de conteos antes del `drop`.
- **Reescribir los modelos en estilo SQLAlchemy 2.0** aprovechando que los vas a tocar de todas formas: `Mapped[tipo]` + `mapped_column()` en lugar de `Column()`, y `select()` en lugar de `db.query()` en todo el CRUD. Con esto mypy empieza a detectar errores de tipos en las consultas, y desaparece la clase de fallos del `DetachedInstanceError`.
- **Decidir qué hacer con los JSON.** `death_events`, `ward_events` y `dragon_setups` son hoy columnas JSON. Mantenerlos como `JSONB` está bien si solo los lees enteros para pintar el mapa de calor; si quieres consultarlos (por ejemplo «muertes en el minuto 8 en el río del lado azul»), necesitan tabla propia `match_events (match_id, puuid, tipo, minuto, x, y)` con índice. Mi recomendación: `JSONB` ahora, y tabla de eventos solo si llegas a la mejora de detección de patrones.
- Eliminar `copy_timeline_fields` como mecanismo de reutilización entre jugadores: ahora cada jugador tiene su propia fila de participante y el timeline enriquecido se comparte a nivel de partida.
- Añadir `user_id` a `jobs` y comprobar propiedad en el endpoint de estado (**P2**).
- Índices: `(puuid, creation_time DESC)` para historial, `(snapshot_id)` en la N:M, `(match_id)` en participantes.
- Persistencia en lote: `INSERT ... ON CONFLICT DO UPDATE` en vez del bucle de `db.query` por partida (**P8**).
- Test de regresión explícito: dos jugadores registrados, misma partida, cada uno ve sus propias estadísticas. Ese test es la prueba de que **P1** está cerrado.

**Hecho cuando:** el test de los dos jugadores en la misma partida pasa, y los datos existentes sobreviven a la migración.

**Para el CV:** Esta es tu mejor historia técnica. «Detecté que el modelo de datos colapsaba las estadísticas de varios jugadores en una misma partida; rediseñé el esquema separando partida y participante, con migración de datos en producción verificada y un test de regresión que fija el comportamiento.»

### Fase 3 — API endurecida (días 8-10)

| Área | Cambio |
|---|---|
| Async real | `create_async_engine` + `asyncpg` + `AsyncSession`; todos los endpoints `async`. Adiós al bloqueo del event loop (**P7**). Pool dimensionado según el plan del hosting, no el 5 por defecto. |
| SQL analítico | Las consultas de agregados salen del ORM a ficheros `.sql` en `app/queries/`, ejecutados con `text()` y con test propio que compara su resultado contra el cálculo de `ygg-core`. Ahí se van también los `INSERT ... ON CONFLICT` masivos. |
| Auth | PyJWT en lugar de python-jose. Access token corto (15 min) + **refresh token en cookie `httpOnly`, `Secure`, `SameSite=Lax`** con rotación y tabla de revocación. El frontend deja de tocar el token (**P5**). |
| Contraseñas | Política única y compartida: mínimo 10 caracteres, validada en registro y en cambio. |
| Rate limiting | `slowapi` o middleware propio con Redis: global por IP, y límite estricto en `/auth/login` (**P6**) y en `POST /snapshots/`. |
| Contratos | `response_model` en **todos** los endpoints, incluido el dashboard (**P9**). Paginación en historial y listados. |
| Caché | Dashboard en Redis con clave `snapshot_id + versión de esquema`, invalidada al añadir partidas al snapshot. |
| Data Dragon | Caché en Redis + URLs directas al CDN de Riot, eliminando el `StaticFiles` sobre disco efímero (**P10**). |
| Observabilidad | `structlog` con JSON y request-id, Sentry para errores, `/health` comprobando Postgres y Redis, `/metrics` en formato Prometheus (**P15**). |
| OpenAPI | Esquema completo y limpio; se convierte en la fuente de los tipos TypeScript del frontend. |

**Hecho cuando:** el OpenAPI describe el 100 % de la API, `ab`/`k6` muestran latencia estable bajo concurrencia, y `/health` falla de verdad si Postgres cae.

**Para el CV:** «Migré a SQLAlchemy 2.0 asíncrono con las consultas analíticas en SQL a mano, sustituí el JWT en localStorage por refresh tokens en cookie httpOnly con rotación, y añadí rate limiting, caché en Redis y logging estructurado con trazabilidad por petición.»

### Fase 4 — Jobs fuera del proceso (días 11-12)

- Worker con **ARQ** (async, encaja con el stack; Celery es más pesado y no aporta aquí) sobre Redis.
- `POST /snapshots/` encola y devuelve `job_id`; el worker ejecuta `ygg-core` y escribe progreso en Redis + Postgres.
- Reintentos con backoff, *heartbeat*, y recuperación de jobs huérfanos al arrancar el worker: si un job quedó `processing` sin heartbeat, se marca `failed` y se puede reintentar (**P3**).
- **Progreso por SSE** (`GET /snapshots/jobs/{id}/stream`) sustituyendo el polling cada 2 s. SSE y no WebSockets: el flujo es unidireccional, se reconecta solo y funciona sobre HTTP normal.
- Idempotencia: encolar dos veces el mismo (jugador, rango) reutiliza el job en curso.

**Hecho cuando:** matas el contenedor de la API a mitad de análisis, el job sobrevive y el navegador sigue recibiendo progreso.

**Para el CV:** «Saqué el procesamiento a un worker con cola Redis, con reintentos, recuperación de trabajos huérfanos y progreso en tiempo real vía Server-Sent Events.»

### Fase 5 — Frontend React (días 13-19)

**Stack**

| Pieza | Elección | Por qué |
|---|---|---|
| Base | React 19 + TypeScript (`strict`) + Vite | Lo que piden las ofertas junior |
| Routing | React Router 7 con rutas anidadas y `lazy` | Resuelve **P12**: URLs reales y enlaces compartibles |
| Datos | TanStack Query | Caché, reintentos, invalidación y estados de carga sin escribirlos a mano |
| Tipos | `openapi-typescript` + `openapi-fetch` desde el OpenAPI de la API | Cliente tipado generado: si cambias el backend, el front deja de compilar |
| Estilos | Tailwind v4 con los tokens Hextech como variables CSS | La paleta ya está en HSL documentada |
| Componentes | shadcn/ui (Radix) | Accesibilidad de serie en diálogos, tooltips y menús |
| Gráficas | Recharts para radar/líneas/barras; SVG propio para el mapa de calor | Equivalentes de `fl_chart` con mejor rendimiento en DOM |
| Tablas | TanStack Table + virtualización | El historial y el panel de admin son tablas grandes |
| Tests | Vitest + Testing Library; Playwright para el flujo crítico | |

**Mapa de rutas**

```
/login                                  público
/players                                tabla de jugadores
/players/:id                            detalle: historial, campeones, rango
/players/:id/snapshots/:snapshotId      dashboard del snapshot (radar, métricas, partidas)
/players/:id/snapshots/compare?a=&b=    comparar dos snapshots
/cutoffs                                cortes de rango
/admin/(users|players|stats)            solo rol admin
/s/:publicToken                         snapshot público compartible (opcional, Fase 6)
```

Todo el estado visible —snapshot abierto, rol filtrado, métrica seleccionada, pestaña— va en la URL como *search params*. Es lo que convierte la app en algo que se puede enseñar con un enlace.

**Orden de trabajo**

1. **Días 13-14 — Cimientos.** Vite, Tailwind con tokens, layout, router, cliente generado, capa de auth con cookie y refresh silencioso, `ProtectedRoute`, formulario de login con validación (`react-hook-form` + `zod`).
2. **Día 15 — Jugadores.** Tabla con ordenación y virtualización, alta de jugador con validación contra Riot, badges de rango, chips de rol, refresco de rango.
3. **Días 16-17 — Dashboard del snapshot.** La pantalla estrella: radar con datasets (jugador / challenger / cuenta comparada), tarjetas de métricas coloreadas por el `status` semántico del backend —el helper de `FRONTEND_COLOR_GUIDE.md` se traduce tal cual a TypeScript—, tabla de partidas con tooltips de objetos y runas, y mapa de calor de muertes y wards en SVG sobre el minimapa.
4. **Día 18 — Creación de snapshots y admin.** Selector de rango de fechas, barra de progreso alimentada por SSE con reconexión, y panel de admin (usuarios, jugadores, estadísticas globales) partido en componentes pequeños: los 49 KB de `admin_users.dart` no se replican en un solo fichero.
5. **Día 19 — Pulido web.** Estados de carga con *skeletons*, estados vacíos y de error con reintento, `prefers-reduced-motion`, navegación por teclado, `aria` en las gráficas con tabla de datos alternativa, y responsive real de 360 px a 2560 px.

**Presupuesto de rendimiento** (lo mides y lo pones en el README):

- JS inicial < 200 KB comprimido; rutas en *chunks* aparte.
- LCP < 2,0 s y CLS < 0,05 en 4G simulada.
- Lighthouse ≥ 95 en Performance, Accessibility y Best Practices.
- Los badges de rango pasan a WebP/AVIF con sprite SVG para los roles: de ~4 MB a menos de 200 KB (**P11**).

**Hecho cuando:** las cuatro pantallas funcionan contra la API real, Playwright cubre login → crear snapshot → ver dashboard, y el presupuesto de rendimiento se cumple.

**Para el CV:** «Reescribí el cliente en React 19 + TypeScript con cliente HTTP generado desde OpenAPI, estado de servidor con TanStack Query, rutas profundas y presupuesto de rendimiento verificado con Lighthouse.»

### Fase 6 — Deploy y demo pública (días 20-22)

**Infraestructura**

| Componente | Dónde | Notas |
|---|---|---|
| Web | Vercel o Cloudflare Pages | Estático + cabeceras de caché y CSP |
| API + worker | Fly.io o Railway | Render free duerme la instancia; si te quedas, paga el plan que no duerme o acepta el arranque en frío |
| Postgres | Supabase (ya lo usas) | |
| Redis | Upstash | Plan gratuito suficiente para cola y caché |

- Dominio propio (`ygg.tudominio.dev`) con HTTPS. Un dominio propio en el CV se nota.
- CSP estricta, `Strict-Transport-Security`, `X-Content-Type-Options`, `Referrer-Policy`.
- Pipeline de deploy: merge a `main` → tests → migraciones → deploy API → deploy web, con *rollback* documentado.

**Clave de Riot**

La clave de desarrollo caduca cada 24 horas, así que la demo no puede depender de ella:

1. Solicitar la **Personal API Key** en el portal de desarrolladores de Riot: requiere describir el proyecto, tener una URL pública funcionando y cumplir su política de uso (sin monetización, atribución correcta). La aprobación tarda días o semanas, así que **este trámite se inicia el día 1, no en la Fase 6**.
2. Hasta que llegue (y como red de seguridad permanente si se revoca): **modo demo**. Base de datos sembrada con snapshots reales anonimizados, usuario `demo` de solo lectura con credenciales visibles en la landing, y una bandera `DEMO_MODE` que desactiva las llamadas a Riot sirviendo los datos sembrados. El enlace del CV nunca se cae en medio de una entrevista.
3. Cuota y coste: con la clave personal, limitar a N análisis por usuario y día para no quemar la cuota, reutilizando agresivamente la caché de partidas que ya tienes.

**Hecho cuando:** un enlace público abre la app, el usuario demo entra y ve un dashboard completo, y el arranque en frío no supera los 3 s.

### Fase 7 — Empaquetado para el portfolio (días 23-25)

Esta fase es la que convierte trabajo técnico en entrevistas. No la recortes.

1. **README como escaparate:** captura o GIF arriba, enlace a la demo con credenciales, qué problema resuelve y para quién, diagrama de arquitectura, decisiones técnicas con su por qué, y `docker compose up` como única instrucción para levantarlo.
2. **`docs/adr/`:** cinco o seis decisiones en una página cada una (por qué separar partida y participante, por qué SQLAlchemy 2.0 en vez de SQLModel o Tortoise y por qué SQL a mano en la analítica, por qué DuckDB en el core junto a Postgres, por qué ARQ y no Celery, por qué SSE y no WebSockets, por qué cookie httpOnly y no localStorage). Un junior que documenta decisiones destaca inmediatamente.
3. **`docs/metrics.md` con antes/después medido:** latencia p95 del dashboard, tiempo de análisis de 100 partidas, JS inicial, Lighthouse, cobertura de tests. Números concretos, no adjetivos.
4. **Vídeo de 60-90 s** sin audio, con subtítulos: login → añadir jugador → crear snapshot con progreso en vivo → dashboard → comparar. Va en el README y en LinkedIn.
5. **Entrada del CV**, en dos líneas y con cifras:

   > **YGG — Plataforma de análisis de rendimiento en League of Legends** · React 19, TypeScript, FastAPI, SQLAlchemy 2.0 async, PostgreSQL, DuckDB, Redis, Docker · [demo] [código]
   > Análisis de partidas sobre la API de Riot con enriquecimiento de timeline (diferenciales de oro/CS/XP, control de visión de objetivos, mapas de calor). Rediseñé el esquema de datos para soportar varios jugadores por partida, saqué el procesamiento a un worker con cola Redis y progreso por SSE, y reescribí el cliente en React con un cliente HTTP generado desde OpenAPI. Lighthouse 95+, p95 del dashboard bajo X ms.

6. **Prepara tres historias** para la entrevista, cada una con contexto → problema → decisión → resultado: el bug del modelo de datos, el rate limiter global ante los 429 de Riot, y la migración de jobs en proceso a cola externa.

---

## 4. Mejoras de producto (opcionales, por valor/esfuerzo)

Si sobra tiempo o quieres seguir después. Lo primero de la lista es lo que más impresiona por lo poco que cuesta.

| Mejora | Esfuerzo | Por qué merece la pena |
|---|---|---|
| **Comparar dos snapshots del mismo jugador** (evolución entre fechas) | Bajo | El backend ya calcula todo; es una ruta y un radar con dos datasets. Y es *la* pregunta que se hace un entrenador |
| **Snapshot público compartible** (`/s/:token`, solo lectura) | Bajo | Hace el proyecto viral-demostrable: pegas un enlace en el CV que abre datos reales sin login |
| **Tendencia temporal de métricas** (serie por partida con media móvil) | Medio | Convierte fotos fijas en progresión; es lo que hace útil la herramienta |
| **Informe PDF del snapshot** | Medio | Entregable tangible para un equipo; y te hace tocar generación de documentos |
| **Vista de equipo** (5 jugadores, fortalezas y huecos por rol) | Alto | El paso natural del scouting individual al competitivo — y solo es posible **después** de arreglar P1 |
| **Detección de patrones** (muertes repetidas en la misma zona y minuto) | Alto | Usa los `death_events` con coordenadas que ya guardas; es análisis de verdad |

---

## 5. Riesgos

| Riesgo | Mitigación |
|---|---|
| La Personal API Key de Riot tarda o se deniega | Solicitarla el día 1 y construir el modo demo con datos sembrados como camino garantizado |
| La migración de datos de la Fase 2 corrompe lo existente | Migración en tres pasos, script de verificación de conteos antes del `drop`, *dump* previo de la base |
| La reescritura del frontend se alarga | Congelar alcance en las 4 pantallas actuales; las mejoras de producto son explícitamente posteriores |
| Riot cambia el formato de partida (parches, temporada 27) | Fixtures JSON versionadas en `ygg-core` y parseo tolerante a campos ausentes (ya lo haces con las Role Quests) |
| Quedarte sin cuota de API en la demo | Caché agresiva, límite por usuario y día, y `DEMO_MODE` sirviendo datos sembrados |
| Abandonar a mitad y quedarte con un repo peor que el actual | Cada fase acaba en rama mergeable con tests verdes: si paras, paras en un estado publicable |

---

## 6. Primeras acciones concretas

Para empezar hoy mismo, en este orden:

1. **Solicitar la Personal API Key de Riot.** Es lo único con latencia externa; cada día que tardes en pedirla lo pierdes al final.
2. **Localizar el repositorio git.** La carpeta local no tiene `.git` pese a tener workflows de GitHub: confirma dónde está el remoto, o inicializa y súbelo.
3. **Volcado de la base de datos de producción** a un fichero local. Es la red de seguridad de la Fase 2 y lo necesitas antes de tocar nada.
4. **Crear la rama `feat/monorepo`** y ejecutar la Fase 0.
5. **Medir la línea base antes de cambiar nada:** p95 del dashboard, tiempo de análisis de 100 partidas, tamaño del bundle web actual. Sin estos números, el «después» de la Fase 7 no significa nada.
