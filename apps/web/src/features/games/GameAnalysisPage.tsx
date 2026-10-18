import { useQuery } from "@tanstack/react-query";
import { lazy, Suspense } from "react";
import { useParams } from "react-router";

import { NotFound } from "@/app/RouteError";
import { Card, Skeleton } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { ErrorState } from "@/components/ui/States";
import type { PremiumData, Review } from "@/features/snapshots/premiumData";
import { api, isApiError, unwrap } from "@/lib/api/client";

const GameAnalysis = lazy(() => import("./GameAnalysis").then((m) => ({ default: m.GameAnalysis })));

/** A match's analysis, in its own tab (`/analysis/:matchId`): opened from the history. */
export function GameAnalysisPage() {
  const { matchId = "" } = useParams();
  const analysis = useQuery({
    queryKey: ["games", "analysis", matchId],
    queryFn: () => unwrap(api.GET("/games/analyses/{match_id}", { params: { path: { match_id: matchId } } })),
    retry: false,
    // if it is still being analysed, it is checked again until it finishes
    refetchInterval: (query) => (query.state.data?.status === "processing" ? 4000 : false),
  });

  if (analysis.isPending) return <Skeleton className="h-96" />;
  if (analysis.isError) {
    if (isApiError(analysis.error, 404) || isApiError(analysis.error, 422)) return <NotFound />;
    return (
      <Card>
        <ErrorState error={analysis.error} onRetry={() => void analysis.refetch()} />
      </Card>
    );
  }
  const data = analysis.data;
  const result = data.result as unknown as PremiumData | null;
  const game = result?.games[0];

  return (
    <>
      <PageHeader title={game ? `${game.champion} analysis` : "Analysis"} />
      {data.status === "done" && result ? (
        <Suspense fallback={<Skeleton className="h-96" />}>
          <GameAnalysis result={result} review={(data.review ?? null) as Review | null} />
        </Suspense>
      ) : (
        <Card className="p-6 text-sm text-muted">
          {data.status === "processing" ? "Still reading your replay. This page updates by itself." : (data.error ?? "This game isn't analysed.")}
        </Card>
      )}
    </>
  );
}
