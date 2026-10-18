import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Lock, RotateCw, Sparkles } from "lucide-react";
import { lazy, Suspense } from "react";

import { Button } from "@/components/ui/Button";
import { Card, CardHeader, ProgressBar, Skeleton } from "@/components/ui/Card";
import { ChampionIcon } from "@/components/player/PlayerBits";
import { ErrorState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/features/auth/AuthProvider";
import { HowToDownload, ReplayUpload, replayFile } from "@/features/games/ReplayUpload";
import { api, isApiError, unwrap } from "@/lib/api/client";
import { cn } from "@/lib/cn";
import { formatDateTime } from "@/lib/format";
import { queryKeys } from "@/lib/queryKeys";

import type { PremiumData, Review } from "./PremiumResult";

const ACTIVE = new Set(["queued", "processing"]);

/** What is seen under the padlock. It is made up on purpose: without replay access, real data is never requested or drawn. */
function FakePreview() {
  const bars = [62, 38, 81, 27, 55, 70, 44];
  return (
    <div aria-hidden="true" className="pointer-events-none select-none p-5 blur-[2.5px]">
      <p className="text-sm font-black text-text">Review · 12 games · ADC</p>
      <p className="mt-2 text-sm leading-relaxed text-soft">
        Your laning is solid, but 31% of your flashes go on skirmishes with a dragon up in less than a minute. When your
        support roams you lose 420 HP more than your tier average before the first back, and you take 38% of fights
        with an item deficit.
      </p>
      <div className="mt-4 grid grid-cols-2 gap-4">
        <div className="flex h-28 items-end gap-2 border border-line p-3">
          {bars.map((height, index) => (
            <div key={index} className="flex-1 bg-acid/70" style={{ height: `${height}%` }} />
          ))}
        </div>
        <svg viewBox="0 0 100 40" className="h-28 w-full border border-line p-3">
          <path d="M0 20 L12 18 L22 24 L35 14 L48 16 L60 8 L74 22 L86 12 L100 6" fill="none" stroke="currentColor" className="text-stat-gold" strokeWidth="2" />
        </svg>
      </div>
    </div>
  );
}

/** For accounts without replay access: the analysis in view but blurred, with the padlock on top. */
export function PremiumTeaser({
  className,
  title = "Replay analysis",
  text = "Not enabled for your account.",
}: {
  className?: string;
  title?: string;
  text?: string;
}) {
  return (
    <Card className={cn("relative overflow-hidden border-stat-gold/30", className)}>
      <FakePreview />
      <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-ink/85 p-6 text-center">
        <span className="grid size-12 place-items-center rounded-full border border-stat-gold/50 bg-stat-gold/15">
          <Lock className="size-6 text-stat-gold" aria-hidden="true" />
        </span>
        <p className="text-base font-black text-text">{title}</p>
        <p className="max-w-md text-sm text-soft">{text}</p>
      </div>
    </Card>
  );
}

/** Where it stands, according to what the API stores (app/service/premium.py: up to 90, the matches that have finished; from 90
 * to 100, the review). */
function stage(progress: number, waiting: number): string {
  if (progress >= 90) return "Writing your coach review";
  return waiting > 0 ? `${waiting} ${waiting === 1 ? "replay" : "replays"} to upload` : "Reading your replays";
}

/** State of the snapshot's replay analysis: launching it, its progress, and what comes out when it finishes. */
function PremiumAnalysis({ snapshotId }: { snapshotId: number }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const key = queryKeys.premium(snapshotId);

  const analysis = useQuery({
    queryKey: key,
    queryFn: async () => {
      try {
        return await unwrap(api.GET("/snapshots/{snapshot_id}/premium", { params: { path: { snapshot_id: snapshotId } } }));
      } catch (error) {
        if (isApiError(error, 404)) return null; // not requested yet
        throw error;
      }
    },
    // while it is running, it is queried every 2 s: each query advances it with the replays already analysed
    refetchInterval: (query) => (query.state.data && ACTIVE.has(query.state.data.status) ? 2000 : false),
  });

  const start = useMutation({
    mutationFn: () => unwrap(api.POST("/snapshots/{snapshot_id}/premium", { params: { path: { snapshot_id: snapshotId } } })),
    onSuccess: (queued) => queryClient.setQueryData(key, queued),
    onError: (error) => toast.error(error.message),
  });
  const skip = useMutation({
    mutationFn: () => unwrap(api.POST("/snapshots/{snapshot_id}/premium/skip", { params: { path: { snapshot_id: snapshotId } } })),
    onSuccess: (done) => queryClient.setQueryData(key, done),
    onError: (error) => toast.error(error.message),
  });

  if (analysis.isPending) return <Skeleton className="h-40" />;
  if (analysis.isError) return <Card><ErrorState error={analysis.error} onRetry={() => void analysis.refetch()} /></Card>;

  const data = analysis.data;
  return (
    <Card className="border-stat-gold/30">
      <CardHeader
        title="Replay analysis"
        description="Every replay decoded second by second, compared with players of your tier and role."
      />
      <div className="flex flex-col gap-4 p-4">
        {data === null && (
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-soft">This snapshot has no replay analysis yet.</p>
            <Button loading={start.isPending} onClick={() => start.mutate()}>
              {!start.isPending && <Sparkles className="size-4" aria-hidden="true" />}
              Run replay analysis
            </Button>
          </div>
        )}
        {data && ACTIVE.has(data.status) && (
          <div className="flex flex-col gap-3" aria-live="polite">
            <div className="flex justify-between text-sm">
              <span className="font-normal text-text">{stage(data.progress, data.waiting.length)}</span>
              <span className="text-muted tabular-nums">{data.progress}%</span>
            </div>
            <ProgressBar
              value={Math.max(data.progress, 2)}
              label="Replay analysis progress"
              className="h-2 rounded-full"
              barClassName="bg-stat-gold"
            />
            {data.waiting.length > 0 ? (
              <>
                <ul className="flex flex-col divide-y divide-line border border-line">
                  {data.waiting.map((game) => (
                    <li key={game.match_id} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2 text-sm">
                      <ChampionIcon name={game.champion} size={24} />
                      <span className="font-bold text-text">{game.champion}</span>
                      <span className="text-muted tabular-nums">{formatDateTime(game.played_at)}</span>
                      <code className="ml-auto text-xs text-muted">{replayFile(game.match_id)}</code>
                    </li>
                  ))}
                </ul>
                <div className="flex flex-col items-center gap-3">
                  <ReplayUpload expected={data.waiting.map((game) => game.match_id)} label="Upload the replays" />
                  <HowToDownload many />
                </div>
                <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line pt-3">
                  <p className="text-xs text-muted">Riot only keeps the replays of the current patch: older games can't be downloaded.</p>
                  <Button variant="ghost" size="sm" loading={skip.isPending} onClick={() => skip.mutate()}>
                    Finish with the ones uploaded
                  </Button>
                </div>
              </>
            ) : (
              <p className="text-xs text-muted">It keeps going if you leave this page.</p>
            )}
          </div>
        )}
        {data?.status === "error" && (
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p role="alert" className="text-sm text-stat-red">{data.error ?? "The replay analysis failed."}</p>
            <Button variant="outline" loading={start.isPending} onClick={() => start.mutate()}>
              {!start.isPending && <RotateCw className="size-4" aria-hidden="true" />}
              Retry
            </Button>
          </div>
        )}
        {data?.status === "done" && (
          <>
            <PremiumResult result={data.result ?? null} review={data.review ?? null} />
            <div className="flex justify-end border-t border-line pt-3">
              <Button variant="ghost" size="sm" loading={start.isPending} onClick={() => start.mutate()}>
                {!start.isPending && <RotateCw className="size-3.5" aria-hidden="true" />}
                Analyse again
              </Button>
            </div>
          </>
        )}
      </div>
    </Card>
  );
}

// Recharts goes in its own chunk, like the rest of the charts: it is only downloaded on opening a finished analysis.
const LazyPremiumResult = lazy(() => import("./PremiumResult").then((m) => ({ default: m.PremiumResult })));

function PremiumResult({ result, review }: { result: Record<string, unknown> | null; review: Record<string, unknown> | null }) {
  if (!result) return <p className="text-sm text-muted">The analysis is ready.</p>;
  return (
    <Suspense fallback={<Skeleton className="h-96" />}>
      {/* the shape of `result` and `review` is fixed by app/service/replays.py and app/service/review.py */}
      <LazyPremiumResult result={result as unknown as PremiumData} review={review as unknown as Review | null} />
    </Suspense>
  );
}

/** The replay analysis tab: the analysis for accounts with replay access and, for the rest, the padlock. */
export function PremiumPanel({ snapshotId }: { snapshotId: number }) {
  const { isPremium } = useAuth();
  return isPremium ? <PremiumAnalysis snapshotId={snapshotId} /> : <PremiumTeaser />;
}
