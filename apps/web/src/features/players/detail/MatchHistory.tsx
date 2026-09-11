import { useInfiniteQuery, useMutation, useQueryClient, type InfiniteData } from "@tanstack/react-query";
import { ChevronDown, RefreshCw, Swords } from "lucide-react";
import { useEffect, useId, useMemo, useState, type ReactNode } from "react";

import { ChampionIcon, ItemIcon } from "@/components/player/PlayerBits";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader, Skeleton } from "@/components/ui/Card";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { cn } from "@/lib/cn";
import { formatCompact, formatDateTime, formatDuration, formatNumber, timeAgo } from "@/lib/format";
import { queryKeys } from "@/lib/queryKeys";
import { roleLabel } from "@/lib/roles";
import { kdaTone, toneText } from "@/lib/stats";

import { FIRST_PAGE, historyPageLimit, mergeHistoryPages, NEXT_PAGE, nextHistoryOffset } from "./historyPaging";
import { MatchDetails } from "./MatchDetails";

type Match = Schemas["MatchResponse"];

// Columnas compartidas por la cabecera y las filas (la build solo cabe desde lg); la última es el desplegable.
const GRID =
  "sm:grid-cols-[44px_minmax(130px,1.3fr)_repeat(4,minmax(56px,1fr))_28px] lg:grid-cols-[44px_minmax(140px,1.3fr)_repeat(4,minmax(58px,1fr))_176px_28px]";

const STAT_LABELS = ["KDA", "CS/min", "DMG/min", "Vision"];

function Stat({
  label,
  value,
  detail,
  detailClassName,
}: {
  label: string;
  value: ReactNode;
  detail: ReactNode;
  detailClassName?: string;
}) {
  return (
    <div className="min-w-0 sm:text-right">
      <p className="microtext text-[9px] text-subtle sm:hidden">{label}</p>
      <p className="mt-1 text-sm font-extrabold text-text tabular-nums sm:mt-0">{value}</p>
      <p className={cn("mt-0.5 truncate text-[11px] text-subtle tabular-nums", detailClassName)}>{detail}</p>
    </div>
  );
}

function MatchRow({ match, trackedPuuid }: { match: Match; trackedPuuid: string | undefined }) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const items = [match.item0, match.item1, match.item2, match.item3, match.item4, match.item5];

  return (
    <li className="border-b border-line">
      {/* Toda la fila despliega con el ratón; el botón del final lo hace accesible con teclado. */}
      <div
        onClick={() => setOpen((current) => !current)}
        className={cn(
          "relative grid cursor-pointer grid-cols-[44px_minmax(0,1fr)_28px] items-center gap-x-4 gap-y-3 py-3.5 pr-4 pl-5 transition-colors hover:bg-white/[0.025] sm:pr-5",
          GRID,
          open && "bg-white/[0.025]",
        )}
      >
        <span aria-hidden="true" className={cn("absolute inset-y-0 left-0 w-[3px]", match.win ? "bg-stat-blue" : "bg-stat-red")} />
        <ChampionIcon name={match.champion} size={44} />
        <div className="min-w-0">
          <p className="truncate text-[15px] font-extrabold tracking-[-0.01em] text-text">{match.champion}</p>
          <p className="mt-1 flex flex-wrap items-center gap-x-2 text-xs text-subtle">
            <span className={cn("text-[10px] font-black tracking-[0.14em] uppercase", match.win ? "text-stat-blue" : "text-stat-red")}>
              {match.win ? "Win" : "Loss"}
            </span>
            <span>{roleLabel(match.player_role)}</span>
            <span aria-hidden="true">·</span>
            <span className="tabular-nums">{formatDuration(match.duration)}</span>
            <span aria-hidden="true">·</span>
            <time dateTime={match.creation_time} title={formatDateTime(match.creation_time)}>
              {timeAgo(match.creation_time)}
            </time>
          </p>
        </div>

        {/* En móvil las cifras bajan a una fila propia; desde sm se integran en las columnas. */}
        <div className="col-span-3 grid grid-cols-4 gap-3 border-t border-line pt-3 sm:contents">
          <Stat
            label="KDA"
            value={
              <>
                {match.kills}/<span className="text-stat-red">{match.deaths}</span>/{match.assists}
              </>
            }
            detail={`${formatNumber(match.kda, 2)} KDA`}
            detailClassName={toneText[kdaTone(match.kda)]}
          />
          <Stat label="CS/min" value={formatNumber(match.cs_per_min, 1)} detail={`${match.total_cs} CS`} />
          <Stat label="DMG/min" value={formatNumber(match.dmg_per_min, 0)} detail={`${formatCompact(match.damage)} dmg`} />
          <Stat label="Vision" value={match.vision} detail={`${formatNumber(match.vision_per_min, 2)}/min`} />
        </div>

        <div role="group" aria-label="Items" className="hidden items-center justify-end gap-0.5 lg:flex">
          {items.map((item, index) => (
            <ItemIcon key={index} itemId={item} size={22} />
          ))}
          <span className="ml-1.5">
            <ItemIcon itemId={match.item6} size={22} />
          </span>
        </div>

        <button
          type="button"
          aria-expanded={open}
          aria-controls={panelId}
          aria-label={`${open ? "Hide" : "Show"} details of ${match.champion} ${match.win ? "win" : "loss"} ${timeAgo(match.creation_time)}`}
          className="col-start-3 row-start-1 grid size-7 cursor-pointer place-items-center justify-self-end border border-transparent text-subtle transition-colors hover:border-line hover:text-acid sm:col-start-auto sm:row-start-auto"
        >
          <ChevronDown className={cn("size-4 transition-transform duration-300", open && "rotate-180 text-acid")} aria-hidden="true" />
        </button>
      </div>

      {open && (
        <div id={panelId}>
          <MatchDetails matchId={match.match_id} trackedPuuid={trackedPuuid} />
        </div>
      )}
    </li>
  );
}

