import { describe, expect, it } from "vitest";

import { matchIdOf, replayFile, targetOf } from "./ReplayUpload";

describe("replay files", () => {
  it("map the client's file names to match ids and back", () => {
    expect(matchIdOf("EUW1-8006268209.rofl")).toBe("EUW1_8006268209");
    expect(matchIdOf("euw1-8006268209.ROFL")).toBe("EUW1_8006268209");
    expect(matchIdOf("EUW1-8006268209 (1).rofl")).toBeNull();
    expect(replayFile("EUW1_8006268209")).toBe("EUW1-8006268209.rofl");
  });

  it("send each file to its game; with only one expected, a renamed file goes to it", () => {
    const games = ["EUW1_1000001", "EUW1_1000002"];
    expect(targetOf("EUW1-1000002.rofl", games)).toBe("EUW1_1000002");
    expect(targetOf("EUW1-1000003.rofl", games)).toBeNull();
    expect(targetOf("my game.rofl", games)).toBeNull();
    expect(targetOf("my game.rofl", ["EUW1_1000001"])).toBe("EUW1_1000001");
  });
});
