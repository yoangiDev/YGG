import { useEffect, useState } from "react";

import { api, API_URL, ApiError, isApiError, refreshAccessToken, tokenStore, unwrap, type Schemas } from "@/lib/api/client";
import { SseParser } from "@/lib/sse";

export type JobStatus = Schemas["SnapshotJobStatus"];

export function isTerminal(status: JobStatus["status"]): boolean {
  return status === "done" || status === "error";
}

const RETRY_BASE_MS = 2000;
const RETRY_MAX_MS = 10_000;

/** Función y no `signal.aborted` directo: TypeScript estrecha la propiedad y no ve que cambia durante los await. */
function isAborted(signal: AbortSignal): boolean {
  return signal.aborted;
}

function sleep(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    const timer = setTimeout(resolve, ms);
    signal.addEventListener(
      "abort",
      () => {
        clearTimeout(timer);
        resolve();
      },
      { once: true },
    );
  });
}

/** EventSource no permite la cabecera Authorization, así que el stream se abre con fetch. */
async function openStream(jobId: string, signal: AbortSignal): Promise<Response> {
  const url = `${API_URL}/snapshots/jobs/${encodeURIComponent(jobId)}/stream`;
  const request = (token: string | null) =>
    globalThis.fetch(url, {
      headers: token ? { Accept: "text/event-stream", Authorization: `Bearer ${token}` } : { Accept: "text/event-stream" },
      credentials: "include",
      signal,
    });

  const response = await request(tokenStore.get());
  if (response.status !== 401) return response;
  const token = await refreshAccessToken();
  return token ? request(token) : response;
}

/** Lee eventos hasta un estado final. Devuelve ese estado, o null si el servidor cerró antes. */
async function readStream(response: Response, onStatus: (status: JobStatus) => void): Promise<JobStatus | null> {
  if (!response.body) return null;
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const parser = new SseParser();
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) return null;
      for (const message of parser.feed(decoder.decode(value, { stream: true }))) {
        const status = JSON.parse(message.data) as JobStatus;
        onStatus(status);
        if (isTerminal(status.status)) return status;
      }
    }
  } finally {
    void reader.cancel().catch(() => undefined);
  }
}

/**
 * Sigue un análisis hasta que termina.
 *
 * Usa el stream SSE y, si se corta (un proxy que cierra conexiones largas, un
 * worker que se reinicia…), consulta el estado por HTTP y vuelve a conectar con
 * espera creciente. El servidor manda el estado actual al conectar, así que una
 * reconexión nunca pierde el final.
 */
export async function followJob(
  jobId: string,
  onStatus: (status: JobStatus) => void,
  signal: AbortSignal,
): Promise<JobStatus | null> {
  for (let failures = 1; !signal.aborted; failures++) {
    try {
      const response = await openStream(jobId, signal);
      if (response.ok) {
        const final = await readStream(response, onStatus);
        if (final) return final;
      } else if (response.status >= 400 && response.status < 500 && response.status !== 429) {
        throw new ApiError(response.status, response.status === 404 ? "This analysis does not exist." : "Cannot follow this analysis.");
      }
    } catch (error) {
      if (isAborted(signal)) return null;
      if (error instanceof ApiError) throw error;
    }

    try {
      const status = await unwrap(api.GET("/snapshots/jobs/{job_id}", { params: { path: { job_id: jobId } } }));
      onStatus(status);
      if (isTerminal(status.status)) return status;
    } catch (error) {
      if (isAborted(signal)) return null;
      if (isApiError(error) && error.status >= 400 && error.status < 500 && error.status !== 429) throw error;
    }

    await sleep(Math.min(RETRY_BASE_MS * failures, RETRY_MAX_MS), signal);
  }
  return null;
}

interface JobProgressState {
  jobId: string | null;
  status: JobStatus | null;
  error: unknown;
}

export function useJobProgress(jobId: string | null): { status: JobStatus | null; error: unknown } {
  const [state, setState] = useState<JobProgressState>({ jobId: null, status: null, error: null });

  useEffect(() => {
    if (!jobId) return;
    const controller = new AbortController();
    followJob(jobId, (status) => setState({ jobId, status, error: null }), controller.signal).catch((error: unknown) => {
      setState((current) => ({ ...current, jobId, error }));
    });
    return () => controller.abort();
  }, [jobId]);

  return state.jobId === jobId ? { status: state.status, error: state.error } : { status: null, error: null };
}
