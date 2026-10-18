import { useQuery } from "@tanstack/react-query";
import { Bug, Castle, Crown, Eye, Flame, Handshake, Skull, Swords, type LucideIcon } from "lucide-react";
import { Line, LineChart, ReferenceDot, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { ChartTooltipBox } from "@/components/charts/ChartTooltip";
import { Skeleton } from "@/components/ui/Card";
import { ErrorState } from "@/components/ui/States";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { cn } from "@/lib/cn";
import { formatDuration, formatNumber, formatSigned } from "@/lib/format";
import { queryKeys } from "@/lib/queryKeys";

type WpaEvent = Schemas["WpaEventResponse"];

const OBJECTIVES: Record<string, string> = {
  DRAGON_1: "1st dragon",
  DRAGON_2: "2nd dragon",
  DRAGON_3: "3rd dragon",
  DRAGON_4: "Dragon soul",
  ELDER: "Elder dragon",
  BARON_NASHOR: "Baron",
  RIFTHERALD: "Rift Herald",
  HORDE: "Void grub",
  ATAKHAN: "Atakhan",
  INHIBITOR: "Inhibitor",
  TOWER_BASE: "Inhibitor turret",
  TOWER_NEXUS: "Nexus turret",
};

function objectiveName(target: string): string {
  const known = OBJECTIVES[target];
  if (known) return known;
  const [, tier, lane] = target.split("_"); // TOWER_OUTER_MID → Mid outer turret
  if (tier && lane) return `${lane.charAt(0)}${lane.slice(1).toLowerCase()} ${tier.toLowerCase()} turret`;
  return target;
}

function objectiveIcon(target: string): LucideIcon {
  if (target.startsWith("DRAGON") || target === "ELDER") return Flame;
  if (target === "BARON_NASHOR") return Crown;
  if (target === "RIFTHERALD") return Eye;
  if (target === "HORDE") return Bug;
  return Castle;
}

function describe(event: WpaEvent): { label: string; icon: LucideIcon } {
  switch (event.kind) {
    case "KILL":
      return { label: `Killed ${event.target}`, icon: Swords };
    case "ASSIST":
      return { label: `Assist on ${event.target}`, icon: Handshake };
    case "DEATH":
      return { label: `Died to ${event.target || "a turret or minions"}`, icon: Skull };
    case "OBJECTIVE":
      return { label: `Took ${objectiveName(event.target)}`, icon: objectiveIcon(event.target) };
    case "OBJECTIVE_AFTER_KILL":
      return { label: `${objectiveName(event.target)} after your kill`, icon: objectiveIcon(event.target) };
    case "CONCEDED_WHILE_DEAD":
      return { label: `${objectiveName(event.target)} lost while you were dead`, icon: objectiveIcon(event.target) };
  }
}

const signedTone = (value: number) => (value >= 0 ? "text-stat-blue" : "text-stat-red");

// Features of the ygg_core.metrics.wpa model, as they are shown.
const FACTORS: Record<string, { label: string; unit?: string }> = {
  gold_k: { label: "Gold", unit: "gold" },
  xp_k: { label: "Experience", unit: "XP" },
  kills: { label: "Kill balance" },
  dead: { label: "Numbers advantage" },
  outer_turrets: { label: "Outer turrets" },
  inner_turrets: { label: "Inner turrets" },
  base_turrets: { label: "Inhibitor turrets" },
  nexus_turrets: { label: "Nexus turrets" },
  inhibitors_down: { label: "Inhibitors down" },
  dragons: { label: "Dragons" },
  soul_point: { label: "Soul point" },
  soul: { label: "Dragon soul" },
  baron_active: { label: "Baron buff" },
  elder_active: { label: "Elder buff" },
  grubs: { label: "Void grubs" },
  herald: { label: "Rift Herald" },
};

function shareReason(event: WpaEvent): string {
  const n = event.shared_with ?? 1;
  switch (event.kind) {
    case "KILL":
    case "ASSIST":
      return n === 1 ? "All yours: nobody else on your team took part." : `Split between the ${n} teammates who took part: yours is 1/${n}.`;
    case "DEATH":
      return "A death counts entirely for the player who dies.";
    case "OBJECTIVE":
      return Math.abs((event.share ?? 0) * n - 0.5) < 0.01
        ? `Half goes to those who took it, half to whoever killed an enemy who was still dead. Split between the ${n} who took it.`
        : n === 1
          ? "All yours: you took it alone."
          : `Split between the ${n} teammates who took it.`;
    case "OBJECTIVE_AFTER_KILL":
      return `Half its value goes to whoever killed an enemy who was still dead when it fell. Your part: ${formatNumber(100 * (event.share ?? 0), 0)}%.`;
    case "CONCEDED_WHILE_DEAD":
      return n === 1 ? "It fell while you were dead: it counts for you." : `It fell while ${n} of your team were dead: yours is 1/${n}.`;
  }
}

/** Gold of the kill when there was a real shutdown (≥ 300): what was given away on dying or what their team collected. */
function bountyText(event: WpaEvent): string | null {
  const { bounty, shutdown } = event;
  if (!["KILL", "ASSIST", "DEATH"].includes(event.kind) || shutdown < 300) return null;
  const gold = `${formatNumber(bounty, 0)} gold bounty and a ${formatNumber(shutdown, 0)} gold shutdown`;
  return event.kind === "DEATH" ? `You gave a ${gold}.` : `Your team collected a ${gold}.`;
}

/** The why of an event: how much it moved their team's WP, what explains it and what part falls to the player. */
function Why({ event }: { event: WpaEvent }) {
  if (event.team_wpa === null || event.team_wpa === undefined) {
    return <p className="text-muted">Analysed before explanations were added. Run a new analysis to see why.</p>;
  }
  const decided = event.wp_before >= 80 || event.wp_before <= 20;
  const bounty = bountyText(event);
  const [lostLow, lostHigh] = event.gold_lost ?? [];
  return (
    <div className="flex flex-col gap-1.5">
      <p>
        Your team&apos;s chance to win went {formatNumber(event.wp_before, 0)}% → {formatNumber(event.wp_after, 0)}%. In an even game
        this play is worth <span className={cn("font-bold", signedTone(event.team_wpa))}>{formatSigned(event.team_wpa, 1)} pts</span>.
      </p>
      {bounty && <p>{bounty}</p>}
      {event.kind === "DEATH" && lostHigh ? (
        <p className="text-muted">
          Dead time cost you roughly {formatNumber(lostLow ?? 0, 0)}–{formatNumber(lostHigh, 0)} gold you would have earned.
        </p>
      ) : null}
      {event.drivers.length > 0 && (
        <ul className="flex flex-wrap gap-x-4 gap-y-1" aria-label="Why">
          {event.drivers.map((driver) => {
            const factor = FACTORS[driver.factor] ?? { label: driver.factor };
            return (
              <li key={driver.factor}>
                {factor.label} {formatSigned(driver.change, 0)}
                {factor.unit ? ` ${factor.unit}` : ""}{" "}
                <span className={cn("font-bold tabular-nums", signedTone(driver.wpa))}>({formatSigned(driver.wpa, 1)})</span>
              </li>
            );
          })}
        </ul>
      )}
      {decided && (
        <p className="text-muted">
          The game was already decided, so the real chance barely moves. The play still counts as much as in an even game.
        </p>
      )}
      <p>
        {shareReason(event)}{" "}
        <span className={cn("font-bold", signedTone(event.wpa))}>{formatSigned(event.wpa, 1)} for you.</span>
      </p>
    </div>
  );
}

/** WPA timeline of a snapshot match: their team's curve and each event with what it contributed. */
export function WpaTimeline({ snapshotId, matchId }: { snapshotId: number; matchId: string }) {
  const wpa = useQuery({
    queryKey: queryKeys.matchWpa(snapshotId, matchId),
    queryFn: () =>
      unwrap(
        api.GET("/matches/snapshot/{snapshot_id}/{match_id}/wpa", {
          params: { path: { snapshot_id: snapshotId, match_id: matchId } },
        }),
      ),
    staleTime: Infinity, // it is computed on analysing: it doesn't change
  });

  if (wpa.isPending) return <Skeleton className="m-4 h-48" />;
  if (wpa.isError) return <ErrorState error={wpa.error} onRetry={() => void wpa.refetch()} />;

  const { events, wp_curve: curve, wpa_total: total } = wpa.data;
  if (total === null || total === undefined) {
    return (
      <p className="p-4 text-sm text-muted">
        This match was analysed before win probability was added. Run a new analysis to see its timeline.
      </p>
    );
  }

  const points = curve.map((wp, minute) => ({ minute, wp }));
  return (
    <div className="grid gap-5 p-4 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
      <section aria-label="Win probability">
        <p className="text-xs text-muted">
          How much every play you took part in moves your team&apos;s chance of winning, each valued as if the game were even. 70
          is an average Challenger game.
        </p>
        <div
          role="img"
          aria-label={`Your team's win probability went from ${formatNumber(curve[0] ?? 50, 0)}% to ${formatNumber(curve.at(-1) ?? 50, 0)}%.`}
          className="mt-3 h-44"
        >
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: -20 }}>
              <XAxis dataKey="minute" type="number" domain={[0, "dataMax"]} tickFormatter={(m: number) => `${m}'`} tick={{ fontSize: 11 }} />
              <YAxis domain={[0, 100]} ticks={[0, 50, 100]} tickFormatter={(v: number) => `${v}%`} tick={{ fontSize: 11 }} />
              <ReferenceLine y={50} stroke="rgba(255,255,255,0.15)" strokeDasharray="4 4" />
              <Tooltip
                content={(props) => {
                  const row = props.active ? (props.payload[0]?.payload as { minute: number; wp: number } | undefined) : undefined;
                  return row ? <ChartTooltipBox title={`${row.minute}'`}>{formatNumber(row.wp, 0)}% to win</ChartTooltipBox> : null;
                }}
              />
              <Line dataKey="wp" type="monotone" stroke="var(--color-soft)" strokeWidth={2} dot={false} isAnimationActive={false} />
              {events.map((event, index) => (
                <ReferenceDot
                  key={index}
                  x={event.time / 60}
                  y={event.wp_after}
                  r={4}
                  stroke="none"
                  fill={event.wpa >= 0 ? "var(--color-stat-blue)" : "var(--color-stat-red)"}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>

      <ol className="flex max-h-72 flex-col overflow-y-auto" aria-label="Plays">
        {events.length === 0 && <li className="text-sm text-muted">No plays with a kill, death or objective.</li>}
        {events.map((event, index) => {
          const { label, icon: Icon } = describe(event);
          return (
            <li key={index} className="border-b border-line/50 last:border-0">
              {/* native details: opens and closes with keyboard and mouse with no state of its own. */}
              <details>
                <summary className="flex cursor-pointer list-none items-center gap-3 py-2 hover:bg-panel-light/40 [&::-webkit-details-marker]:hidden">
                  <span className="w-10 shrink-0 text-xs text-subtle tabular-nums">{formatDuration(event.time)}</span>
                  <Icon className={cn("size-4 shrink-0", signedTone(event.wpa))} aria-hidden="true" />
                  <span className="min-w-0 flex-1 truncate text-sm text-text">{label}</span>
                  <span className="shrink-0 text-xs text-subtle tabular-nums">
                    {formatNumber(event.wp_before, 0)}% → {formatNumber(event.wp_after, 0)}%
                  </span>
                  <span className={cn("w-14 shrink-0 text-right text-sm font-bold tabular-nums", signedTone(event.wpa))}>
                    {formatSigned(event.wpa, 1)}
                  </span>
                </summary>
                <div className="mb-2 ml-[3.25rem] text-xs leading-relaxed text-soft">
                  <Why event={event} />
                </div>
              </details>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
