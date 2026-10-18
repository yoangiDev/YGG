/** Normalised point on the minimap: (0,0) top left, (1,1) bottom right. */
export interface HeatPoint {
  x: number;
  y: number;
}

/**
 * Density of points over a grid with a Gaussian kernel, normalised to [0, 1].
 * Same formula as the original Flutter client's heatmap (the degree project's client).
 */
export function buildHeatmapGrid(points: readonly HeatPoint[], gridSize = 40, kernelRadius = 0.06): number[] {
  const grid = new Array<number>(gridSize * gridSize).fill(0);
  if (points.length === 0) return grid;

  const radiusSq = kernelRadius * kernelRadius;
  for (const point of points) {
    const cx = Math.min(1, Math.max(0, point.x));
    const cy = Math.min(1, Math.max(0, point.y));
    const minX = Math.max(0, Math.floor((cx - kernelRadius) * gridSize));
    const maxX = Math.min(gridSize - 1, Math.ceil((cx + kernelRadius) * gridSize));
    const minY = Math.max(0, Math.floor((cy - kernelRadius) * gridSize));
    const maxY = Math.min(gridSize - 1, Math.ceil((cy + kernelRadius) * gridSize));

    for (let gy = minY; gy <= maxY; gy++) {
      for (let gx = minX; gx <= maxX; gx++) {
        const dx = (gx + 0.5) / gridSize - cx;
        const dy = (gy + 0.5) / gridSize - cy;
        const distSq = dx * dx + dy * dy;
        if (distSq <= radiusSq) {
          const index = gy * gridSize + gx;
          grid[index] = (grid[index] ?? 0) + Math.exp(-distSq / (radiusSq * 0.35));
        }
      }
    }
  }

  const max = Math.max(...grid);
  return max > 0 ? grid.map((value) => value / max) : grid;
}

export const HEAT_STOPS = ["#9e5ae2", "#f87171", "#ff9f19"] as const;

/** Purple → red → orange scale for an intensity in [0, 1]. */
export function heatColor(value: number): string {
  const t = Math.min(1, Math.max(0, value));
  const upper = t >= 0.5;
  const from = Number.parseInt((upper ? HEAT_STOPS[1] : HEAT_STOPS[0]).slice(1), 16);
  const to = Number.parseInt((upper ? HEAT_STOPS[2] : HEAT_STOPS[1]).slice(1), 16);
  const local = upper ? (t - 0.5) * 2 : t * 2;
  const channel = (shift: number) => Math.round(((from >> shift) & 255) * (1 - local) + ((to >> shift) & 255) * local);
  return `rgb(${channel(16)} ${channel(8)} ${channel(0)})`;
}

/** Minute 14 in seconds: the laning phase is everything before it (as in ygg_core). */
const LANE_PHASE_END_SEC = 840;

export type DeathPhase = "laning" | "mid_late";

/** Normalised positions of the deaths of a set of matches (computed by the backend), of one phase or of all. */
export function deathPoints(
  matches: readonly { death_events_normalized: readonly Record<string, unknown>[] }[],
  phase?: DeathPhase,
): HeatPoint[] {
  return matches.flatMap((match) =>
    match.death_events_normalized.flatMap((event) => {
      if (typeof event.norm_x !== "number" || typeof event.norm_y !== "number") return [];
      if (phase) {
        const laning = (typeof event.time === "number" ? event.time : 0) < LANE_PHASE_END_SEC;
        if (laning !== (phase === "laning")) return [];
      }
      return [{ x: event.norm_x, y: event.norm_y }];
    }),
  );
}
