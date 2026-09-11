# 0002 · SQLAlchemy 2.0 async y SQL a mano para la analítica

**Estado:** aceptada · **Fase:** 3 · **Resuelve:** P7, P8

## Contexto

La API usaba el ORM síncrono dentro de endpoints `async`: cada consulta bloqueaba el event loop, y
un análisis largo congelaba al resto de usuarios (P7). Además, guardar un snapshot hacía una consulta
por partida (P8).

## Decisión

- **SQLAlchemy 2.0 con modelos tipados** (`Mapped[...]`, `mapped_column`) y `AsyncSession` sobre
  asyncpg. Alembic sigue siendo el único dueño del esquema.
- **Escrituras en lote** con `INSERT … ON CONFLICT` de `sqlalchemy.dialects.postgresql`, en trozos
  de 500 filas: unas pocas sentencias por análisis, tenga las partidas que tenga.
- **Consultas analíticas en SQL a mano** (`app/queries/*.sql`): resúmenes por rol y agregados de
  snapshot con `FILTER`, `percentile_cont` y ventanas. `tests/test_queries.py` comprueba que dan lo
  mismo que las fórmulas de `ygg-core`.

## Alternativas

- **SQLModel.** Une modelo de tabla y esquema de API en una clase. Cómodo al principio, pero aquí los
  contratos de la API (paginación, campos calculados) y las tablas divergen, y va por detrás de
  SQLAlchemy 2.0 en tipado y soporte async.
- **Tortoise ORM.** Async de nacimiento, pero con un ecosistema menor y migraciones con Aerich en lugar
  de Alembic, que ya estaba en el proyecto.
- **Todo con el ORM.** Las agregaciones con `func.percentile_cont` y `FILTER` son más difíciles de leer
  en Python que en SQL, y el SQL es lo que luego se revisa con `EXPLAIN`.

## Consecuencias

- La API no bloquea el loop; el dashboard caliente responde en milisegundos
  ([`metrics.md`](../metrics.md)).
- Con `AsyncSession` no hay carga perezosa: las relaciones que se usan se cargan explícitamente
  (`lazy="joined"`, `selectinload`). Es más código, pero hace visible cada consulta.
- El SQL a mano se prueba contra un Postgres real; los tests no pueden usar SQLite.
