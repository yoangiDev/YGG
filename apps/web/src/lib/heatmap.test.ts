import { describe, expect, it } from "vitest";

import { buildHeatmapGrid, deathPoints, heatColor } from "./heatmap";

describe("buildHeatmapGrid", () => {
  it("is empty without points", () => {
    expect(buildHeatmapGrid([], 10).every((v) => v === 0)).toBe(true);
  });

  it("peaks at 1 where points concentrate", () => {
    const grid = buildHeatmapGrid(
      [
        { x: 0.5, y: 0.5 },
        { x: 0.5, y: 0.5 },
        { x: 0.1, y: 0.9 },
      ],
      20,
    );
    const center = grid[10 * 20 + 10] ?? 0;
    const corner = grid[18 * 20 + 2] ?? 0;
    expect(Math.max(...grid)).toBe(1);
    expect(center).toBeGreaterThan(corner);
    expect(corner).toBeGreaterThan(0);
  });

  it("clamps points outside the map", () => {
    const grid = buildHeatmapGrid([{ x: 1.5, y: -0.2 }], 40);
    expect(grid[0 * 40 + 39]).toBe(1);
  });

  it("maps intensity to the heat scale", () => {
    expect(heatColor(0)).toBe("rgb(158 90 226)");
    expect(heatColor(0.5)).toBe("rgb(248 113 113)");
    expect(heatColor(1)).toBe("rgb(255 159 25)");
    expect(heatColor(7)).toBe(heatColor(1));
  });

  it("extracts normalized death positions and skips malformed events", () => {
    expect(
      deathPoints([
        { death_events_normalized: [{ norm_x: 0.2, norm_y: 0.8, time: 300 }, { x: 100 }] },
        { death_events_normalized: [{ norm_x: 0.5, norm_y: 0.5 }] },
      ]),
    ).toEqual([
      { x: 0.2, y: 0.8 },
      { x: 0.5, y: 0.5 },
    ]);
  });
});
