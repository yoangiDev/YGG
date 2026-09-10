# 0003 · DuckDB en `ygg-core`, junto a Postgres

**Estado:** aceptada · **Fase:** 1

## Contexto

El análisis (cliente de Riot, enriquecimiento con timeline, métricas) estaba repartido por servicios
de FastAPI. Para probarlo o experimentar con una métrica nueva había que levantar la API, Postgres y
autenticarse. Al extraerlo a `packages/ygg-core` (paquete Python puro, sin FastAPI ni SQLAlchemy) hacía
falta un sitio donde guardar partidas mientras se trabaja fuera de la aplicación.

## Decisión

`ygg-core` incluye `MatchStore` (`store/duckdb_store.py`), un almacén DuckDB en un único fichero que:

- cachea los JSON crudos de Riot (partida y timeline), de modo que un cambio en los parsers se aplica
  con `ygg reparse` sin volver a gastar cuota de API;
- guarda los `ParticipantStats` en una tabla cuyo esquema se deriva de las anotaciones del dataclass,
  así que no puede desincronizarse;
- admite SQL ad hoc, resumen por rol y exportación/importación a Parquet.

La CLI (`ygg fetch | stats | store | reparse`) trabaja sobre ese fichero. Postgres sigue siendo la base
transaccional de la aplicación web: usuarios, jugadores, snapshots y trabajos.

## Alternativas

- **Postgres también en el core.** Obliga a tener un servidor para cualquier experimento y mezcla el
  dominio con la infraestructura de la API.
- **SQLite.** Igual de portable, pero orientado a filas: peor para agregaciones sobre miles de
  participantes y sin Parquet.
- **Ficheros Parquet sueltos con pandas.** Buenos para análisis, malos como caché incremental con
  upserts.

## Consecuencias

- El core se prueba sin servicios (121 tests, mypy estricto) y funciona como herramienta por sí mismo.
- Hay dos motores de almacenamiento, con papeles distintos: DuckDB local y analítico, Postgres
  compartido y transaccional. Las métricas se calculan con el mismo código Python en ambos casos.
- DuckDB es una dependencia opcional del core: la API no la importa.
