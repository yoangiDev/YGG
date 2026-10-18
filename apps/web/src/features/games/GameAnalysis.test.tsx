import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { PremiumData, Review } from "@/features/snapshots/premiumData";
import { renderWithProviders } from "@/test/render";

import { GameAnalysis } from "./GameAnalysis";

const moment = (id: number, clock: string, title: string, extra: { gold?: number; dead_for?: number; wp_before?: number; wp_after?: number } = {}) => ({
  id,
  t: 100 * id,
  clock,
  x: 7000,
  z: 7000,
  where: "Mid lane",
  kind: "death" as const,
  tone: "bad" as const,
  severity: 2 as const,
  title,
  text: `${title}, explained.`,
  ...extra,
});

const result: PremiumData = {
  summary: {
    tier: "EMERALD",
    role: "BOTTOM",
    games: 1,
    wins: 0,
    metrics: {},
    patterns: [{ kind: "death", title: "Dying without vision", text: "You die unseen.", tone: "bad", weight: 1, moments: ["EUW1_1:1"] }],
  },
  games: [
    {
      match_id: "EUW1_1",
      champion: "Kaisa",
      role: "BOTTOM",
      win: false,
      duration: 1800,
      stats: {},
      flashes: [],
      wp: null,
      moments: [moment(1, "1:40", "Died to Qiyana"), moment(2, "3:20", "Died to Gragas", { gold: -620, dead_for: 25, wp_before: 60, wp_after: 52 })],
    },
  ],
  missing: {},
};

const review: Review = {
  headline: "You won your lane; information cost you the game.",
  coach_summary: "First paragraph.\n\nSecond paragraph.",
  lessons: [{ title: "Count who you have not seen", why: "Because.", fix: "Stay near vision.", moments: ["EUW1_1:2"] }],
  strengths: [{ title: "Wave management", detail: "Slow pushes.", moments: ["EUW1_1:1"] }],
  game_notes: [],
  moment_notes: [],
  next_game: ["Recall on a pushed wave."],
};

const lessons = () => within(screen.getByRole("heading", { name: "What to work on" }).closest("section") as HTMLElement);
const headings = () => screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);

/** jsdom has no matchMedia: `wide` says whether the screen shows the stage alongside (≥1024 px). */
function screenIs(wide: boolean) {
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: query.includes("min-width") ? wide : false }));
}

describe("GameAnalysis", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    screenIs(true);
  });

  it("puts the match, what you do well, the coach and the numbers in that order", () => {
    renderWithProviders(<GameAnalysis result={result} review={review} />);
    expect(headings()).toEqual([
      "Your game, moment by moment",
      "What you already do well",
      review.headline,
      "Your numbers against your tier",
    ]);
  });

  it("a lesson shows its moment on the stage, without «G1» on the card", async () => {
    renderWithProviders(<GameAnalysis result={result} review={review} />);
    const chip = lessons().getByRole("button", { name: /3:20/ });
    expect(chip).not.toHaveTextContent("G1");
    await userEvent.click(chip);
    expect(screen.getByText("Died to Gragas, explained.")).toBeInTheDocument();
  });

  it("stacked, a lesson takes the page up to the stage; with the stage alongside nothing moves", async () => {
    const scroll = vi.fn();
    Element.prototype.scrollIntoView = scroll;
    renderWithProviders(<GameAnalysis result={result} review={review} />);
    const chip = () => lessons().getByRole("button", { name: /3:20/ });
    await userEvent.click(chip());
    expect(scroll).not.toHaveBeenCalled();
    screenIs(false);
    await userEvent.click(chip());
    expect(scroll).toHaveBeenCalledOnce();
  });

  it("the cards show the essentials and the full text stays behind a button, per card or per section", async () => {
    renderWithProviders(<GameAnalysis result={result} review={review} />);
    expect(screen.queryByText("Because.")).not.toBeInTheDocument();
    await userEvent.click(lessons().getByRole("button", { name: "Why it happened" }));
    expect(screen.getByText("Because.")).toBeInTheDocument();
    await userEvent.click(lessons().getByRole("button", { name: "Show less" }));
    expect(screen.queryByText("Because.")).not.toBeInTheDocument();

    await userEvent.click(lessons().getByRole("button", { name: "Show all text: What to work on" }));
    expect(screen.getByText("Because.")).toBeInTheDocument();
  });

  it("each mistake in a lesson carries its verdict, its cost and its minute, and the lesson its total", () => {
    renderWithProviders(<GameAnalysis result={result} review={review} />);
    const lesson = lessons();
    expect(lesson.getByText("−620 gold")).toBeInTheDocument();
    expect(lesson.getByText("≈ 2.1 kills")).toBeInTheDocument();
    expect(lesson.getByText("−620 gold · 25 s dead")).toBeInTheDocument();
    expect(lesson.getByRole("img", { name: "Mistake" })).toBeInTheDocument();
  });

  it("the stage tells what came after a mistake", () => {
    renderWithProviders(<GameAnalysis result={result} review={review} />);
    const chain = screen.getByRole("list", { name: "What followed this error" });
    expect(within(chain).getByText("25 s dead")).toBeInTheDocument();
    expect(within(chain).getByText("Win chance 60% → 52%")).toBeInTheDocument();
  });

  it("announces with a short sentence which moment has been chosen, not with the whole card", async () => {
    renderWithProviders(<GameAnalysis result={result} review={review} />);
    const said = () => screen.getAllByRole("status").map((el) => el.textContent);
    expect(said()).toContain("Mistake. 3:20, Died to Gragas");
    expect(document.querySelector("[aria-live]:not([role=status])")?.textContent ?? "").not.toContain("Died to Gragas, explained.");

    await userEvent.click(within(screen.getByRole("list", { name: "Moments" })).getByRole("button", { name: /1:40/ }));
    expect(said()).toContain("Mistake. 1:40, Died to Qiyana");
  });

  it("a team loss isn't noted as a player's mistake", () => {
    const team = structuredClone(result);
    const objective = { ...moment(3, "5:00", "Lost the Cloud Drake"), kind: "objective" as const };
    team.games[0]?.moments?.push(objective);
    const lesson = { title: "Count who you have not seen", why: "Because.", fix: "Stay near vision.", moments: ["EUW1_1:2", "EUW1_1:3"] };
    renderWithProviders(<GameAnalysis result={team} review={{ ...review, lessons: [lesson] }} />);
    expect(lessons().getByRole("img", { name: "Team loss" })).toBeInTheDocument();
  });

  it("without a review it says where it will appear and draws no lessons", () => {
    renderWithProviders(<GameAnalysis result={result} review={null} />);
    expect(screen.getByText(/written coach review appears here/)).toBeInTheDocument();
    expect(screen.queryByText("What to work on")).not.toBeInTheDocument();
  });
});
