import { useState } from "react";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { EmptyState } from "@/components/ui/States";
import type { Schemas } from "@/lib/api/client";
import { cn } from "@/lib/cn";
import { formatDate, formatNumber, formatPercent, formatSigned } from "@/lib/format";
import { palette } from "@/lib/palette";

import { ChartTooltipBox, Swatch } from "./ChartTooltip";

type TrendGame = Schemas["TrendGame"];
type TrendGroup = Schemas["TrendGroup"];
type TrendSeries = Schemas["TrendSeries"];

interface Row {
  game_num: number;
  value: number | null;
  average: number | null;
}

/** A value in its metric's format: differences with a sign, percentages with %. */
function formatTrendValue(value: number, series: Pick<TrendSeries, "unit" | "digits" | "signed">): string {
  if (series.signed) return formatSigned(value, series.digits);
  if (series.unit === "%") return formatPercent(value, series.digits);
  return formatNumber(value, series.digits);
}

function TooltipRow({ color, dashed = false, label, value }: { color: string; dashed?: boolean; label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4">
      <span className="flex items-center gap-1.5">
        <Swatch color={color} dashed={dashed} />
        {label}
      </span>
      <span className="tabular-nums">{value}</span>
    </div>
  );
}

function TrendTooltip({
  active,
  label,
  games,
  rows,
  series,
}: {
  active: boolean | undefined;
  label: string | number | undefined;
  games: TrendGame[];
  rows: Row[];
  series: TrendSeries;
}) {
  const index = typeof label === "number" ? label - 1 : -1;
  const game = games[index];
  const row = rows[index];
  if (!active || !game || !row) return null;
  const show = (value: number | null) => (value === null ? "—" : formatTrendValue(value, series));
  return (
    <ChartTooltipBox
      title={
        <>
          Game {game.game_num} · {game.champion}{" "}
          <span className={game.win ? "text-stat-blue" : "text-stat-red"}>{game.win ? "W" : "L"}</span>
        </>
      }
    >
      <TooltipRow color={palette.gray} label={series.label} value={show(row.value)} />
      <TooltipRow color={palette.primary} label="Moving average" value={show(row.average)} />
      {series.challenger !== null && <TooltipRow color={palette.gold} dashed label="Challenger" value={show(series.challenger)} />}
      <p className="text-muted">{formatDate(game.creation_time)}</p>
    </ChartTooltipBox>
  );
}

/** A trends chart: each match, its moving average and what is expected of a Challenger (dotted line). */
export function TrendChart({ games, group, height = 240 }: { games: TrendGame[]; group: TrendGroup; height?: number }) {
  const [selected, setSelected] = useState(group.metrics[0]?.key);
  const series = group.metrics.find((metric) => metric.key === selected) ?? group.metrics[0];

  if (!series || games.length === 0) return <EmptyState title="No games to chart" />;

  const rows: Row[] = games.map((game, index) => ({
    game_num: game.game_num,
    value: series.values[index] ?? null,
    average: series.moving_average[index] ?? null,
  }));
  const latest = [...rows].reverse().find((row) => row.average !== null)?.average ?? null;
  const summary = [
    `${series.label} over ${games.length} games.`,
    latest !== null ? `Latest moving average ${formatTrendValue(latest, series)}.` : "",
    series.challenger !== null ? `Challenger expected ${formatTrendValue(series.challenger, series)}.` : "",
  ].join(" ");

  return (
    <div>
      {group.metrics.length > 1 && (
        <div role="group" aria-label={`${group.label} metric`} className="mb-3 flex flex-wrap gap-1.5">
          {group.metrics.map((metric) => (
            <button
              key={metric.key}
              type="button"
              aria-pressed={metric.key === series.key}
              onClick={() => setSelected(metric.key)}
              className={cn(
                "cursor-pointer border px-3 py-1 text-xs font-bold transition-colors",
                metric.key === series.key ? "border-acid bg-acid/15 text-acid" : "border-line text-muted hover:text-text",
              )}
            >
              {metric.label}
            </button>
          ))}
        </div>
      )}
      <div role="img" aria-label={summary.trim()} style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: -8 }}>
            <CartesianGrid stroke={palette.grid} vertical={false} />
            <XAxis dataKey="game_num" tick={{ fill: palette.muted, fontSize: 11 }} tickLine={false} axisLine={{ stroke: palette.border }} />
            <YAxis
              tick={{ fill: palette.muted, fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              width={48}
              tickFormatter={(value: number) => formatTrendValue(value, { ...series, digits: Math.min(series.digits, 1) })}
            />
            <Tooltip
              cursor={{ stroke: palette.border }}
              content={(props) => <TrendTooltip active={props.active} label={props.label} games={games} rows={rows} series={series} />}
            />
            {series.challenger !== null && (
              <ReferenceLine y={series.challenger} stroke={palette.gold} strokeDasharray="6 4" strokeWidth={1.5} ifOverflow="extendDomain" />
            )}
            <Line
              type="monotone"
              dataKey="value"
              stroke={palette.gray}
              strokeOpacity={0.45}
              strokeWidth={1}
              dot={{ r: 2.5, fill: palette.gray, strokeWidth: 0 }}
              activeDot={{ r: 4 }}
              connectNulls
              isAnimationActive={false}
            />
            <Line type="monotone" dataKey="average" stroke={palette.primary} strokeWidth={2.5} dot={false} connectNulls isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
        <span className="flex items-center gap-1.5">
          <Swatch color={palette.gray} />
          Each game
        </span>
        <span className="flex items-center gap-1.5">
          <Swatch color={palette.primary} />
          Moving average
        </span>
        {series.challenger !== null && (
          <span className="flex items-center gap-1.5">
            <Swatch color={palette.gold} dashed />
            Challenger {formatTrendValue(series.challenger, series)}
          </span>
        )}
      </p>
    </div>
  );
}
