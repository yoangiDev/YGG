import { describe, expect, it } from "vitest";

import type { Located, Moment } from "@/features/snapshots/premiumData";

import { consequencesOf, costOf, placeLabel, verdictOf } from "./errors";

const moment = (id: number, t: number, extra: Partial<Moment> = {}): Located => {
  const m: Moment = {
    id,
    t,
    clock: `${Math.floor(t / 60)}:${String(t % 60).padStart(2, "0")}`,
    x: 7000,
    z: 7000,
    where: "the bot side river",
    kind: "death",
    tone: "bad",
    severity: 3,
    title: "Died",
    text: "",
    ...extra,
  };
  return { key: `m:${id}`, game: {} as Located["game"], gameIndex: 0, moment: m };
};

describe("verdictOf", () => {
  it("the engine's severity decides a mistake's verdict", () => {
    expect(verdictOf({ tone: "bad", severity: 3, kind: "death" })).toMatchObject({ name: "Blunder", glyph: "??" });
    expect(verdictOf({ tone: "bad", severity: 2, kind: "death" })).toMatchObject({ name: "Mistake", glyph: "?" });
    expect(verdictOf({ tone: "bad", severity: 1, kind: "fog" })).toMatchObject({ name: "Slip", glyph: "?!" });
  });

  it("a hit and a trade each have their own", () => {
    expect(verdictOf({ tone: "good", severity: 3, kind: "back" }).glyph).toBe("!!");
    expect(verdictOf({ tone: "good", severity: 1, kind: "back" }).glyph).toBe("!");
    expect(verdictOf({ tone: "neutral", severity: 2, kind: "trade" }).name).toBe("Trade-off");
  });

  it("what the team decides isn't the player's mistake: objectives, fights and swings", () => {
    expect(verdictOf({ tone: "bad", severity: 3, kind: "objective" })).toMatchObject({ key: "teamloss", name: "Team loss" });
    expect(verdictOf({ tone: "bad", severity: 2, kind: "fight" }).key).toBe("teamloss");
    expect(verdictOf({ tone: "good", severity: 3, kind: "swing" })).toMatchObject({ key: "teamwin", name: "Team win" });
    expect(verdictOf({ tone: "neutral", severity: 1, kind: "objective" }).key).toBe("tradeoff");
  });
});

describe("costOf y placeLabel", () => {
  it("states the gold and the dead time, or the WP if there is no gold", () => {
    expect(costOf(moment(1, 100, { gold: -310, dead_for: 20 }).moment)).toBe("−310 gold · 20 s dead");
    expect(costOf(moment(1, 100, { value: -14.6 }).moment)).toBe("−14.6 WP");
    expect(costOf(moment(1, 100).moment)).toBe("");
  });

  it("drops the place's article and capitalises it", () => {
    expect(placeLabel("the bot side river")).toBe("Bot side river");
    expect(placeLabel(null)).toBe("");
  });
});

describe("consequencesOf", () => {
  const death = moment(1, 1032, { dead_for: 36, killer: "Xerath", wp_before: 82, wp_after: 77 });

  it("chains the mistake, the dead time, what fell while you were away and the win chance", () => {
    const lost = moment(2, 1060, { kind: "objective", title: "Lost the Cloud Drake" });
    const steps = consequencesOf(death, [death, lost]);
    expect(steps.map((s) => s.kind)).toEqual(["death", "time", "objective", "wp"]);
    expect(steps[0]).toMatchObject({ sub: "17:12 · Xerath" });
    expect(steps[1]).toMatchObject({ label: "36 s dead", sub: "back at 17:48" });
    expect(steps[2]).toMatchObject({ key: "m:2", sub: "28 s later" });
  });

  it("doesn't count what happened before, what happened long after or what went well", () => {
    const before = moment(2, 1000, { kind: "objective" });
    const late = moment(3, 1032 + 36 + 13, { kind: "objective" });
    const won = moment(4, 1050, { kind: "objective", tone: "good" });
    expect(consequencesOf(death, [death, before, late, won]).map((s) => s.kind)).toEqual(["death", "time", "wp"]);
  });

  it("without dead time it only looks at the following 30 s", () => {
    const wave = moment(5, 500, { kind: "dive" });
    const next = moment(6, 520, { kind: "fight", title: "Lost the fight" });
    expect(consequencesOf(wave, [wave, next])).toEqual([]); // two links are not a chain
  });

  it("only mistakes have a chain of consequences", () => {
    expect(consequencesOf(moment(7, 100, { tone: "good", dead_for: 10, wp_before: 50, wp_after: 60 }), [])).toEqual([]);
  });
});
