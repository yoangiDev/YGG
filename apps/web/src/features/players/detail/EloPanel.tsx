import { useQuery } from "@tanstack/react-query";
import { ArrowDown, ArrowUp } from "lucide-react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { ChartTooltipBox } from "@/components/charts/ChartTooltip";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { cn } from "@/lib/cn";
import { formatDate, formatSigned } from "@/lib/format";
import { queryKeys } from "@/lib/queryKeys";
import { ladderPoints, normalizeTier, RANK_COLORS, rankImage, rankLabel, type Tier } from "@/lib/rank";

type Player = Schemas["PlayerResponse"];
type EloPoint = Schemas["EloPoint"];

interface Row {
  point: EloPoint;
  value: number;
  change: number | null; // LP relative to the previous day with a point
  games: number | null;
  [tier: string]: unknown;
}

// Local noon: a bare "2026-09-17" would be read as UTC midnight and could fall on the previous day.
const dayLabel = (day: string) => formatDate(`${day}T12:00:00`);

function EloTooltip({ row }: { row: Row | undefined }) {
  if (!row) return null;
  const { point } = row;
  return (
    <ChartTooltipBox title={dayLabel(point.day)}>
      <span className="flex items-center gap-2">
        <img src={rankImage(point.tier)} alt="" className="size-7" />
        <span className="text-sm font-black tabular-nums">{rankLabel(point.tier, point.division, point.lp)}</span>
      </span>
      {row.change !== null && (
        <span className={row.change >= 0 ? "text-stat-blue" : "text-stat-red"}>{formatSigned(row.change)} LP</span>
      )}
      {row.games !== null && <span className="text-muted">{row.games} {row.games === 1 ? "game" : "games"}</span>}
    </ChartTooltipBox>
  );
}

const DAY_MS = 86_400_000;

/** LP gained or lost in the last `days` days up to the last point (from the first if the history is shorter). */
function lpChange(rows: Row[], days: number): number | null {
  const last = rows.at(-1);
  if (!last) return null;
  const since = Date.parse(last.point.day) - days * DAY_MS;
  const base = rows.findLast((row) => Date.parse(row.point.day) <= since) ?? rows[0];
  return base ? last.value - base.value : null;
}

function LpChange({ label, change }: { label: string; change: number | null }) {
  if (change === null) return null;
  return (
    <span className="flex items-baseline gap-1.5">
      <span className="microtext text-subtle">{label}</span>
      <span
        className={cn("flex items-center gap-0.5 text-sm font-black tabular-nums", change >= 0 ? "text-stat-blue" : "text-stat-red")}
      >
        {change > 0 && <ArrowUp className="size-3.5" strokeWidth={3} aria-hidden="true" />}
        {change < 0 && <ArrowDown className="size-3.5" strokeWidth={3} aria-hidden="true" />}
        {formatSigned(change)} LP
      </span>
    </span>
  );
}

function EloChart({ points }: { points: EloPoint[] }) {
  const rows: Row[] = points.map((point, index) => {
    const value = ladderPoints(point.tier, point.division, point.lp) ?? 0;
    const previous = points[index - 1];
    return {
      point,
      value,
      change: previous ? value - (ladderPoints(previous.tier, previous.division, previous.lp) ?? 0) : null,
      games: previous ? point.wins + point.losses - previous.wins - previous.losses : null,
    };
  });

  // One line per tier: each stretch carries the colour of the tier of its final day, so the colour changes exactly where the rank changes.
  const tierOf = (index: number) => normalizeTier(points[index]?.tier);
  const tiers = [...new Set(points.map((point) => normalizeTier(point.tier)))].filter((tier): tier is Tier => tier !== null);
  for (const [index, row] of rows.entries()) {
    for (const tier of tiers) row[tier] = tierOf(index) === tier || tierOf(index + 1) === tier ? row.value : null;
  }

  const first = rows[0];
  const last = rows.at(-1);
  const summary =
    first && last
      ? `Elo from ${rankLabel(first.point.tier, first.point.division, first.point.lp)} on ${dayLabel(first.point.day)} to ${rankLabel(last.point.tier, last.point.division, last.point.lp)} on ${dayLabel(last.point.day)}.`
      : "";

  return (
    <div className="flex items-center gap-6">
      <p className="flex shrink-0 gap-x-6">
        <LpChange label="Last 30d" change={lpChange(rows, 30)} />
        <LpChange label="Last 7d" change={lpChange(rows, 7)} />
      </p>
      <div role="img" aria-label={summary} className="h-14 min-w-0 flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 6, right: 8, bottom: 6, left: 8 }}>
            <XAxis dataKey="point.day" hide />
            <YAxis hide domain={["dataMin - 40", "dataMax + 40"]} />
            <Tooltip
              cursor={{ stroke: "rgba(255,255,255,0.15)" }}
              content={(props) => (props.active ? <EloTooltip row={props.payload[0]?.payload as Row | undefined} /> : null)}
            />
            {tiers.map((tier) => (
              <Line
                key={tier}
                dataKey={tier}
                type="monotone"
                stroke={RANK_COLORS[tier]}
                strokeWidth={2}
                dot={{ r: 3, fill: RANK_COLORS[tier], strokeWidth: 0 }}
                activeDot={{ r: 4, strokeWidth: 0 }}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

/** Elo day by day (stored automatically only for verified accounts), under the rank on the player's card. With no points
 * yet, nothing is shown. */
export function EloSection({ player }: { player: Player }) {
  const elo = useQuery({
    queryKey: queryKeys.playerElo(player.id),
    queryFn: () => unwrap(api.GET("/players/{player_id}/elo", { params: { path: { player_id: player.id } } })),
  });

  if (!elo.data?.length) return null;
  return (
    <section aria-label="Elo" className="relative mt-3 min-w-0 border-t border-line pt-3">
      <EloChart points={elo.data} />
    </section>
  );
}
