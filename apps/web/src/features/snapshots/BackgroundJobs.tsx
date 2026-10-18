import { useQueryClient } from "@tanstack/react-query";
import { X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";

import { ProgressBar } from "@/components/ui/Card";
import { useToast } from "@/components/ui/Toast";
import { useGameAnalyses, type Analysis } from "@/features/games/analyses";
import { queryKeys } from "@/lib/queryKeys";

import { describeJob, removeBackgroundJob, useBackgroundJobs, useJobProgress, type BackgroundJob } from "./jobProgress";

/** Analyses still running after their window is closed: bottom right, on any screen. */
export function BackgroundJobs() {
  const jobs = useBackgroundJobs();
  const games = useGameAnalyses().data?.items;
  const analysing = (games ?? []).filter((game) => game.status === "processing");
  useFinishedGames(games);
  if (jobs.length === 0 && analysing.length === 0) return null;
  return (
    <aside aria-label="Analyses in progress" className="fixed right-4 bottom-4 z-[100] flex w-72 max-w-[calc(100vw-2rem)] flex-col gap-2">
      {analysing.map((game) => (
        <GameAnalysisCard key={game.match_id} game={game} />
      ))}
      {jobs.map((job) => (
        <BackgroundJobCard key={job.jobId} job={job} />
      ))}
    </aside>
  );
}

/** Notifies when a match that was being analysed finishes (or fails): its card disappears and this says how it went. */
function useFinishedGames(games: Analysis[] | undefined) {
  const toast = useToast();
  const before = useRef<Map<string, string> | null>(null);
  useEffect(() => {
    if (!games) return;
    const now = new Map(games.map((game) => [game.match_id, game.status]));
    for (const game of games) {
      if (before.current?.get(game.match_id) !== "processing") continue;
      if (game.status === "done") toast.success("Your analysis is ready");
      else if (game.status === "error") toast.error(game.error ?? "The game couldn't be analysed.");
    }
    before.current = now;
  }, [games, toast]);
}

// ponytail: the API doesn't say how far along it is (decoding is 30-60 s); the bar is a time-based estimate, which doesn't reach
// 100 until it finishes. If it is really needed, have the API store the step it is at.
const ESTIMATED_SECONDS = 50;

function GameAnalysisCard({ game }: { game: Analysis }) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => setElapsed((seconds) => seconds + 1), 1000);
    return () => clearInterval(timer);
  }, []);
  const progress = Math.min(95, (elapsed / ESTIMATED_SECONDS) * 100);
  return (
    <div role="status" className="border border-line bg-popover p-3 shadow-popover">
      <div className="flex items-center justify-between gap-3">
        <p className="min-w-0 truncate text-xs font-bold text-text">Analysing your replay</p>
        <span className="shrink-0 text-xs text-muted tabular-nums">{Math.round(progress)}%</span>
      </div>
      <p className="mt-0.5 text-xs text-muted">{game.match_id.replace("_", "-")}</p>
      <ProgressBar value={progress} label="Analysis of your replay" className="mt-2" />
    </div>
  );
}

function BackgroundJobCard({ job }: { job: BackgroundJob }) {
  const { status, error } = useJobProgress(job.jobId);
  const queryClient = useQueryClient();
  const snapshotId = status?.status === "done" ? (status.snapshot_id ?? null) : null;
  const done = status?.status === "done";
  const failed = status?.status === "error" || error !== null;
  const progress = done ? 100 : (status?.progress ?? 0);

  useEffect(() => {
    if (done) void queryClient.invalidateQueries({ queryKey: queryKeys.snapshots(job.playerId) });
  }, [done, job.playerId, queryClient]);

  return (
    <div role="status" className="border border-line bg-popover p-3 shadow-popover">
      <div className="flex items-center justify-between gap-3">
        <p className="min-w-0 truncate text-xs font-bold text-text">{job.playerName}</p>
        {done || failed ? (
          <button
            type="button"
            aria-label={`Dismiss the analysis of ${job.playerName}`}
            onClick={() => removeBackgroundJob(job.jobId)}
            className="grid size-6 shrink-0 cursor-pointer place-items-center text-subtle transition hover:text-text"
          >
            <X className="size-3.5" aria-hidden="true" />
          </button>
        ) : (
          <span className="shrink-0 text-xs text-muted tabular-nums">{Math.round(progress)}%</span>
        )}
      </div>
      <p className="mt-0.5 text-xs text-muted">{failed ? "Analysis failed" : describeJob(status)}</p>
      <ProgressBar
        value={progress}
        label={`Analysis of ${job.playerName}`}
        className="mt-2"
        barClassName={failed ? "bg-none bg-stat-red" : undefined}
      />
      {snapshotId !== null && (
        <Link
          to={`/players/${job.playerId}/snapshots/${snapshotId}`}
          onClick={() => removeBackgroundJob(job.jobId)}
          className="mt-2 inline-block text-xs font-bold text-acid hover:underline"
        >
          Open analysis
        </Link>
      )}
    </div>
  );
}
