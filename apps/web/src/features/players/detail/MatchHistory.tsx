import { useInfiniteQuery, useMutation, useQueryClient, type InfiniteData } from "@tanstack/react-query";
import { ArrowUpRight, ChevronDown, Loader2, RefreshCw, Sparkles, Swords } from "lucide-react";
import { useEffect, useId, useMemo, useState, type ReactNode } from "react";

import { ChampionIcon, ItemIcon, RoleIcon, ScoreRing } from "@/components/player/PlayerBits";
import { Button, buttonClasses } from "@/components/ui/Button";
import { Card, CardHeader, Skeleton } from "@/components/ui/Card";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { useGameAnalyses, type Analysis } from "@/features/games/analyses";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { cn } from "@/lib/cn";
import { formatCompact, formatDateTime, formatDuration, formatNumber, timeAgo } from "@/lib/format";
import { queryKeys } from "@/lib/queryKeys";
import { roleIcon, roleLabel } from "@/lib/roles";
import { statTone, toneText } from "@/lib/stats";

import { FIRST_PAGE, historyPageLimit, mergeHistoryPages, NEXT_PAGE, nextHistoryOffset } from "./historyPaging";
import { MatchDetails, Placement } from "./MatchDetails";

type Match = Schemas["MatchResponse"];


// Columns shared by the header and the rows: result · champion · 4 figures · build (from lg) · grade · expander.
// Each block has its fixed column, so nothing depends on how wide the neighbouring text is.
const GRID =
  "sm:grid-cols-[28px_72px_48px_repeat(4,minmax(48px,1fr))_52px] @4xl:grid-cols-[28px_72px_48px_repeat(4,minmax(56px,1fr))_190px_52px]";


const STAT_LABELS = ["KDA", "CS/min", "DMG/min", "Vision"];

function Stat({
  label,
  value,
  detail,
  valueClassName,
}: {
  label: string;
  value: ReactNode;
  detail: ReactNode;
  valueClassName?: string;
}) {
  return (
    <div className="min-w-0 sm:text-right">
      <p className="microtext text-xs text-subtle sm:hidden">{label}</p>
      <p className={cn("mt-1 text-sm font-black text-text tabular-nums sm:mt-0", valueClassName)}>{value}</p>
      <p className="mt-0.5 truncate text-xs text-subtle tabular-nums">{detail}</p>
    </div>
  );
}

/** The analysis mark, in the champion's corner: a spinner while it is being analysed and, once analysed, a spark
 * in the accent (not a number, nor the row's colour, which is the result's). */
function AnalysisMark({ analysis }: { analysis: Analysis | undefined }) {
  if (analysis?.status === "processing") {
    return (
      <span className="absolute -top-1.5 -right-1.5 grid size-5 place-items-center rounded-full border border-line bg-ink">
        <Loader2 className="size-3 animate-spin text-stat-gold" aria-label="Analysing" />
      </span>
    );
  }
  if (analysis?.status !== "done") return null;
  return (
    <span className="absolute -top-1.5 -right-1.5 grid size-5 place-items-center rounded-full bg-acid text-on-acid" title="Analysed">
      <Sparkles className="size-3" aria-hidden="true" />
    </span>
  );
}

