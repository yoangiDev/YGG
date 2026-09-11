# 0005 · Server-Sent Events para el progreso

**Estado:** aceptada · **Fase:** 4-5

## Contexto

Mientras un análisis corre, el usuario quiere ver el progreso. El cliente Flutter consultaba
`GET /snapshots/jobs/{id}` en bucle: peticiones inútiles la mayor parte del tiempo y un retraso igual
al intervalo de sondeo. Con el trabajo fuera de la API (ADR 0004), el progreso lo produce otro proceso.

## Decisión

- El worker publica cada cambio en Redis: un canal pub/sub y una clave con el último estado.
- `GET /snapshots/jobs/{id}/stream` responde con **SSE** (`sse-starlette`). Al conectar envía primero el
  estado actual y después cada evento `progress`, `done` o `error`, con el mismo esquema que el endpoint
  de estado. Cualquier réplica de la API puede servir el stream.
- En la web, `EventSource` no permite la cabecera `Authorization`, así que el stream se lee con `fetch` y
  un parser propio (`src/lib/sse.ts`, probado con trozos partidos y comentarios de keep-alive). Si la
  conexión se corta, se consulta el estado por HTTP y se reconecta con espera creciente
  (`src/features/snapshots/jobProgress.ts`).

## Alternativas

- **WebSockets.** Bidireccionales, pero aquí solo habla el servidor. Exigen *upgrade* de la conexión,
  autenticar el *handshake* y, detrás de algunos proxies, configuración adicional.
- **Sondeo.** Lo que había: simple, pero con latencia fija y carga constante.
- **`EventSource` con el token en la query string.** Permitiría el reconectado nativo del navegador,
  pero el token acabaría en logs de acceso e historiales.

## Consecuencias

- El progreso llega en cuanto el worker lo publica, con una sola conexión HTTP por diálogo abierto.
- Es HTTP normal: pasa por CDNs y proxies, siempre que no almacenen en búfer las respuestas en streaming.
- La reconexión la implementa el cliente, pero como el servidor manda el estado actual al conectar,
  nunca se pierde el final de un trabajo.
