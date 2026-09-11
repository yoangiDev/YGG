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

function participant(index: number, teamId: number) {
  return {
    puuid: index === 0 ? "tracked-puuid" : `puuid-${index}`,
    game_name: index === 0 ? "Tracked" : `Player ${index}`,
    tag_line: "EUW",
    champion: index === 0 ? "Ahri" : "Garen",
    champion_level: 16,
    team_id: teamId,
    role: index % 5 === 4 ? "SUPPORT" : "MID",
    win: teamId === 100,
    kills: 5,
    deaths: 2,
    assists: 7,
    kda: 6,
    kill_participation: 60,
    cs: 225,
    cs_per_min: 7.5,
    gold: 12_000,
    damage: 24_000 - index * 1000,
    damage_per_min: 800,
    damage_share: 25,
    damage_taken: 18_000,
    vision_score: 25,
    vision_per_min: 0.83,
    wards_placed: 10,
    control_wards: 2,
    items: [0, 0, 0, 0, 0, 0],
    trinket: 0,
    spells: [4, 14],
    keystone: 8112,
    secondary_tree: 8200,
    score: 100 - index * 5,
    placement: index + 1,
    badge: index === 0 ? "MVP" : index === 5 ? "ACE" : null,
  };
}

const details = {
  match_id: "EUW1_0",
  creation_time: "2026-09-01T00:00:00Z",
  duration: 1800,
  queue_id: 420,
  game_version: "16.10.1",
  teams: [100, 200].map((teamId, side) => ({
    team_id: teamId,
    win: teamId === 100,
    kills: 25,
    towers: 8,
    inhibitors: 1,
    dragons: 3,
    barons: 1,
    heralds: 1,
    grubs: 3,
    atakhans: 0,
    participants: Array.from({ length: 5 }, (_, i) => participant(side * 5 + i, teamId)),
  })),
};

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

  it("opens a match with its ten players only when asked", async () => {
    const detailRequests: string[] = [];
    fetchMock.mockImplementation((input) => {
      const url = new URL(requestUrl(input));
      if (url.pathname === "/matches/player/1") return Promise.resolve(jsonResponse([match(0)]));
      if (url.pathname === "/matches/EUW1_0/details") {
        detailRequests.push(url.pathname);
        return Promise.resolve(jsonResponse(details));
      }
      return Promise.resolve(new Response(null, { status: 404 }));
    });

    renderWithProviders(<MatchHistory playerId={1} trackedPuuid="tracked-puuid" />);

    const toggle = await screen.findByRole("button", { name: /Show details of Ahri/ });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(detailRequests).toHaveLength(0);

    await userEvent.click(toggle);

    const winners = await screen.findByRole("region", { name: "Victory, Blue side" });
    expect(within(winners).getByText("Tracked")).toBeInTheDocument();
    expect(within(winners).getByText("MVP")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Defeat, Red side" })).getByText("ACE")).toBeInTheDocument();
    expect(screen.getAllByText(/^Player \d$/)).toHaveLength(9);
    expect(screen.getByRole("button", { name: /Hide details of Ahri/ })).toHaveAttribute("aria-expanded", "true");
    expect(detailRequests).toHaveLength(1);

    await userEvent.click(screen.getByRole("button", { name: /Hide details of Ahri/ }));
    expect(screen.queryByRole("region", { name: "Victory, Blue side" })).not.toBeInTheDocument();
  });
});
