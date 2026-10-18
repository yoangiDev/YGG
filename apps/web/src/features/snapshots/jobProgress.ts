import { useEffect, useState, useSyncExternalStore } from "react";

import { api, API_URL, ApiError, isApiError, refreshAccessToken, tokenStore, unwrap, type Schemas } from "@/lib/api/client";
import { SseParser } from "@/lib/sse";

export type JobStatus = Schemas["SnapshotJobStatus"];

function isTerminal(status: JobStatus["status"]): boolean {
  return status === "done" || status === "error";
}

export function describeJob(status: JobStatus | null): string {
  if (!status) return "Connecting…";
  switch (status.status) {
    case "queued":
      return "Queued, waiting for a worker";
    case "processing":
      if (status.progress < 10) return "Finding ranked games";
      if (status.progress < 90) return "Downloading matches and timelines";
      return "Computing metrics";
    case "done":
      return "Analysis complete";
    case "error":
      return "Analysis failed";
  }
}

const RETRY_BASE_MS = 2000;
const RETRY_MAX_MS = 10_000;

/** A function and not `signal.aborted` directly: TypeScript narrows the property and doesn't see that it changes during the awaits. */
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

/** EventSource doesn't allow the Authorization header, so the stream is opened with fetch. */
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

/** Reads events until a final state. Returns that state, or null if the server closed first. */
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
 * Follows an analysis until it finishes.
 *
 * It uses the SSE stream and, if it is cut (a proxy that closes long connections, a
 * worker that restarts…), queries the state over HTTP and reconnects with
 * growing backoff. The server sends the current state on connecting, so a
 * reconnection never loses the end.
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

// ── Background analyses ───────────────────────────────────────────────────────
// Those still running after their window is closed. In localStorage: they survive
// reloading the page and appear in any tab that is opened.

export interface BackgroundJob {
  jobId: string;
  playerId: number;
  playerName: string;
}

const BACKGROUND_KEY = "ygg.backgroundJobs";
const listeners = new Set<() => void>();

function readBackgroundJobs(): BackgroundJob[] {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(BACKGROUND_KEY) ?? "[]");
    return Array.isArray(parsed) ? (parsed as BackgroundJob[]) : [];
  } catch {
    return [];
  }
}

let backgroundJobs = readBackgroundJobs();

function setBackgroundJobs(next: BackgroundJob[]) {
  backgroundJobs = next;
  try {
    localStorage.setItem(BACKGROUND_KEY, JSON.stringify(next));
  } catch {
    // No storage (private mode): it keeps showing until reload.
  }
  for (const listener of listeners) listener();
}

export function addBackgroundJob(job: BackgroundJob) {
  if (!backgroundJobs.some((current) => current.jobId === job.jobId)) setBackgroundJobs([...backgroundJobs, job]);
}

export function removeBackgroundJob(jobId: string) {
  setBackgroundJobs(backgroundJobs.filter((job) => job.jobId !== jobId));
}

export function useBackgroundJobs(): BackgroundJob[] {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => backgroundJobs,
  );
}
