import { useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { EmptyState } from "@/components/ui/States";
import type { Schemas } from "@/lib/api/client";
import { cn } from "@/lib/cn";
import { formatDate, formatNumber } from "@/lib/format";
import { palette } from "@/lib/palette";

import { ChartTooltipBox, Swatch } from "./ChartTooltip";

type TrendPoint = Schemas["TrendPoint"];

const METRICS = [
  { value: "kda", average: "kda_moving_avg", label: "KDA", digits: 2 },
  { value: "cs_per_min", average: "cs_moving_avg", label: "CS / min", digits: 1 },
  { value: "gold_per_min", average: "gold_moving_avg", label: "Gold / min", digits: 0 },
  { value: "vision_per_min", average: "vision_moving_avg", label: "Vision / min", digits: 2 },
] as const;

type Metric = (typeof METRICS)[number];

function TrendTooltip({
  active,
  label,
  points,
  metric,
}: {
  active: boolean | undefined;
  label: string | number | undefined;
  points: TrendPoint[];
  metric: Metric;
}) {
  const point = points.find((candidate) => candidate.game_num === label);
  if (!active || !point) return null;
  return (
    <ChartTooltipBox
      title={
        <>
          Game {point.game_num} · {point.champion}{" "}
          <span className={point.win ? "text-stat-blue" : "text-stat-red"}>{point.win ? "W" : "L"}</span>
        </>
      }
    >
      <div className="flex justify-between gap-4">
        <span className="flex items-center gap-1.5">
          <Swatch color={palette.gray} />
          {metric.label}
        </span>
        <span className="tabular-nums">{formatNumber(point[metric.value], metric.digits)}</span>
      </div>
      <div className="flex justify-between gap-4">
        <span className="flex items-center gap-1.5">
          <Swatch color={palette.primaryLight} />
          Moving average
        </span>
        <span className="tabular-nums">{formatNumber(point[metric.average], metric.digits)}</span>
      </div>
      <p className="text-muted">{formatDate(point.creation_time)}</p>
    </ChartTooltipBox>
  );
}

export function TrendChart({ points, height = 260 }: { points: TrendPoint[]; height?: number }) {
  const [selected, setSelected] = useState<Metric["value"]>("kda");
  const metric = METRICS.find((candidate) => candidate.value === selected) ?? METRICS[0];

  if (points.length === 0) return <EmptyState title="No games to chart" />;

  const latest = points.at(-1);

  return (
    <div>
      <div role="group" aria-label="Trend metric" className="mb-3 flex flex-wrap gap-1.5">
        {METRICS.map((candidate) => (
          <button
            key={candidate.value}
            type="button"
            aria-pressed={candidate.value === selected}
            onClick={() => setSelected(candidate.value)}
            className={cn(
              "cursor-pointer rounded-full border px-3 py-1 text-xs font-semibold transition",
              candidate.value === selected
                ? "border-primary bg-primary/15 text-primary-light"
                : "border-border text-muted hover:text-fg",
            )}
          >
            {candidate.label}
          </button>
        ))}
      </div>
      <div
        role="img"
        aria-label={`${metric.label} over ${points.length} games. Latest moving average: ${formatNumber(latest?.[metric.average] ?? 0, metric.digits)}.`}
        style={{ height }}
      >
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={points} margin={{ top: 8, right: 12, bottom: 0, left: -8 }}>
            <CartesianGrid stroke={palette.grid} vertical={false} />
            <XAxis dataKey="game_num" tick={{ fill: palette.muted, fontSize: 11 }} tickLine={false} axisLine={{ stroke: palette.border }} />
            <YAxis tick={{ fill: palette.muted, fontSize: 11 }} tickLine={false} axisLine={false} width={44} />
            <Tooltip
              cursor={{ stroke: palette.border }}
              content={(props) => <TrendTooltip active={props.active} label={props.label} points={points} metric={metric} />}
            />
            <Line
              type="monotone"
              dataKey={metric.value}
              stroke={palette.gray}
              strokeOpacity={0.45}
              strokeWidth={1}
              dot={{ r: 2.5, fill: palette.gray, strokeWidth: 0 }}
              activeDot={{ r: 4 }}
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey={metric.average}
              stroke={palette.primaryLight}
              strokeWidth={2.5}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
