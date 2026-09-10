/** Punto normalizado sobre el minimapa: (0,0) arriba a la izquierda, (1,1) abajo a la derecha. */
export interface HeatPoint {
  x: number;
  y: number;
}

/**
 * Densidad de puntos sobre una rejilla con núcleo gaussiano, normalizada a [0, 1].
 * Misma fórmula que el mapa de calor del cliente Flutter.
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

const HEAT_STOPS = ["#9e5ae2", "#f87171", "#ff9f19"] as const;

/** Escala morado → rojo → naranja para una intensidad en [0, 1]. */
export function heatColor(value: number): string {
  const t = Math.min(1, Math.max(0, value));
  const upper = t >= 0.5;
  const from = Number.parseInt((upper ? HEAT_STOPS[1] : HEAT_STOPS[0]).slice(1), 16);
  const to = Number.parseInt((upper ? HEAT_STOPS[2] : HEAT_STOPS[1]).slice(1), 16);
  const local = upper ? (t - 0.5) * 2 : t * 2;
  const channel = (shift: number) => Math.round(((from >> shift) & 255) * (1 - local) + ((to >> shift) & 255) * local);
  return `rgb(${channel(16)} ${channel(8)} ${channel(0)})`;
}

/** Posiciones normalizadas de las muertes de un conjunto de partidas (las calcula el backend). */
export function deathPoints(matches: readonly { death_events_normalized: readonly Record<string, unknown>[] }[]): HeatPoint[] {
  return matches.flatMap((match) =>
    match.death_events_normalized.flatMap((event) =>
      typeof event.norm_x === "number" && typeof event.norm_y === "number" ? [{ x: event.norm_x, y: event.norm_y }] : [],
    ),
  );
}
