import { describe, expect, it } from "vitest";

import { kdaTone, statTone, statusLabel, winRateTone } from "./stats";

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
  it("colors win rates and KDA like OP.GG", () => {
    expect([55, 50, 45, 44.9].map(winRateTone)).toEqual(["gold", "blue", "green", "gray"]);
    expect([5, 4, 3, 2.99].map(kdaTone)).toEqual(["gold", "blue", "green", "gray"]);
  });
});
