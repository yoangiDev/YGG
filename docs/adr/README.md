# Architecture Decision Records

Una decisión por fichero, en una página: contexto, decisión, alternativas y consecuencias.
Los problemas `P1`…`P17` son los del diagnóstico inicial de [`PLAN_WEB.md`](../../PLAN_WEB.md).

| ADR | Decisión | Estado |
|---|---|---|
| [0001](0001-partida-y-participante.md) | Separar partida y participante en el modelo de datos | Aceptada |
| [0002](0002-sqlalchemy-2-y-sql-a-mano.md) | SQLAlchemy 2.0 async para la aplicación y SQL a mano para la analítica | Aceptada |
| [0003](0003-duckdb-en-el-core.md) | DuckDB como almacén local de `ygg-core`, junto a Postgres | Aceptada |
| [0004](0004-arq-y-no-celery.md) | ARQ como cola de análisis, con Postgres como fuente de verdad | Aceptada |
| [0005](0005-sse-y-no-websockets.md) | Server-Sent Events para el progreso de los análisis | Aceptada |
| [0006](0006-cookie-httponly-y-no-localstorage.md) | Access token en memoria y refresh token en cookie httpOnly | Aceptada |
