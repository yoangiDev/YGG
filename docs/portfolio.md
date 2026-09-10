# Portfolio

Material para el CV y las entrevistas. Todas las cifras salen de [`metrics.md`](metrics.md).

## Entrada del CV

> **YGG, análisis de rendimiento en League of Legends** · React 19, TypeScript, FastAPI, SQLAlchemy 2.0 async,
> PostgreSQL, DuckDB, Redis, Docker · [demo] [código]
>
> Plataforma de scouting sobre la API de Riot con enriquecimiento de timeline (diferenciales de oro, CS y
> experiencia, visión en objetivos, mapas de calor de muertes). Rediseñé el modelo de datos para varios
> jugadores por partida, saqué los análisis a un worker con cola Redis y progreso por SSE, y reescribí el
> cliente en React con un cliente HTTP generado desde OpenAPI: 126 KB de JS inicial, dashboard en 4 ms (p95)
> con caché, 90 % de cobertura en el motor de análisis y 82 % en la API.

Versión de una línea: *Plataforma de análisis de League of Legends: FastAPI + worker ARQ + React/TypeScript,
con modelo de datos rediseñado, progreso en tiempo real por SSE y CI con tests y presupuesto de rendimiento.*

## Historias para entrevista

Formato: contexto → problema → decisión → resultado.

### 1. El bug que no daba errores (modelo de datos)

- **Contexto.** El TFG guardaba cada partida como una fila asociada al jugador analizado, y reutilizaba las
  partidas ya descargadas para no gastar cuota de Riot.
- **Problema.** La caché buscaba por `match_id`. Si dos jugadores seguidos habían jugado la misma partida, el
  segundo heredaba las estadísticas del primero: otro campeón, otro KDA, otras muertes. Nada fallaba; los
  números simplemente eran de otra persona.
- **Decisión.** Separar `matches` de `match_participants` con clave única `(match_id, puuid)`, y hacer que la
  caché busque siempre por jugador. Migración en tres pasos (crear, copiar, verificar conteos antes de borrar)
  para no perder datos. [ADR 0001](adr/0001-partida-y-participante.md)
- **Resultado.** Un test fija el caso de dos jugadores en la misma partida. Como efecto secundario, las
  escrituras pasaron a lotes con `ON CONFLICT` y un análisis reutiliza cualquier partida ya guardada de ese
  jugador.

### 2. Los 429 de Riot (limitador global)

- **Contexto.** Riot limita por clave: 20 peticiones por segundo y 100 cada dos minutos con la clave de
  desarrollo. Un análisis descarga la partida y el timeline de cada partida en paralelo.
- **Problema.** Si cada descarga controla su propio ritmo, varias en paralelo superan juntas el límite. Llegan
  429 en cascada y los reintentos inmediatos empeoran la situación.
- **Decisión.** Un único limitador en `ygg-core`, compartido por todo el proceso, con dos ventanas deslizantes
  (1 s y 2 min) que reservan hueco *antes* de pedir. Ante un 429, pausa global coordinada con el `Retry-After`,
  en lugar de que cada petición reintente por su cuenta.
- **Resultado.** Las descargas se reparten dentro de la cuota en vez de chocar con ella. El tiempo de un
  análisis grande lo marca la cuota (100 partidas nuevas ≈ 4 minutos con la clave de desarrollo) y es
  predecible.

### 3. Los trabajos que se perdían (cola externa)

- **Contexto.** Los análisis se lanzaban con `asyncio.create_task` dentro de la API y el cliente preguntaba
  por su estado cada pocos segundos.
- **Problema.** Cualquier reinicio o despliegue dejaba trabajos en «procesando» para siempre. Además, conociendo
  un id se podía consultar el trabajo de otro usuario.
- **Decisión.** Worker ARQ aparte, con Postgres como fuente de verdad: heartbeat cada 10 s, un cron que marca
  como interrumpidos los trabajos sin latido, idempotencia con un índice único parcial y reintentos solo ante
  errores de Riot. El progreso va por Redis pub/sub y SSE. [ADR 0004](adr/0004-arq-y-no-celery.md),
  [ADR 0005](adr/0005-sse-y-no-websockets.md)
- **Resultado.** Matar el worker a mitad ya no deja zombis: el usuario ve el error y reintenta. La API no se
  resiente mientras se analiza, y el progreso llega en cuanto ocurre en lugar de cada intervalo de sondeo.

### 4. Medir antes de optimizar (rendimiento web)

- **Contexto.** Presupuesto de la reescritura: LCP por debajo de 2 s en 4G lenta.
- **Problema.** La primera medida dio 3,1 s en el dashboard. Comprimir los ficheros apenas cambió nada.
- **Decisión.** Guardar en la prueba de rendimiento qué elemento es el LCP y la cascada de recursos. Mostró que
  cada página no pedía sus datos hasta descargar todas sus dependencias, incluidas Recharts y zod para un
  diálogo cerrado. Separé en chunks el marco de la app, los diálogos, las gráficas y la tabla.
- **Resultado.** Dashboard de 3,08 s a 2,34 s, lista de jugadores de 2,08 s a 1,96 s y JS inicial de 156 KB a
  126 KB. El dashboard aún está 340 ms por encima del objetivo, y está documentado qué falta.
