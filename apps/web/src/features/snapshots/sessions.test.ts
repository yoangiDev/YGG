import { describe, expect, it } from "vitest";

import { buildLabel, groupSessions, periodOf, sessionRange, type SessionGame } from "./sessions";

const game = (id: string, time: string, version: string, win = true): SessionGame => ({
  match_id: id,
  creation_time: time,
  game_version: version,
  champion: "Ahri",
  win,
});

// in local time, so the day doesn't depend on the time zone of whoever runs the tests
const at = (day: number, hour: number) => new Date(2026, 9, day, hour).toISOString();

/** Element i, or a clear failure if it isn't there (with noUncheckedIndexedAccess, indexing gives T | undefined). */
function nth<T>(items: T[], i: number): T {
  const item = items[i];
  if (item === undefined) throw new Error(`no such element ${i} of ${items.length}`);
  return item;
}

describe("sessions", () => {
  const games = [
    game("a", at(5, 20), "16.19.821.7343"),
    game("b", at(6, 10), "16.19.823.722", false),
    game("c", at(6, 22), "16.19.823.722"),
    game("d", at(7, 9), "16.20.824.8524"),
    game("e", at(6, 9), "16.19.821.9000"), // the same day as b and c, but before the hotfix
  ];

  it("groups by build, then by local day, newest first", () => {
    const groups = groupSessions(games);
    expect(groups.map((g) => g.build)).toEqual(["16.20.824", "16.19.823", "16.19.821"]);
    const hotfix = nth(groups, 1);
    expect(hotfix.sessions).toHaveLength(1);
    expect(nth(hotfix.sessions, 0).games.map((g) => g.match_id)).toEqual(["c", "b"]);
    expect(nth(hotfix.sessions, 0).wins).toBe(1);
    expect(nth(groups, 2).sessions.map((s) => s.games.map((g) => g.match_id))).toEqual([["e"], ["a"]]); // the 6th and the 5th
  });

  it("names the build only when a patch has a hotfix in the list", () => {
    const groups = groupSessions(games);
    expect(buildLabel(nth(groups, 0), groups)).toBe("Patch 16.20");
    expect(buildLabel(nth(groups, 1), groups)).toBe("Patch 16.19 · build 823");
    expect(buildLabel(nth(groupSessions([game("x", at(1, 1), "")]), 0), [])).toBe("Unknown patch");
  });

  it("selects every session between two clicks, in either order, and its period covers only them", () => {
    const group = nth(
      groupSessions([game("1", at(3, 12), "16.20.1.1"), game("2", at(4, 12), "16.20.1.1"), game("3", at(5, 12), "16.20.1.1")]),
      0,
    );
    const [newest, middle, oldest] = group.sessions.map((s) => s.key);
    if (!newest || !middle || !oldest) throw new Error("missing sessions");
    expect(sessionRange(group, oldest, newest).map((s) => s.key)).toEqual([newest, middle, oldest]);
    expect(sessionRange(group, middle, middle)).toHaveLength(1);
    const period = periodOf(sessionRange(group, middle, oldest));
    expect(period.date_from).toBe(new Date(at(3, 12)).getTime() / 1000 - 60);
    expect(period.date_to).toBe(new Date(at(4, 12)).getTime() / 1000 + 60);
  });
});
