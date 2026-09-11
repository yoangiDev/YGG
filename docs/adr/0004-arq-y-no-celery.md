# 0004 · ARQ como cola de análisis

**Estado:** aceptada · **Fase:** 4 · **Resuelve:** P2, P3

## Contexto

Crear un snapshot descarga decenas de partidas y timelines respetando los límites de Riot: minutos de
trabajo. Se lanzaba con `asyncio.create_task` dentro del proceso de la API. Un reinicio o un despliegue
perdía los trabajos en curso, que se quedaban para siempre en `processing` (P3). Además, cualquiera que
conociera un `job_id` podía consultar su estado (P2).

## Decisión

- **ARQ sobre Redis** ejecuta los análisis en un proceso aparte (`arq app.jobs.worker.WorkerSettings`).
- **La tabla `jobs` de Postgres es la fuente de verdad**, no Redis: guarda parámetros, dueño, intentos,
  progreso y un `heartbeat_at` que el worker actualiza cada 10 s.
- **Recuperación de huérfanos**: un cron cada minuto marca como interrumpidos los trabajos sin heartbeat
  durante 60 s y vuelve a encolar los que Redis perdió. El usuario ve el error y puede reintentar.
- **Idempotencia**: un índice único parcial sobre los trabajos activos hace que pedir dos veces el mismo
  análisis (mismo jugador y rango) devuelva el mismo trabajo.
- **Reintentos** con espera creciente solo ante `RiotUnavailableError` (hasta 3 intentos): un 5xx de Riot
  se reintenta; un error de datos no.
- Todos los endpoints de trabajos comprueban el dueño.
- En desarrollo sin Redis, `InlineJobQueue` ejecuta el trabajo en el propio proceso con la misma interfaz.

## Alternativas

- **Celery.** El estándar, pero pensado para código síncrono: el cliente de Riot es `aiohttp` y habría que
  envolver cada tarea en un event loop. Además añade broker, backend de resultados y bastante configuración.
- **RQ / Dramatiq.** Más ligeros que Celery, también síncronos.
- **Tabla de Postgres con `SELECT … FOR UPDATE SKIP LOCKED`.** Sin Redis, pero habría que escribir
  a mano el sondeo, los reintentos y el cron.

## Consecuencias

- Matar el worker a mitad de un análisis ya no deja trabajos zombis (`tests/test_jobs.py`).
- La API y el worker escalan por separado; un análisis pesado no afecta a la latencia de la API.
- ARQ tiene una comunidad pequeña. La interfaz `JobQueue` (`app/jobs/queue.py`) aísla el cambio si hubiera
  que sustituirlo.
- Redis pasa a ser obligatorio en producción (ya lo era para caché y rate limiting).
