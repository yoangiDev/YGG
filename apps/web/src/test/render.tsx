import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { createMemoryRouter, RouterProvider } from "react-router";

import { TooltipProvider } from "@/components/ui/Overlay";
import { ToastProvider } from "@/components/ui/Toast";
import { AuthProvider } from "@/features/auth/AuthProvider";

export function renderWithProviders(ui: ReactElement, { path = "/", route = path }: { path?: string; route?: string } = {}) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const router = createMemoryRouter(
    [
      { path, element: ui },
      { path: "*", element: <p>Redirected</p> },
    ],
    { initialEntries: [route] },
  );
  const result = render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <TooltipProvider>
          <ToastProvider>
            <RouterProvider router={router} />
          </ToastProvider>
        </TooltipProvider>
      </AuthProvider>
    </QueryClientProvider>,
  );
  return { ...result, queryClient, router };
}

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

export function requestUrl(input: RequestInfo | URL): string {
  if (input instanceof Request) return input.url;
  return input instanceof URL ? input.href : input;
}
