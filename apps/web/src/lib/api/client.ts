import createClient, { type Middleware } from "openapi-fetch";

import type { components, paths } from "./schema";

export type Schemas = components["schemas"];

export const API_URL = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");

// ── Access token ──────────────────────────────────────────────────────────────
//
// El access token vive solo en memoria (nunca en localStorage: un XSS no puede
// leer lo que no está persistido). El refresh token es una cookie httpOnly que
// el navegador envía solo a /auth; al recargar la página se pide uno nuevo.

type SessionListener = (token: string | null) => void;

let accessToken: string | null = null;
const listeners = new Set<SessionListener>();

export const tokenStore = {
  get: (): string | null => accessToken,
  set(token: string | null): void {
    accessToken = token;
    for (const listener of listeners) listener(token);
  },
  subscribe(listener: SessionListener): () => void {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
};

let pendingRefresh: Promise<string | null> | null = null;

/**
 * Cambia la cookie de refresh por un access token nuevo.
 *
 * Las llamadas concurrentes comparten la misma petición: el backend rota el
 * refresh token en cada uso y trata la reutilización como robo (revoca la
 * familia entera), así que dos refresh en paralelo cerrarían la sesión.
 */
export function refreshAccessToken(): Promise<string | null> {
  pendingRefresh ??= globalThis
    .fetch(`${API_URL}/auth/refresh`, { method: "POST", credentials: "include" })
    .then(async (response) => {
      if (!response.ok) return null;
      const body = (await response.json()) as Schemas["TokenResponse"];
      return body.access_token;
    })
    .catch(() => null)
    .then((token) => {
      tokenStore.set(token);
      return token;
    })
    .finally(() => {
      pendingRefresh = null;
    });
  return pendingRefresh;
}

const NO_RETRY_PATHS = ["/auth/login", "/auth/register", "/auth/refresh", "/auth/logout"];

const retryableRequests = new WeakMap<Request, Request>();

const authMiddleware: Middleware = {
  onRequest({ request }) {
    const token = tokenStore.get();
    if (token) request.headers.set("Authorization", `Bearer ${token}`);
    if (!NO_RETRY_PATHS.some((path) => request.url.endsWith(path))) {
      // El cuerpo de la petición original se consume al enviarla: se guarda una copia para reintentar.
      retryableRequests.set(request, request.clone());
    }
    return request;
  },
  async onResponse({ request, response }) {
    const retry = retryableRequests.get(request);
    retryableRequests.delete(request);
    if (response.status !== 401 || !retry) return response;

    const token = await refreshAccessToken();
    if (!token) return response;
    retry.headers.set("Authorization", `Bearer ${token}`);
    return globalThis.fetch(retry);
  },
};

export const api = createClient<paths>({
  baseUrl: API_URL,
  credentials: "include",
  // Resolver fetch en cada llamada permite sustituirlo en los tests.
  fetch: (request) => globalThis.fetch(request),
});
api.use(authMiddleware);

// ── Errores ───────────────────────────────────────────────────────────────────

export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(status: number, message: string, body?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

function describeError(status: number, body: unknown, response: Response): string {
  if (body && typeof body === "object" && "detail" in body) {
    const { detail } = body;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      // Errores de validación de FastAPI: [{ loc: ["body", "password"], msg: "..." }]
      const first: unknown = detail[0];
      if (first && typeof first === "object") {
        const { msg, loc } = first as { msg?: unknown; loc?: unknown };
        const field: unknown = Array.isArray(loc) ? loc.at(-1) : undefined;
        const message = typeof msg === "string" ? msg : "Invalid data";
        return typeof field === "string" ? `${field}: ${message}` : message;
      }
    }
  }
  if (status === 429) {
    const retryAfter = response.headers.get("Retry-After");
    return retryAfter ? `Too many requests. Try again in ${retryAfter}s.` : "Too many requests. Try again later.";
  }
  if (status === 401) return "Your session has expired. Sign in again.";
  if (status === 403) return "You do not have permission to do that.";
  if (status === 404) return "Not found.";
  if (status === 503) return "The Riot API is not available right now. Try again in a moment.";
  if (status >= 500) return "The server had a problem. Try again in a moment.";
  return `Request failed (${status}).`;
}

interface ApiResult<T> {
  data?: T;
  error?: unknown;
  response: Response;
}

/** Devuelve `data` o lanza un ApiError legible: así las queries de TanStack reciben errores normales. */
export async function unwrap<T>(request: Promise<ApiResult<T>>): Promise<T> {
  let result: ApiResult<T>;
  try {
    result = await request;
  } catch {
    throw new ApiError(0, "Cannot reach the server. Check your connection.");
  }
  const { data, error, response } = result;
  if (!response.ok) throw new ApiError(response.status, describeError(response.status, error, response), error);
  return data as T;
}

export function isApiError(error: unknown, status?: number): error is ApiError {
  return error instanceof ApiError && (status === undefined || error.status === status);
}
