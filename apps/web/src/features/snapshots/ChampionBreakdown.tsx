import { ChevronDown } from "lucide-react";
import { Fragment, type ReactNode } from "react";

import { ChampionIcon } from "@/components/player/PlayerBits";
import { Card, CardHeader } from "@/components/ui/Card";
import type { Schemas } from "@/lib/api/client";
import { cn } from "@/lib/cn";
import { asPercent, formatNumber, formatPercent, formatSigned } from "@/lib/format";
import { statTone, toneText, winRateTone } from "@/lib/stats";

type Champion = Schemas["ChampionStatsResponse"];

const HEADERS = [
  "Champion",
  "Games",
  "W–L",
  "WR",
  "K / D / A",
  "KDA",
  "CS/min",
  "Vis/min",
  "DMG/min",
  "Gold/min",
  "KP",
  "DMG %",
  "GD@14",
  "CSD@14",
  "Deaths 0–14",
  "Deaths 14+",
];

function Missing() {
  return <span className="text-subtle">—</span>;
}

function Signed({ value }: { value: number | null }) {
  if (value === null) return <Missing />;
  return <span className={value >= 0 ? "text-stat-green" : "text-stat-red"}>{formatSigned(value)}</span>;
}

/** Performance with each champion of the snapshot. Clicking one expands its history below its row. */
export function ChampionBreakdown({
  champions,
  selected,
  onSelect,
  history,
}: {
  champions: Champion[];
  selected: string | null;
  onSelect: (champion: string) => void;
  history: (champion: string) => ReactNode;
}) {
  return (
    <Card className="min-w-0">
      <CardHeader title="Champion stats" description="Per game on each champion. Select one to unfold its games." />
      <div className="relative overflow-x-auto">
        <table className="w-full border-collapse text-sm" aria-label="Champion stats">
          <thead>
            <tr className="border-b border-line">
              {HEADERS.map((header, index) => (
                <th
                  key={header}
                  scope="col"
                  className={cn(
                    "px-2 py-2.5 text-xs leading-tight font-bold tracking-wider text-muted uppercase",
                    index === 0 ? "text-left" : "text-center",
                  )}
                >
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {champions.map((champion) => {
              const active = champion.champion_name === selected;
              return (
                <Fragment key={champion.champion_name}>
                {/* The whole row expands with the mouse; the button in the first cell makes it accessible by keyboard. */}
                <tr
                  onClick={() => onSelect(champion.champion_name)}
                  className={cn(
                    "cursor-pointer border-b border-line/60 text-center whitespace-nowrap text-text/90 tabular-nums transition-colors hover:bg-white/[0.03]",
                    active && "bg-acid/[0.06] shadow-[inset_3px_0_0_var(--color-acid)]",
                  )}
                >
                  <td className="px-2 py-2 text-left">
                    <button type="button" aria-expanded={active} className="flex cursor-pointer items-center gap-2.5 text-left">
                      <ChevronDown className={cn("size-4 text-subtle transition-transform", active && "rotate-180 text-acid")} aria-hidden="true" />
                      <ChampionIcon name={champion.champion_name} size={28} />
                      <span className={cn("font-black", active ? "text-acid" : "text-text")}>{champion.champion_name}</span>
                    </button>
                  </td>
                  <td className="px-2 py-2">{champion.games_played}</td>
                  <td className="px-2 py-2 text-subtle">
                    {champion.wins}–{champion.losses}
                  </td>
                  <td className={cn("px-2 py-2 font-bold", toneText[winRateTone(champion.win_rate)])}>{formatPercent(champion.win_rate, 0)}</td>
                  <td className="px-2 py-2">
                    {formatNumber(champion.kills, 1)} / <span className="text-stat-red">{formatNumber(champion.deaths, 1)}</span> /{" "}
                    {formatNumber(champion.assists, 1)}
                  </td>
                  <td className={cn("px-2 py-2 font-bold", toneText[statTone("kda", champion.kda_status)])}>{formatNumber(champion.kda, 2)}</td>
                  <td className="px-2 py-2">{formatNumber(champion.cs_per_min, 1)}</td>
                  <td className="px-2 py-2">{formatNumber(champion.vision_per_min, 2)}</td>
                  <td className="px-2 py-2">{formatNumber(champion.dmg_per_min, 0)}</td>
                  <td className="px-2 py-2">{formatNumber(champion.gold_per_min, 0)}</td>
                  <td className="px-2 py-2">{formatPercent(asPercent(champion.kill_participation), 0)}</td>
                  <td className="px-2 py-2">{formatPercent(asPercent(champion.damage_share), 1)}</td>
                  <td className="px-2 py-2">
                    <Signed value={champion.gold_diff_14} />
                  </td>
                  <td className="px-2 py-2">
                    <Signed value={champion.cs_diff_14} />
                  </td>
                  <td className="px-2 py-2">{champion.laning_deaths === null ? <Missing /> : formatNumber(champion.laning_deaths, 1)}</td>
                  <td className="px-2 py-2">{champion.mid_late_deaths === null ? <Missing /> : formatNumber(champion.mid_late_deaths, 1)}</td>
                </tr>
                {active && (
                  <tr className="border-b border-line/60 bg-ink-soft/60">
                    <td colSpan={HEADERS.length} aria-label={`${champion.champion_name} games`}>
                      {history(champion.champion_name)}
                    </td>
                  </tr>
                )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
