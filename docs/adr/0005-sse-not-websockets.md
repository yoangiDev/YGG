# 0005 · Server-Sent Events for progress

**Status:** accepted · **Phase:** 4-5

## Context

While an analysis runs, the user wants to see its progress. The Flutter client polled `GET /snapshots/jobs/{id}` in a loop:
useless requests most of the time and a delay equal to the polling interval. With the job outside the API (ADR 0004),
progress is produced by another process.

## Decision

- The worker publishes every change to Redis: a pub/sub channel and a key with the latest state.
- `GET /snapshots/jobs/{id}/stream` responds with **SSE** (`sse-starlette`). On connecting it first sends the current
  state and then each `progress`, `done` or `error` event, with the same schema as the status endpoint. Any API replica
  can serve the stream.
- On the web side, `EventSource` doesn't allow the `Authorization` header, so the stream is read with `fetch` and a
  parser of our own (`src/lib/sse.ts`, tested with split chunks and keep-alive comments). If the connection drops, the
  status is queried over HTTP and it reconnects with growing waits (`src/features/snapshots/jobProgress.ts`).

## Alternatives

- **WebSockets.** Bidirectional, but here only the server talks. They require a connection *upgrade*, authenticating the
  *handshake* and, behind some proxies, extra configuration.
- **Polling.** What there was: simple, but with a fixed latency and a constant load.
- **`EventSource` with the token in the query string.** It would allow the browser's native reconnection, but the token
  would end up in access logs and histories.

## Consequences

- Progress arrives as soon as the worker publishes it, with a single HTTP connection per open dialog.
- It is plain HTTP: it passes through CDNs and proxies, as long as they don't buffer streaming responses.
- Reconnection is implemented by the client, but since the server sends the current state on connecting, the end of a job
  is never lost.
