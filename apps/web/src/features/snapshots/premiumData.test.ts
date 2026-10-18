import { describe, expect, it } from "vitest";

import {
  type Game,
  gameMoments,
  indexMoments,
  isCoachReview,
  isSupportOpening,
  type Moment,
  separates,
  trendRows,
  type Ward,
  WARD_RISKS,
  wardGroups,
  wpAt,
} from "./premiumData";

const moment = (id: number, patch: Partial<Moment>): Moment => ({
  id,
  t: 300,
  clock: "5:00",
  x: 1000,
  z: 1000,
  where: "top lane",
  kind: "death",
  tone: "bad",
  severity: 2,
  title: "Died",
  text: "…",
  ...patch,
});

const game = (matchId: string, patch: Partial<Game>): Game => ({
  match_id: matchId,
  champion: "Qiyana",
  role: "JUNGLE",
  win: false,
  duration: 1800,
  stats: {},
  flashes: [],
  wp: null,
  ...patch,
});

describe("replay analysis dashboard data", () => {
  const games = [
    game("EUW1_1", {
      moments: [moment(0, {}), moment(1, { kind: "camps" }), moment(2, { kind: "gank", tone: "good" })],
      numbers: { gold_diff_14: -450, deaths_early: 1, deaths_late: 3, camp_gold_lost: 250 },
      wp: [[600, 0.4], [610, 0.5], [620, 0.55]],
    }),
    game("EUW1_2", { win: true, moments: [moment(0, { kind: "objective" })] }),
  ];

  it("finds every moment by the key the patterns and the review cite", () => {
    const index = indexMoments(games);
    expect(index.get("EUW1_1:1")?.moment.kind).toBe("camps");
    expect(index.get("EUW1_2:0")?.gameIndex).toBe(1);
    expect(index.size).toBe(4);
  });

  it("counts only the mistakes of each kind per game, in order", () => {
    const [first, second] = trendRows(games);
    expect(first).toMatchObject({ label: "G1", gold14: -450, deathsLate: 3, campGold: 250, mistakes: 2, death: 1, camps: 1 });
    expect(first?.gank).toBeUndefined(); // a gank that goes well is not a mistake
    expect(second).toMatchObject({ label: "G2", win: true, gold14: null, mistakes: 1, objective: 1 });
  });

  it("reads the team's win chance at a second and tells coach reviews from old ones", () => {
    const [first, second] = games as [Game, Game];
    expect(wpAt(first, 612)).toBe(50);
    expect(wpAt(second, 612)).toBeNull();
    expect(isCoachReview({ headline: "x", summary: "old", tips: [] })).toBe(false);
    expect(isCoachReview({ headline: "x", coach_summary: "new", lessons: [] })).toBe(true);
  });

  it("compares with winners and losers only where they are far apart", () => {
    expect(separates({ median: 5, winners: 3.76, losers: 6.64 })).toBe(true); // Master junglers' deaths
    expect(separates({ median: 5, winners: 4.94, losers: 5.13 })).toBe(false); // lost camps, Master
    expect(separates({ median: 0, winners: 0, losers: 0 })).toBe(false);
  });

  it("splits plays, wards and the support's openings into what went well and what didn't", () => {
    const [jungler] = trendRows([game("EUW1_3", { numbers: { plays: 5, plays_good: 3, plays_bad: 1 } })]);
    expect(jungler).toMatchObject({ playsGood: 3, playsBad: 1, playsEven: 1, wardsUseful: null, openingsBot: null });
    const [support] = trendRows([
      game("EUW1_4", { role: "UTILITY", numbers: { openings: 6, openings_mid: 4, wards: 30, wards_useful: 18, setups_prepared: 2 } }),
    ]);
    expect(support).toMatchObject({ openingsMid: 4, openingsBot: 2, wardsUseful: 18, wardsSilent: 12, setupsPrepared: 2, playsEven: null });
    expect(isSupportOpening({ role: "support" } as Parameters<typeof isSupportOpening>[0])).toBe(true);
  });

  it("gives each game its own moments, in the order they happened", () => {
    const index = indexMoments(games);
    expect(gameMoments(index, "EUW1_1").map((m) => m.moment.id)).toEqual([0, 1, 2]);
    expect(gameMoments(index, "EUW1_2")).toHaveLength(1);
    expect(gameMoments(index, "EUW1_nope")).toEqual([]);
  });

  it("groups the support's wards by risk, keeping the empty groups", () => {
    const ward = (patch: Partial<Ward>): Ward => ({
      t: 300, clock: "5:00", x: 0, z: 0, type: "support", when: "none", risk: "low", seconds: 0, jungler: false, swept: false, lived: 90, died: false, ...patch,
    });
    const groups = wardGroups([ward({ seconds: 12, jungler: true }), ward({}), ward({ risk: "high", died: true })], "risk", WARD_RISKS);
    expect(groups).toEqual([
      { key: "low", wards: 2, useful: 1, seconds: 12, jungler: 1, died: 0 },
      { key: "medium", wards: 0, useful: 0, seconds: 0, jungler: 0, died: 0 },
      { key: "high", wards: 1, useful: 0, seconds: 0, jungler: 0, died: 1 },
    ]);
  });
});
