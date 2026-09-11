import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api, ApiError, refreshAccessToken, tokenStore, unwrap } from "./client";

function json(body: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

function requestOf(call: unknown[]): Request {
  const [input, init] = call as [RequestInfo | URL, RequestInit | undefined];
  return input instanceof Request ? input : new Request(input, init);
}

describe("api client", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    tokenStore.set(null);
  });

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
  });

  it("sends the in-memory access token", async () => {
    tokenStore.set("token-1");
    fetchMock.mockResolvedValueOnce(json({ id: 1, email: "a@b.co", username: "a", role: "user", is_active: true }));

    await unwrap(api.GET("/auth/me"));

    expect(requestOf(fetchMock.mock.calls[0] ?? []).headers.get("Authorization")).toBe("Bearer token-1");
  });

  it("refreshes silently once on 401 and retries with the new token", async () => {
    tokenStore.set("expired");
    fetchMock
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(json({ access_token: "fresh", token_type: "bearer", expires_in: 900 }))
      .mockResolvedValueOnce(json({ items: [], total: 0, limit: 50, offset: 0 }));

    const page = await unwrap(api.GET("/players/"));

    expect(page.total).toBe(0);
    expect(tokenStore.get()).toBe("fresh");
    const refresh = requestOf(fetchMock.mock.calls[1] ?? []);
    expect(refresh.url).toMatch(/\/auth\/refresh$/);
    expect(refresh.method).toBe("POST");
    expect(requestOf(fetchMock.mock.calls[2] ?? []).headers.get("Authorization")).toBe("Bearer fresh");
  });

  it("replays the request body after refreshing", async () => {
    tokenStore.set("expired");
    fetchMock
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(json({ access_token: "fresh", token_type: "bearer", expires_in: 900 }))
      .mockResolvedValueOnce(json({ job_id: "j1", status: "queued" }, 202));

    await unwrap(api.POST("/snapshots/", { body: { player_id: 7, date_from: 1, date_to: 2, description: "" } }));

    const retried = requestOf(fetchMock.mock.calls[2] ?? []);
    expect(await retried.json()).toEqual({ player_id: 7, date_from: 1, date_to: 2, description: "" });
  });

  it("clears the session when the refresh token is rejected", async () => {
    tokenStore.set("expired");
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 401 })).mockResolvedValueOnce(new Response(null, { status: 401 }));

    await expect(unwrap(api.GET("/auth/me"))).rejects.toMatchObject({ status: 401 });
    expect(tokenStore.get()).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("never retries the login endpoint", async () => {
    fetchMock.mockResolvedValueOnce(json({ detail: "Invalid credentials" }, 401));

    const error = await unwrap(api.POST("/auth/login", { body: { email: "a@b.co", password: "x" } })).catch(
      (e: unknown) => e,
    );

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).message).toBe("Invalid credentials");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("shares a single refresh between concurrent callers", async () => {
    let resolve: (response: Response) => void = () => undefined;
    fetchMock.mockReturnValueOnce(new Promise<Response>((r) => (resolve = r)));

    const first = refreshAccessToken();
    const second = refreshAccessToken();
    resolve(json({ access_token: "shared", token_type: "bearer", expires_in: 900 }));

    expect(await Promise.all([first, second])).toEqual(["shared", "shared"]);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("turns validation and rate-limit errors into readable messages", async () => {
    fetchMock
      .mockResolvedValueOnce(json({ detail: [{ loc: ["body", "password"], msg: "too short", type: "value_error" }] }, 422))
      .mockResolvedValueOnce(new Response(null, { status: 429, headers: { "Retry-After": "30" } }));

    await expect(
      unwrap(api.POST("/auth/register", { body: { email: "a@b.co", username: "a", password: "x" } })),
    ).rejects.toThrow("password: too short");
    await expect(unwrap(api.POST("/auth/login", { body: { email: "a@b.co", password: "x" } }))).rejects.toThrow(
      "Try again in 30s",
    );
  });
});
