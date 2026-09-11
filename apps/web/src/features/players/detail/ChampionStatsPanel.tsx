import { useQuery } from "@tanstack/react-query";
import { Crown } from "lucide-react";

import { ChampionIcon } from "@/components/player/PlayerBits";
import { Card, CardHeader, Skeleton } from "@/components/ui/Card";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { cn } from "@/lib/cn";
import { formatNumber, formatPercent } from "@/lib/format";
import { queryKeys } from "@/lib/queryKeys";
import { kdaTone, toneBackground, toneText, winRateTone } from "@/lib/stats";

type ChampionStats = Schemas["PlayerChampionStats"];

const LIMIT = 10;

function MiniStat({ label, value, className }: { label: string; value: string; className?: string }) {
  return (
    <div className="min-w-0 border-l border-line pl-3 first:border-l-0 first:pl-0">
      <dt className="microtext text-[9px] text-subtle">{label}</dt>
      <dd className={cn("mt-1 text-sm font-extrabold text-text tabular-nums", className)}>{value}</dd>
    </div>
  );
}

function ChampionRow({ champion }: { champion: ChampionStats }) {
  const tone = winRateTone(champion.win_rate);
  return (
    <li className="border-b border-line px-5 py-4 last:border-b-0">
      <div className="flex items-center gap-3">
        <ChampionIcon name={champion.champion_name} size={40} />
        <div className="min-w-0 flex-1">
          <p className="truncate text-[15px] font-extrabold tracking-[-0.01em] text-text">{champion.champion_name}</p>
          <p className="mt-0.5 text-xs text-subtle tabular-nums">
            {champion.games} {champion.games === 1 ? "game" : "games"} · {champion.wins}W {champion.losses}L
          </p>
        </div>
        <div className="text-right">
          <p className={cn("text-[15px] font-black tabular-nums", toneText[tone])}>{formatPercent(champion.win_rate, 0)}</p>
          <div className="mt-1.5 flex h-1 w-16 overflow-hidden bg-stat-red/30" aria-hidden="true">
            <div className={toneBackground[tone]} style={{ width: `${champion.win_rate}%` }} />
          </div>
        </div>
      </div>
      <dl className="mt-3.5 grid grid-cols-4 gap-3">
        <MiniStat label="KDA" value={formatNumber(champion.kda, 2)} className={toneText[kdaTone(champion.kda)]} />
        <MiniStat label="CS/min" value={formatNumber(champion.cs_per_min, 1)} />
        <MiniStat label="DMG/min" value={formatNumber(champion.dmg_per_min, 0)} />
        <MiniStat label="Vision" value={formatNumber(champion.vision_score, 1)} />
      </dl>
      <p className="sr-only">
        Average {champion.kills} kills, {champion.deaths} deaths and {champion.assists} assists per game.
      </p>
    </li>
  );
}

/** Campeones más jugados con su rendimiento: KDA, CS/min, daño por minuto y visión. */
export function ChampionStatsPanel({ playerId }: { playerId: number }) {
  const champions = useQuery({
    queryKey: queryKeys.playerChampions(playerId),
    queryFn: () =>
      unwrap(
        api.GET("/matches/player/{player_id}/champions", {
          params: { path: { player_id: playerId }, query: { limit: LIMIT } },
        }),
      ),
  });

  return (
    <Card featured>
      <CardHeader title="Champions" description="All stored ranked games of this player." />
      {champions.isPending ? (
        <div className="flex flex-col gap-3 p-5" aria-hidden="true">
          {Array.from({ length: 4 }, (_, index) => (
            <Skeleton key={index} className="h-20" />
          ))}
        </div>
      ) : champions.isError ? (
        <ErrorState error={champions.error} onRetry={() => void champions.refetch()} />
      ) : champions.data.length === 0 ? (
        <EmptyState icon={<Crown className="size-6" />} title="No champions yet" description="They appear as matches are loaded." />
      ) : (
        <ul aria-label="Champion statistics">
          {champions.data.map((champion) => (
            <ChampionRow key={champion.champion_name} champion={champion} />
          ))}
        </ul>
      )}
    </Card>
  );
}
