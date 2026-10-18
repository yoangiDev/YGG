import { useId, useMemo } from "react";

import { buildHeatmapGrid, HEAT_STOPS, heatColor, type HeatPoint } from "@/lib/heatmap";

const MIN_VISIBLE = 0.05;

/** Death heatmap over the Rift minimap, drawn in SVG (no canvas: it scales and prints well). */
export function DeathHeatmap({ points, mapUrl, gridSize = 40 }: { points: HeatPoint[]; mapUrl: string | null; gridSize?: number }) {
  const grid = useMemo(() => buildHeatmapGrid(points, gridSize), [points, gridSize]);
  const filterId = `heat-blur-${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`;
  const cell = 100 / gridSize;

  return (
    <figure>
      <svg
        viewBox="0 0 100 100"
        role="img"
        aria-label={points.length > 0 ? `Heatmap of ${points.length} deaths on Summoner's Rift` : "No deaths recorded"}
        className="aspect-square w-full overflow-hidden bg-ink"
      >
        <defs>
          <filter id={filterId} x="-10%" y="-10%" width="120%" height="120%">
            <feGaussianBlur stdDeviation="0.9" />
          </filter>
        </defs>
        {mapUrl && (
          <image href={mapUrl} x="0" y="0" width="100" height="100" opacity="0.5" preserveAspectRatio="xMidYMid slice" />
        )}
        <g filter={`url(#${filterId})`}>
          {grid.map((value, index) =>
            value < MIN_VISIBLE ? null : (
              <rect
                key={index}
                x={(index % gridSize) * cell}
                y={Math.floor(index / gridSize) * cell}
                width={cell}
                height={cell}
                fill={heatColor(value)}
                fillOpacity={0.25 + value * 0.65}
              />
            ),
          )}
        </g>
      </svg>
      <figcaption className="mt-2 flex items-center justify-between gap-3 text-xs text-muted">
        <span>
          {points.length} death{points.length === 1 ? "" : "s"}
        </span>
        <span className="flex items-center gap-2">
          Fewer
          <span aria-hidden="true" className="h-1.5 w-20 rounded-full" style={{ background: `linear-gradient(90deg, ${HEAT_STOPS.join(", ")})` }} />
          More
        </span>
      </figcaption>
    </figure>
  );
}