function HistorySkeleton() {
  return (
    <div aria-hidden="true" className="flex flex-col">
      {Array.from({ length: 6 }, (_, index) => (
        <div key={index} className="flex items-center gap-4 border-b border-line px-5 py-3.5">
          <Skeleton className="size-11 shrink-0" />
          <Skeleton className="h-9 flex-1" />
          <Skeleton className="hidden h-9 w-72 sm:block" />
        </div>
      ))}
    </div>
  );
}

/**
 * Historial de partidas: 20 al abrir y 10 más cada vez que se pide, al estilo de
 * dpm.lol. Cada partida se despliega con sus 10 participantes.
 */
export function MatchHistory({ playerId, trackedPuuid }: { playerId: number; trackedPuuid?: string }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const key = queryKeys.playerMatches(playerId);

  const history = useInfiniteQuery({
    queryKey: key,
    initialPageParam: 0,
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET("/matches/player/{player_id}", {
          params: { path: { player_id: playerId }, query: { offset: pageParam, limit: historyPageLimit(pageParam) } },
        }),
      ),
    getNextPageParam: (lastPage, _pages, lastOffset) => nextHistoryOffset(lastPage.length, lastOffset),
  });

  // Cada página descargada entra en las estadísticas por campeón y por rol.
  const { dataUpdatedAt } = history;
  useEffect(() => {
    if (!dataUpdatedAt) return;
    void queryClient.invalidateQueries({ queryKey: queryKeys.playerChampions(playerId) });
    void queryClient.invalidateQueries({ queryKey: queryKeys.playerSummary(playerId) });
  }, [dataUpdatedAt, playerId, queryClient]);

  const sync = useMutation({
    mutationFn: () =>
      unwrap(
        api.GET("/matches/player/{player_id}", {
          params: { path: { player_id: playerId }, query: { offset: 0, limit: FIRST_PAGE, sync: true } },
        }),
      ),
    onSuccess: (page) => {
      queryClient.setQueryData<InfiniteData<Match[], number>>(key, { pages: [page], pageParams: [0] });
      toast.success("Match history synced");
    },
    onError: (error) => toast.error(error.message),
  });

  const matches = useMemo(() => mergeHistoryPages(history.data?.pages ?? []), [history.data]);

  return (
    <Card className="min-w-0">
      <CardHeader
        title="Match history"
        description="Ranked solo queue, newest first. Open a match to see all ten players."
        action={
          <Button variant="ghost" size="sm" loading={sync.isPending} onClick={() => sync.mutate()}>
            {!sync.isPending && <RefreshCw className="size-3.5" aria-hidden="true" />}
            Sync
          </Button>
        }
      />

      {history.isPending ? (
        <HistorySkeleton />
      ) : !history.data ? (
        <ErrorState error={history.error} onRetry={() => void history.refetch()} />
      ) : matches.length === 0 ? (
        <EmptyState
          icon={<Swords className="size-6" />}
          title="No ranked games found"
          description="Sync to download the latest ranked games from Riot."
        />
      ) : (
        <>
          <div aria-hidden="true" className={cn("hidden gap-x-4 border-b border-line py-2.5 pr-5 pl-5 sm:grid", GRID)}>
            <span className="microtext col-span-2 text-subtle">Champion</span>
            {STAT_LABELS.map((label) => (
              <span key={label} className="microtext text-right text-subtle">
                {label}
              </span>
            ))}
            <span className="microtext hidden text-right text-subtle lg:block">Build</span>
            <span />
          </div>

          <ul aria-label="Match history">
            {matches.map((match) => (
              <MatchRow key={match.match_id} match={match} trackedPuuid={trackedPuuid} />
            ))}
          </ul>

          <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
            <span className="microtext text-subtle tabular-nums">{matches.length} matches</span>
            {history.hasNextPage ? (
              <Button
                variant="outline"
                size="sm"
                arrow="down"
                loading={history.isFetchingNextPage}
                onClick={() => void history.fetchNextPage()}
              >
                Load {NEXT_PAGE} more
              </Button>
            ) : (
              <span className="microtext text-subtle">End of ranked history</span>
            )}
          </div>
          {history.isFetchNextPageError && (
            <p role="alert" className="px-5 pb-4 text-[13px] text-danger">
              {history.error.message}
            </p>
          )}
        </>
      )}
    </Card>
  );
}
