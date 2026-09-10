import { describe, expect, it } from "vitest";

import { SseParser } from "./sse";

describe("SseParser", () => {
  it("parses events split across chunks", () => {
    const parser = new SseParser();
    expect(parser.feed("event: progress\r\ndata: {\"progress\"")).toEqual([]);
    expect(parser.feed(":50}\r\nretry: 3000\r\n\r\nevent: done\r\ndata: {}\r\n\r\n")).toEqual([
      { event: "progress", data: '{"progress":50}', retry: 3000 },
      { event: "done", data: "{}" },
    ]);
  });

  it("ignores keep-alive comments and empty events", () => {
    const parser = new SseParser();
    expect(parser.feed(": ping - 2026-09-11 12:00:00\n\n\n")).toEqual([]);
  });

  it("joins multi-line data and defaults the event name", () => {
    const parser = new SseParser();
    expect(parser.feed("data: line one\ndata:line two\nid: 7\n\n")).toEqual([
      { event: "message", data: "line one\nline two", id: "7" },
    ]);
  });
});
