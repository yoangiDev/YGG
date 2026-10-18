import { describe, expect, it } from "vitest";

import { parseId } from "./params";
import { parseRiotId } from "./riotId";

describe("parseRiotId", () => {
  it("splits name and tag, trimming spaces", () => {
    expect(parseRiotId("Faker#KR1")).toEqual({ gameName: "Faker", tagLine: "KR1" });
    expect(parseRiotId("  Hide on bush # KR1 ")).toEqual({ gameName: "Hide on bush", tagLine: "KR1" });
  });

  it.each(["Faker", "ab#KR1", "Faker#", "a#b#c", "Faker#TOOLONG", "#KR1"])("rejects %s", (value) => {
    expect(parseRiotId(value)).toBeNull();
  });
});

describe("parseId", () => {
  it("accepts positive integers only", () => {
    expect(parseId("42")).toBe(42);
    expect([undefined, null, "", "0", "-1", "1.5", "abc", "99999999999999999999"].map(parseId)).toEqual(
      Array(8).fill(null),
    );
  });
});
