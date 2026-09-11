import { QueryClient } from "@tanstack/react-query";

import { ApiError } from "@/lib/api/client";

/** Los 4xx no mejoran reintentando (salvo 408/429); los fallos de red y los 5xx sí, un par de veces. */
export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (failureCount >= 2) return false;
  if (error instanceof ApiError && error.status >= 400 && error.status < 500) {
    return error.status === 408 || error.status === 429;
  }
  return true;
}

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: false,
        retry: shouldRetry,
      },
      mutations: { retry: false },
    },
  });
}
