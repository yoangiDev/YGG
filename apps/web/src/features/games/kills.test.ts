import { describe, expect, it } from "vitest";

import { killsLabel } from "./kills";

describe("killsLabel", () => {
  it("states the kills in a sentence, with the sign already out", () => {
    expect(killsLabel(-1240)).toBe("4.1 kills");
    expect(killsLabel(300)).toBe("1 kill");
    expect(killsLabel(-150)).toBe("0.5 of a kill");
    expect(killsLabel(-3600)).toBe("12 kills");
    expect(killsLabel(5)).toBe("");
  });
});
