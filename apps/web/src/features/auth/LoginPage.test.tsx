import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { tokenStore } from "@/lib/api/client";
import { jsonResponse, renderWithProviders, requestUrl } from "@/test/render";

import { LoginPage } from "./LoginPage";

const fetchMock = vi.fn<typeof fetch>();

function mockApi(routes: Record<string, () => Response>) {
  fetchMock.mockImplementation((input) => {
    const url = requestUrl(input);
    const handler = Object.entries(routes).find(([path]) => url.endsWith(path))?.[1];
    return Promise.resolve(handler ? handler() : new Response(null, { status: 404 }));
  });
}

const noSession = () => new Response(null, { status: 401 });
const tokens = () => jsonResponse({ access_token: "access", token_type: "bearer", expires_in: 900 });
const me = (email: string) => () => jsonResponse({ id: 1, email, username: "demo", role: "user", is_active: true });

beforeEach(() => {
  tokenStore.set(null);
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  fetchMock.mockReset();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("LoginPage", () => {
  it("validates the form before calling the API", async () => {
    mockApi({ "/auth/refresh": noSession });
    renderWithProviders(<LoginPage />);

    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Enter a valid email address")).toBeInTheDocument();
    expect(screen.getByText("Enter your password")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toHaveAttribute("aria-invalid", "true");
    expect(fetchMock.mock.calls.map(([input]) => requestUrl(input))).toEqual([expect.stringMatching(/\/auth\/refresh$/)]);
  });

  it("shows the API error when the credentials are wrong", async () => {
    mockApi({
      "/auth/refresh": noSession,
      "/auth/login": () => jsonResponse({ detail: "Incorrect email or password" }, 401),
    });
    renderWithProviders(<LoginPage />);

    await userEvent.type(screen.getByLabelText("Email"), "demo@ygg.gg");
    await userEvent.type(screen.getByLabelText("Password"), "wrong-password");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Incorrect email or password");
  });

  it("applies the backend password policy when creating an account", async () => {
    mockApi({ "/auth/refresh": noSession });
    renderWithProviders(<LoginPage />);

    await userEvent.click(screen.getByRole("button", { name: "Create an account" }));
    await userEvent.type(screen.getByLabelText("Username"), "summoner");
    await userEvent.type(screen.getByLabelText("Email"), "new@ygg.gg");
    await userEvent.type(screen.getByLabelText("Password"), "short");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByText("Use at least 10 characters")).toBeInTheDocument();
  });

  it("signs in and leaves the login page", async () => {
    mockApi({ "/auth/refresh": noSession, "/auth/login": tokens, "/auth/me": me("demo@ygg.gg") });
    renderWithProviders(<LoginPage />, { path: "/login" });

    await userEvent.type(screen.getByLabelText("Email"), "demo@ygg.gg");
    await userEvent.type(screen.getByLabelText("Password"), "correct horse battery");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Redirected")).toBeInTheDocument();
    expect(tokenStore.get()).toBe("access");
  });

  it("hides the demo access unless it is configured", async () => {
    mockApi({ "/auth/refresh": noSession });
    renderWithProviders(<LoginPage />);

    expect(await screen.findByRole("button", { name: "Sign in" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Enter the demo" })).not.toBeInTheDocument();
  });

  it("enters the read-only demo with the published credentials", async () => {
    vi.stubEnv("VITE_DEMO_EMAIL", "demo@ygg.gg");
    vi.stubEnv("VITE_DEMO_PASSWORD", "public-demo-password");
    mockApi({ "/auth/refresh": noSession, "/auth/login": tokens, "/auth/me": me("demo@ygg.gg") });
    renderWithProviders(<LoginPage />, { path: "/login" });

    expect(screen.getByText("public-demo-password")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Enter the demo" }));

    expect(await screen.findByText("Redirected")).toBeInTheDocument();
    const login = fetchMock.mock.calls.map(([input]) => input).find((input) => requestUrl(input).endsWith("/auth/login"));
    expect(login instanceof Request ? await login.json() : null).toEqual({
      email: "demo@ygg.gg",
      password: "public-demo-password",
    });
  });
});
