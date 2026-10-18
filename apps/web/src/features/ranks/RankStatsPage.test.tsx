import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it } from "vitest";

import { ALL_METRICS, OBJECTIVE_CONTROL, WIN_DECISIONS, WIN_OUTCOMES } from "./DeepDive";
import { niceScale, OBJECTIVE_KEYS, OVERVIEW_METRICS, WINNING_KEYS } from "./Overview";
import { RankStatsPage } from "./RankStatsPage";
import { enemyHalfShare, ROLES, stats, trend, winSplit, Z } from "./rankStats";

describe("Stats by rank", () => {
  // The keys are those of leagues.py: if a name changes there, a chart would be left empty without warning.
  it("finds every number the page shows in the data", () => {
    for (const metric of [...ALL_METRICS, ...OVERVIEW_METRICS]) expect(() => trend(metric.ref), metric.label).not.toThrow();
    for (const key of [...WIN_DECISIONS.map((row) => row.key), ...WIN_OUTCOMES.map((row) => row.key), ...WINNING_KEYS]) {
      expect(
        ROLES.some(({ role }) => Math.abs(winSplit(role, key)?.z ?? 0) >= Z),
        key,
      ).toBe(true);
    }
    for (const key of [...OBJECTIVE_CONTROL.map((row) => row.key), ...OBJECTIVE_KEYS]) {
      expect(stats.objectives[key]?.all?.n, key).toBeGreaterThan(0);
    }
    const { cells, high, rest } = stats.map_wards;
    for (const group of [high["100"], high["200"], rest["100"], rest["200"]]) {
      expect(group.squares).toHaveLength(cells * cells);
      // per ten thousand: each cell is rounded, and those under a half stay at 0 (up to 1%)
      expect(Math.abs(group.squares.reduce((total, value) => total + value, 0) - 1e4)).toBeLessThan(100);
    }
  });

  it("splits the ward map by the river", () => {
    const { cells } = stats.map_wards;
    const only = (index: number) => ({ wards: 1, games: 1, squares: Array.from({ length: cells ** 2 }, (_, i) => (i === index ? 1e4 : 0)) });
    expect(enemyHalfShare(only(0), "100")).toBe(0); // the blue base, for blue
    expect(enemyHalfShare(only(0), "200")).toBe(1); // and for red
    expect(enemyHalfShare(only(cells ** 2 - 1), "100")).toBe(1); // the red one
    expect(enemyHalfShare(only(cells - 1), "200")).toBe(0.5); // the bottom-right corner, in the river
  });

  it("opens every view and every deep-dive section", async () => {
    const router = createMemoryRouter([{ path: "/ranks", element: <RankStatsPage /> }], { initialEntries: ["/ranks"] });
    render(<RouterProvider router={router} />);

    expect(screen.getByRole("heading", { level: 1, name: /Stats by\s*rank/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "6 habits of Challenger players" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("tab", { name: "By role" }));
    await userEvent.click(screen.getByRole("button", { name: /Support/ }));
    expect(screen.getByRole("heading", { name: /How Challenger support players play/ })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("tab", { name: "Deep dive" }));
    for (const name of ["Laning", "Roles", "Macro & vision", "What wins games", "Method"]) {
      await userEvent.click(screen.getByRole("tab", { name }));
      expect(screen.getByRole("tab", { name })).toHaveAttribute("data-state", "active");
    }
    expect(screen.getByRole("tab", { name: "Deep dive" })).toHaveAttribute("data-state", "active");
  });
});

describe("niceScale", () => {
  it("rounds the axis to readable steps", () => {
    expect(niceScale([6.76, 7.1, 8.26])).toEqual({ domain: [6.5, 8.5], ticks: [6.5, 7, 7.5, 8, 8.5] });
    expect(niceScale([30.6, 26.2]).ticks).toEqual([26, 27, 28, 29, 30, 31]);
  });
});
