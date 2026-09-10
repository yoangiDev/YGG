import { PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart, ResponsiveContainer, Tooltip } from "recharts";

import type { Schemas } from "@/lib/api/client";
import { formatNumber } from "@/lib/format";
import { palette } from "@/lib/palette";

import { ChartTooltipBox, Swatch } from "./ChartTooltip";

export interface RadarSeries {
  id: string;
  label: string;
  color: string;
  dataset: Schemas["RadarDataset"];
  dashed?: boolean;
  fillOpacity?: number;
}

type Row = Record<string, string | number>;

function RadarTooltip({
  active,
  label,
  rows,
  series,
}: {
  active: boolean | undefined;
  label: string | number | undefined;
  rows: Row[];
  series: RadarSeries[];
}) {
  const row = rows.find((candidate) => candidate.axis === label);
  if (!active || !row) return null;
  return (
    <ChartTooltipBox title={String(label)}>
      {series.map((item, index) => (
        <div key={item.id} className="flex items-center justify-between gap-4">
          <span className="flex min-w-0 items-center gap-1.5">
            <Swatch color={item.color} dashed={item.dashed ?? false} />
            <span className="truncate">{item.label}</span>
          </span>
          <span className="tabular-nums">
            {row[`s${index}`]}
            <span className="text-muted">/100 · {formatNumber(Number(row[`raw${index}`] ?? 0), 2)}</span>
          </span>
        </div>
      ))}
    </ChartTooltipBox>
  );
}

/**
 * Radar normalizado 0-100 por rol. La primera serie es el jugador; el resto
 * (medias por rango, cuentas comparadas) se dibujan encima.
 */
export function PerformanceRadar({ axes, series, height = 340 }: { axes: string[]; series: RadarSeries[]; height?: number }) {
  const rows: Row[] = axes.map((axis) => {
    const row: Row = { axis };
    series.forEach((item, index) => {
      row[`s${index}`] = Math.round(item.dataset.normalized_values[axis] ?? 0);
      row[`raw${index}`] = item.dataset.values[axis] ?? 0;
    });
    return row;
  });

  const player = series[0];
  const summary = player
    ? axes.map((axis) => `${axis} ${Math.round(player.dataset.normalized_values[axis] ?? 0)}`).join(", ")
    : "";

  return (
    <figure>
      <div role="img" aria-label={`Radar chart, scores out of 100 for ${player?.label ?? "player"}: ${summary}.`} style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={rows} outerRadius="72%" margin={{ top: 8, right: 28, bottom: 8, left: 28 }}>
            <PolarGrid stroke={palette.grid} />
            <PolarAngleAxis dataKey="axis" tick={{ fill: palette.muted, fontSize: 11 }} />
            <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} tickCount={5} />
            {series.map((item, index) => (
              <Radar
                key={item.id}
                name={item.label}
                dataKey={`s${index}`}
                stroke={item.color}
                strokeWidth={index === 0 ? 2 : 1.5}
                strokeDasharray={item.dashed ? "5 4" : undefined}
                fill={item.color}
                fillOpacity={item.fillOpacity ?? 0}
                dot={index === 0 ? { r: 2.5, fill: item.color, strokeWidth: 0 } : false}
                isAnimationActive={false}
              />
            ))}
            <Tooltip
              cursor={false}
              content={(props) => <RadarTooltip active={props.active} label={props.label} rows={rows} series={series} />}
            />
          </RadarChart>
        </ResponsiveContainer>
      </div>
      {/* Alternativa accesible: los mismos datos en tabla para lectores de pantalla. */}
      <table className="sr-only">
        <caption>Radar scores out of 100</caption>
        <thead>
          <tr>
            <th scope="col">Axis</th>
            {series.map((item) => (
              <th key={item.id} scope="col">
                {item.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={String(row.axis)}>
              <th scope="row">{row.axis}</th>
              {series.map((item, index) => (
                <td key={item.id}>{row[`s${index}`]}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <figcaption className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-muted">
        {series.map((item) => (
          <span key={item.id} className="flex items-center gap-1.5">
            <Swatch color={item.color} dashed={item.dashed ?? false} />
            {item.label}
          </span>
        ))}
      </figcaption>
    </figure>
  );
}
