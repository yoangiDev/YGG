import { describe, expect, it } from "vitest";

import { formatCompact } from "@/lib/format";

import { FIRST_PAGE, historyPageLimit, mergeHistoryPages, NEXT_PAGE, nextHistoryOffset } from "./historyPaging";

describe("history paging", () => {
  it("asks for 20 matches first and 10 on every load more", () => {
    expect(historyPageLimit(0)).toBe(FIRST_PAGE);
    expect(historyPageLimit(20)).toBe(NEXT_PAGE);
    expect(nextHistoryOffset(20, 0)).toBe(20);
    expect(nextHistoryOffset(10, 20)).toBe(30);
  });

  it("keeps going after a short page and stops after an empty one", () => {
    expect(nextHistoryOffset(7, 20)).toBe(30);
    expect(nextHistoryOffset(0, 30)).toBeUndefined();
  });

  it("merges pages without repeating matches shifted by a new game", () => {
    const page = (...ids: string[]) => ids.map((match_id) => ({ match_id }));
    expect(mergeHistoryPages([page("c", "b"), page("b", "a")]).map((m) => m.match_id)).toEqual(["c", "b", "a"]);
  });
});

describe("formatCompact", () => {
  it("shortens large numbers", () => {
    expect(formatCompact(27_400)).toBe("27.4K");
    expect(formatCompact(950)).toBe("950");
  });
});
