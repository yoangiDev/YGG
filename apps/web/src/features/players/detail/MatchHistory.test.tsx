import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { tokenStore } from "@/lib/api/client";
import { jsonResponse, renderWithProviders, requestUrl } from "@/test/render";

import { MatchHistory } from "./MatchHistory";

const TOTAL_MATCHES = 26;
const fetchMock = vi.fn<typeof fetch>();

function match(index: number) {
  return {
    match_id: `EUW1_${index}`,
    champion: index % 2 === 0 ? "Ahri" : "Syndra",
    win: index % 3 !== 0,
    duration: 1800,
    creation_time: new Date(Date.UTC(2026, 8, 1) - index * 3_600_000).toISOString(),
    player_role: "MID",
    kills: 5,
    deaths: 2,
    assists: 7,
    kda: 6,
    total_cs: 225,
    cs_per_min: 7.5,
    damage: 24_000,
    dmg_per_min: 800,
    vision: 25,
    vision_per_min: 0.83,
    item0: 0,
    item1: 0,
    item2: 0,
    item3: 0,
    item4: 0,
    item5: 0,
    item6: 0,
  };
}

beforeEach(() => {
  tokenStore.set("token");
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  fetchMock.mockReset();
  vi.unstubAllGlobals();
});

describe("MatchHistory", () => {
  it("shows 20 matches and loads 10 more until the history ends", async () => {
    const historyRequests: string[] = [];
    fetchMock.mockImplementation((input) => {
      const url = new URL(requestUrl(input));
      if (url.pathname === "/matches/player/1") {
        historyRequests.push(url.search);
        const offset = Number(url.searchParams.get("offset"));
        const limit = Number(url.searchParams.get("limit"));
        const size = Math.max(0, Math.min(limit, TOTAL_MATCHES - offset));
        return Promise.resolve(jsonResponse(Array.from({ length: size }, (_, i) => match(offset + i))));
      }
      return Promise.resolve(new Response(null, { status: 404 }));
    });

    renderWithProviders(<MatchHistory playerId={1} />);

    const list = await screen.findByRole("list", { name: "Match history" });
    expect(within(list).getAllByRole("listitem")).toHaveLength(20);
    expect(within(list).getAllByText("800")[0]).toBeInTheDocument(); // DMG/min

    await userEvent.click(screen.getByRole("button", { name: "Load 10 more" }));
    await waitFor(() => expect(within(list).getAllByRole("listitem")).toHaveLength(TOTAL_MATCHES));

    await userEvent.click(screen.getByRole("button", { name: "Load 10 more" }));
    expect(await screen.findByText("End of ranked history")).toBeInTheDocument();

    expect(historyRequests).toEqual(["?offset=0&limit=20", "?offset=20&limit=10", "?offset=30&limit=10"]);
  });
});
