import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { tokenStore } from "@/lib/api/client";

import { followJob, type JobStatus } from "./jobProgress";

function sseResponse(chunks: string[]): Response {
  const encoder = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
  return new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" } });
}

const job = (patch: Partial<JobStatus>): JobStatus => ({
  job_id: "job-1",
  status: "processing",
  progress: 0,
  snapshot_id: null,
  error: null,
  attempts: 1,
  ...patch,
});

const event = (name: string, data: JobStatus) => `event: ${name}\r\ndata: ${JSON.stringify(data)}\r\n\r\n`;

describe("followJob", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    tokenStore.set("token");
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
  });

  it("streams progress until the job is done", async () => {
    const split = event("progress", job({ progress: 80 }));
    fetchMock.mockResolvedValueOnce(
      sseResponse([
        ": ping\r\n\r\n",
        event("progress", job({ progress: 40 })),
        split.slice(0, 12),
        split.slice(12),
        event("done", job({ status: "done", progress: 100, snapshot_id: 42 })),
      ]),
    );
    const seen: number[] = [];

    const final = await followJob("job-1", (status) => seen.push(status.progress), new AbortController().signal);

    expect(seen).toEqual([40, 80, 100]);
    expect(final?.snapshot_id).toBe(42);
    const [url, init] = fetchMock.mock.calls[0] ?? [];
    expect(typeof url === "string" ? url : "").toMatch(/\/snapshots\/jobs\/job-1\/stream$/);
    expect(new Headers(init?.headers).get("Authorization")).toBe("Bearer token");
  });

  it("falls back to the status endpoint when the stream drops", async () => {
    fetchMock
      .mockResolvedValueOnce(sseResponse([event("progress", job({ progress: 10 }))]))
      .mockResolvedValueOnce(
        new Response(JSON.stringify(job({ status: "error", error: "Riot API unavailable", attempts: 3 })), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );

    const final = await followJob("job-1", () => undefined, new AbortController().signal);

    expect(final).toMatchObject({ status: "error", error: "Riot API unavailable", attempts: 3 });
  });

  it("gives up on jobs that belong to someone else", async () => {
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 404 }));

    await expect(followJob("job-1", () => undefined, new AbortController().signal)).rejects.toMatchObject({ status: 404 });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("stops quietly when aborted", async () => {
    const controller = new AbortController();
    fetchMock.mockImplementationOnce(() => {
      controller.abort();
      return Promise.reject(new DOMException("Aborted", "AbortError"));
    });

    await expect(followJob("job-1", () => undefined, controller.signal)).resolves.toBeNull();
  });
});