function MatchRow({ match, trackedPuuid, analysis }: { match: Match; trackedPuuid: string | undefined; analysis: Analysis | undefined }) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const items = [match.item0, match.item1, match.item2, match.item3, match.item4, match.item5];
  const hasRoleIcon = roleIcon(match.player_role) !== null;
  const analysed = analysis?.status === "done";
  const reviewUrl = `/analysis/${match.match_id}`;

  return (
    <li className={cn("border-b", match.win ? "border-stat-blue/20" : "border-stat-red/20")}>
      {/* The whole row expands with the mouse; the button at the end makes it accessible by keyboard. */}
      <div
        onClick={() => setOpen((current) => !current)}
        className={cn(
          "relative grid cursor-pointer grid-cols-[64px_52px_minmax(0,1fr)_28px] items-center gap-x-3 gap-y-3 py-2.5 pr-4 pl-5 transition-colors sm:pr-5",
          GRID,
          match.win
            ? cn("bg-stat-blue/[0.07] hover:bg-stat-blue/[0.12]", open && "bg-stat-blue/[0.12]")
            : cn("bg-stat-red/[0.07] hover:bg-stat-red/[0.12]", open && "bg-stat-red/[0.12]"),
        )}
      >
        <span aria-hidden="true" className={cn("absolute inset-y-0 left-0 w-[3px]", match.win ? "bg-stat-blue" : "bg-stat-red")} />
        <button
          type="button"
          aria-expanded={open}
          aria-controls={panelId}
          aria-label={`${open ? "Hide" : "Show"} details of ${match.champion} ${match.win ? "win" : "loss"} ${timeAgo(match.creation_time)}${analysed ? ", analysed" : ""}`}
          className="col-start-4 row-start-1 grid size-7 cursor-pointer place-items-center justify-self-end border border-transparent text-subtle transition-colors hover:border-line hover:text-acid sm:col-start-auto sm:row-start-auto sm:justify-self-start"
        >
          <ChevronDown className={cn("size-4 transition-transform duration-300", open && "rotate-180 text-acid")} aria-hidden="true" />
        </button>
        {/* Result, duration and date, each on its own line and left-aligned. */}
        <div className="min-w-0 whitespace-nowrap">
          <p className={cn("text-sm font-black tracking-title", match.win ? "text-stat-blue" : "text-stat-red")}>
            {match.win ? "Victory" : "Defeat"}
          </p>
          <p className="mt-0.5 text-xs font-bold text-soft tabular-nums">{formatDuration(match.duration)}</p>
          <time dateTime={match.creation_time} title={formatDateTime(match.creation_time)} className="mt-0.5 block text-xs text-subtle">
            {timeAgo(match.creation_time)}
          </time>
        </div>

        {/* The role goes over the champion icon: no variable-width text beside it. */}
        <div className="relative w-fit">
          <ChampionIcon name={match.champion} size={44} />
          <AnalysisMark analysis={analysis} />
          <span className="sr-only">
            {match.champion} · {roleLabel(match.player_role)}
          </span>
          {hasRoleIcon && (
            <span className="absolute -right-1.5 -bottom-1.5 grid size-5 place-items-center rounded-full border border-line bg-ink">
              <RoleIcon role={match.player_role} size={12} />
            </span>
          )}
        </div>

        {/* On mobile the figures drop to a row of their own; from sm they fit into the columns. */}
        <div className="col-span-4 row-start-2 grid grid-cols-4 gap-3 border-t border-line pt-3 sm:row-start-auto sm:contents">
          <Stat
            label="KDA"
            value={
              <>
                {match.kills}/<span className="text-stat-red">{match.deaths}</span>/{match.assists}
              </>
            }
            detail={`${formatNumber(match.kda, 2)} KDA`}
          />
          <Stat
            label="CS/min"
            value={formatNumber(match.cs_per_min, 1)}
            valueClassName={toneText[statTone("cs_per_min", match.cs_status)]}
            detail={`${match.total_cs} CS`}
          />
          <Stat
            label="DMG/min"
            value={formatNumber(match.dmg_per_min, 0)}
            detail={`${formatCompact(match.damage)} dmg`}
          />
          <Stat label="Vision" value={match.vision} detail={`${formatNumber(match.vision_per_min, 2)}/min`} />
        </div>

        <div role="group" aria-label="Items" className="hidden items-center justify-end gap-0.5 @4xl:flex">
          {items.map((item, index) => (
            <ItemIcon key={index} itemId={item} size={22} />
          ))}
          <span className="ml-1.5">
            <ItemIcon itemId={match.item6} size={22} />
          </span>
          <span className="flex" title={match.quest_reward_item ? "Role quest completed" : "Role quest not completed"}>
            <ItemIcon itemId={match.quest_reward_item} size={22} />
          </span>
        </div>

        <div className="col-start-3 row-start-1 justify-self-end sm:col-start-auto sm:row-start-auto sm:justify-self-center">
          {match.placement != null && match.score != null && (
            <div className="flex flex-col items-center gap-1" title="Score vs. Challenger games in this role (70 = better than 2 in 3 Challenger games)">
              <ScoreRing score={match.score} />
              <Placement badge={match.badge} placement={match.placement} className="h-4 w-11 text-xs" />
            </div>
          )}
        </div>

      </div>

      {open && (
        <div id={panelId} className={match.win ? "bg-stat-blue/[0.03]" : "bg-stat-red/[0.03]"}>
          {analysed && (
            <div className="border-t border-line px-5 py-4">
              <a
                href={reviewUrl}
                target="_blank"
                rel="noopener noreferrer"
                className={buttonClasses({ size: "lg", className: "w-full sm:w-auto" })}
              >
                <Sparkles className="size-4" aria-hidden="true" />
                Go to analysis
                <ArrowUpRight className="size-4" aria-hidden="true" />
              </a>
            </div>
          )}
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
 * Match history: 20 on opening and 10 more each time it is requested, in the style of
 * dpm.lol. Each match expands with its 10 participants.
 */
export function MatchHistory({ playerId, trackedPuuid }: { playerId: number; trackedPuuid?: string }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const analyses = useGameAnalyses();
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

  // Each downloaded page enters the per-champion and per-role stats.
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
  const byMatch = useMemo(() => new Map((analyses.data?.items ?? []).map((a) => [a.match_id, a])), [analyses.data]);

  return (
    <Card className="@container min-w-0">
      <CardHeader
        title="Match history"
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
          <div aria-hidden="true" className={cn("hidden gap-x-3 border-b border-line py-2.5 pr-5 pl-5 sm:grid", GRID)}>
            <span />
            <span className="microtext col-span-2 text-subtle">Match</span>
            {STAT_LABELS.map((label) => (
              <span key={label} className="microtext text-right text-subtle">
                {label}
              </span>
            ))}
            <span className="microtext hidden text-right text-subtle @4xl:block">Build</span>
            <span className="microtext text-center text-subtle">Score</span>
          </div>

          <ul aria-label="Match history">
            {matches.map((match) => (
              <MatchRow
                key={match.match_id}
                match={match}
                trackedPuuid={trackedPuuid}
                analysis={byMatch.get(match.match_id)}
              />
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
            <p role="alert" className="px-5 pb-4 text-sm text-danger">
              {history.error.message}
            </p>
          )}
        </>
      )}
    </Card>
  );
}
