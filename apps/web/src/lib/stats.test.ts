import { describe, expect, it } from "vitest";

import { statTone, statusLabel, winRateTone } from "./stats";

describe("statTone", () => {
  it.each([
    ["kda", "excellent", "gold"],
    ["kda", "good", "blue"],
    ["kda", "normal", "green"],
    ["kda", "bad", "gray"],
    ["deaths", "excellent", "gold"],
    ["deaths", "good", "blue"],
    ["deaths", "normal", "gray"],
    ["deaths", "bad", "red"],
    ["early_gank_deaths", "bad", "red"],
    ["Laning Deaths", "normal", "gray"],
  ])("%s with status %s is %s", (key, status, tone) => {
    expect(statTone(key, status)).toBe(tone);
  });

  it("labels statuses for humans", () => {
    expect(statusLabel("normal")).toBe("Average");
    expect(statusLabel("unknown")).toBe("unknown");
  });
});

describe("threshold tones", () => {
  // The KDA status arrives from the backend (ygg-core status.py: grey < 3, green 3-4, orange >= 4).
  it("colors win rates like OP.GG", () => {
    expect([55, 50, 45, 44.9].map(winRateTone)).toEqual(["gold", "blue", "green", "gray"]);
  });
});
