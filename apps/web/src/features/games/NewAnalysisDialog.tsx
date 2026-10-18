import { useQuery } from "@tanstack/react-query";
import { Loader2, Sparkles } from "lucide-react";
import { useState } from "react";

import { Dialog } from "@/components/ui/Overlay";
import { Skeleton } from "@/components/ui/Card";
import { ErrorState } from "@/components/ui/States";
import { useAuth } from "@/features/auth/AuthProvider";
import { ratingColor } from "@/features/snapshots/GameCard";
import { PremiumTeaser } from "@/features/snapshots/PremiumPanel";
import { api, unwrap } from "@/lib/api/client";
import { cn } from "@/lib/cn";
import { queryKeys } from "@/lib/queryKeys";

import { eligible, scoreOf, spent, untilLabel, useGameAnalyses, type Match } from "./analyses";
import { GameLine, UploadReplayDialog } from "./UploadReplayDialog";

const HISTORY = 100;

/** "New analysis": the current patch's matches, with just enough to recognise them; choosing one asks for its
 * replay. Without replay access, the padlock goes below. */
export function NewAnalysisDialog({ playerId, open, onOpenChange }: { playerId: number; open: boolean; onOpenChange: (open: boolean) => void }) {
  const { isPremium } = useAuth();
  const [picked, setPicked] = useState<Match | null>(null);
  // the same query (and cache) the snapshots dialog uses
  const history = useQuery({
    queryKey: [...queryKeys.playerMatches(playerId), "sessions"],
    queryFn: () =>
      unwrap(api.GET("/matches/player/{player_id}", { params: { path: { player_id: playerId }, query: { limit: HISTORY } } })),
    enabled: open,
    staleTime: 5 * 60_000,
  });
  const analyses = useGameAnalyses();
  const quota = analyses.data?.quota;
  const byMatch = new Map((analyses.data?.items ?? []).map((a) => [a.match_id, a]));
  const games = eligible(history.data ?? []);
  const outOfQuota = spent(quota);

  return (
    <>
      <Dialog
        open={open}
        onOpenChange={onOpenChange}
        title="New analysis"
        description="Pick a game and upload its replay, which you download from your League client."
      >
        {quota && quota.limit !== null && (
          <p className={cn("mb-3 text-xs tabular-nums", outOfQuota ? "text-stat-red" : "text-muted")} aria-live="polite">
            {Math.max(0, quota.limit - quota.used)} of {quota.limit} left today
            {outOfQuota && quota.next_at ? ` · next in ${untilLabel(quota.next_at)}` : ""}
          </p>
        )}
        {history.isPending ? (
          <Skeleton className="h-40" />
        ) : history.isError ? (
          <ErrorState error={history.error} onRetry={() => void history.refetch()} />
        ) : games.length === 0 ? (
          <p className="text-sm text-muted">No ranked games in the current patch.</p>
        ) : (
          <ul className="flex max-h-80 flex-col gap-1.5 overflow-y-auto pr-1">
            {games.map((match) => {
              const analysis = byMatch.get(match.match_id);
              const score = scoreOf(analysis);
              const taken = analysis?.status === "processing" || analysis?.status === "done";
              return (
                <li key={match.match_id}>
                  <button
                    type="button"
                    aria-label={`Analyse ${match.champion} game`}
                    disabled={taken || (outOfQuota && analysis === undefined)}
                    onClick={() => setPicked(match)}
                    className="flex w-full cursor-pointer items-center gap-3 border border-line px-3 py-2 text-left transition hover:border-acid/60 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:border-line"
                  >
                    <GameLine match={match} />
                    <span className="ml-auto flex shrink-0 items-center gap-1.5 text-xs font-bold">
                      {score !== undefined ? (
                        <span className="text-lg font-black tabular-nums" style={{ color: ratingColor(score) }}>
                          {score}
                        </span>
                      ) : analysis?.status === "processing" ? (
                        <Loader2 className="size-4 animate-spin text-stat-gold" aria-label="Analysing" />
                      ) : (
                        <Sparkles className="size-4 text-acid" aria-hidden="true" />
                      )}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
        {!isPremium && <PremiumTeaser className="mt-4" />}
      </Dialog>
      <UploadReplayDialog
        match={picked}
        onClose={() => setPicked(null)}
        onUploaded={() => onOpenChange(false)}
      />
    </>
  );
}
