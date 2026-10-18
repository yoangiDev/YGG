import { describe, expect, it, vi } from "vitest";

import { createSelection } from "./selection";

describe("createSelection", () => {
  it("notifies only when the chosen moment really changes", () => {
    const selection = createSelection("a");
    const seen = vi.fn();
    const stop = selection.subscribe(seen);

    selection.set("a");
    expect(seen).not.toHaveBeenCalled();

    selection.set("b");
    expect(selection.get()).toBe("b");
    expect(seen).toHaveBeenCalledTimes(1);

    stop();
    selection.set("c");
    expect(seen).toHaveBeenCalledTimes(1);
  });
});
