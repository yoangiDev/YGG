import { describe, expect, it } from "vitest";

import { ladderPoints, lpLabel, normalizeTier, rankImage, rankLabel, rankProgress, rankScore } from "./rank";

describe("rank helpers", () => {
  it("normalizes tiers from the API", () => {
    expect(normalizeTier("gold")).toBe("GOLD");
    expect(normalizeTier("")).toBeNull();
    expect(normalizeTier(null)).toBeNull();
    expect(normalizeTier("WOOD")).toBeNull();
  });

  it("labels ranks and hides divisions above Diamond", () => {
    expect(rankLabel("GOLD", "II", 45)).toBe("Gold II · 45 LP");
    expect(rankLabel("MASTER", "I", 320)).toBe("Master · 320 LP");
    expect(rankLabel("", "", 0)).toBe("Unranked");
  });

  it("shows only division and LP next to the emblem", () => {
    expect(lpLabel("DIAMOND", "II", 45)).toBe("II · 45 LP");
    expect([lpLabel("MASTER", "I", 320), lpLabel("GRANDMASTER", "I", 812)]).toEqual(["320 LP", "812 LP"]);
    expect(lpLabel(null, null, null)).toBe("Unranked");
  });

  it("points to the optimized badges", () => {
    expect(rankImage("Challenger")).toBe("/img/ranks/challenger.webp");
    expect(rankImage(undefined)).toBe("/img/ranks/unranked.webp");
  });

  it("measures apex progress against the regional cutoff", () => {
    expect(rankProgress("GOLD", 45)).toBeCloseTo(0.45);
    expect(rankProgress("MASTER", 550)).toBeCloseTo(0.5);
    expect(rankProgress("MASTER", 550, { grandmaster: 275, challenger: 900 })).toBe(1);
    expect(rankProgress("GRANDMASTER", 450, { grandmaster: 275, challenger: 900 })).toBeCloseTo(0.5);
    expect(rankProgress("CHALLENGER", 10)).toBe(1);
    expect(rankProgress(null, 10)).toBe(0);
  });

  it("puts ranks on a continuous LP ladder for the elo chart", () => {
    expect(ladderPoints("IRON", "IV", 0)).toBe(0);
    expect(ladderPoints("GOLD", "II", 45)).toBe(3 * 400 + 200 + 45);
    expect(ladderPoints("DIAMOND", "I", 99)).toBe(2799);
    // From Master there are no divisions: LP keeps adding on the same base.
    expect([ladderPoints("MASTER", "I", 0), ladderPoints("GRANDMASTER", "I", 700)]).toEqual([2800, 3500]);
    expect(ladderPoints("", "", 0)).toBeNull();
  });

  it("orders players by rank", () => {
    const ladder = [
      rankScore("", "", 0),
      rankScore("GOLD", "IV", 99),
      rankScore("GOLD", "I", 0),
      rankScore("PLATINUM", "IV", 0),
      rankScore("DIAMOND", "I", 100),
      rankScore("MASTER", "I", 0),
      rankScore("MASTER", "I", 300),
      rankScore("GRANDMASTER", "I", 700),
      rankScore("CHALLENGER", "I", 1500),
    ];
    expect([...ladder].sort((a, b) => a - b)).toEqual(ladder);
  });
});
