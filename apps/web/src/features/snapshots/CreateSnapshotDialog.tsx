import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RotateCw } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router";
import { z } from "zod";

import { ChampionIcon } from "@/components/player/PlayerBits";
import { Button } from "@/components/ui/Button";
import { ProgressBar, Skeleton } from "@/components/ui/Card";
import { Field, Input } from "@/components/ui/Field";
import { Dialog } from "@/components/ui/Overlay";
import { ErrorState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/features/auth/AuthProvider";
import { api, unwrap } from "@/lib/api/client";
import { cn } from "@/lib/cn";
import { LOCALE } from "@/lib/format";
import { queryKeys } from "@/lib/queryKeys";

import { addBackgroundJob, describeJob, useJobProgress } from "./jobProgress";
import { PremiumTeaser } from "./PremiumPanel";
import { type BuildGroup, buildLabel, groupSessions, periodOf, sessionRange } from "./sessions";

const HISTORY = 100; // the matches shown in sessions: the API gives at most 100 per page

const schema = z.object({ description: z.string().trim().max(200, "Use at most 200 characters") });

const sessionsKey = (playerId: number) => [...queryKeys.playerMatches(playerId), "sessions"] as const;

/** "Today", "Yesterday" or "Mon, 6 Oct", of the day YYYY-MM-DD in local time. */
function dayLabel(day: string): string {
  const date = new Date(`${day}T00:00:00`); // no zone: local midnight of that day
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const diff = Math.round((today.getTime() - date.getTime()) / 86_400_000);
  if (diff === 0) return "Today";
  if (diff === 1) return "Yesterday";
  return date.toLocaleDateString(LOCALE, { weekday: "short", day: "numeric", month: "short" });
}

type Selection = { anchor: string; end: string } | null;

/** The history in one-day sessions, split by build, as on DPM: one click picks a day, another on the same
 * build closes the stretch, and one on another build starts again (a snapshot doesn't cross builds). */
function SessionPicker({ groups, selected, onSelect }: { groups: BuildGroup[]; selected: Selection; onSelect: (s: Selection) => void }) {
  const chosenGroup = selected ? groups.find((g) => g.sessions.some((s) => s.key === selected.anchor)) : undefined;
  const chosen = new Set(
    chosenGroup && selected ? sessionRange(chosenGroup, selected.anchor, selected.end).map((s) => s.key) : [],
  );

  function pick(key: string, group: BuildGroup) {
    if (!selected || chosenGroup !== group || selected.anchor !== selected.end) onSelect({ anchor: key, end: key });
    else onSelect({ anchor: selected.anchor, end: key });
  }

  return (
    <div className="flex max-h-[22rem] flex-col gap-3 overflow-y-auto pr-1">
      {groups.map((group) => (
        <section key={group.build || "unknown"} aria-label={buildLabel(group, groups)}>
          <p className="eyebrow mb-1.5">{buildLabel(group, groups)}</p>
          <ul className="flex flex-col gap-1">
            {group.sessions.map((session) => {
              const losses = session.games.length - session.wins;
              const on = chosen.has(session.key);
              return (
                <li key={session.key}>
                  <button
                    type="button"
                    aria-pressed={on}
                    disabled={!group.build}
                    onClick={() => pick(session.key, group)}
                    className={cn(
                      "flex w-full cursor-pointer items-center gap-3 border px-3 py-2 text-left transition disabled:cursor-not-allowed disabled:opacity-50",
                      on ? "border-acid/70 bg-acid/10" : "border-line hover:border-line-button",
                    )}
                  >
                    <span className="w-24 shrink-0 text-sm font-bold text-text">{dayLabel(session.day)}</span>
                    <span className="w-28 shrink-0 text-xs text-muted tabular-nums">
                      {session.games.length} game{session.games.length === 1 ? "" : "s"} ·{" "}
                      <span className="text-stat-green">{session.wins}W</span>{" "}
                      <span className="text-stat-red">{losses}L</span>
                    </span>
                    <span className="flex min-w-0 flex-wrap gap-1">
                      {session.games.map((g) => (
                        <ChampionIcon
                          key={g.match_id}
                          name={g.champion}
                          size={22}
                          className={cn("ring-1", g.win ? "ring-stat-green/60" : "ring-stat-red/60")}
                        />
                      ))}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </div>
  );
}

function SnapshotForm({ playerId, onQueued }: { playerId: number; onQueued: (jobId: string) => void }) {
  const [formError, setFormError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Selection>(null);
  const history = useQuery({
    queryKey: sessionsKey(playerId),
    queryFn: () =>
      unwrap(api.GET("/matches/player/{player_id}", { params: { path: { player_id: playerId }, query: { limit: HISTORY } } })),
    staleTime: 5 * 60_000,
  });
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm({ resolver: zodResolver(schema), defaultValues: { description: "" } });

  const groups = groupSessions(history.data ?? []);
  const group = selected ? groups.find((g) => g.sessions.some((s) => s.key === selected.anchor)) : undefined;
  const sessions = group && selected ? sessionRange(group, selected.anchor, selected.end) : [];
  const games = sessions.reduce((n, s) => n + s.games.length, 0);
  const wins = sessions.reduce((n, s) => n + s.wins, 0);

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    if (sessions.length === 0) {
      setFormError("Pick at least one session.");
      return;
    }
    try {
      const job = await unwrap(
        api.POST("/snapshots/", {
          body: { player_id: playerId, ...periodOf(sessions), description: values.description, premium: true },
        }),
      );
      onQueued(job.job_id);
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Could not start the analysis.");
    }
  });

  return (
    <form className="flex flex-col gap-4" noValidate onSubmit={(event) => void onSubmit(event)}>
      {formError && (
        <p role="alert" className="border border-stat-red/40 bg-stat-red/10 px-3 py-2 text-sm text-stat-red">
          {formError}
        </p>
      )}
      {history.isPending ? (
        <Skeleton className="h-40" />
      ) : history.isError ? (
        <ErrorState error={history.error} onRetry={() => void history.refetch()} />
      ) : groups.length === 0 ? (
        <p className="text-sm text-muted">No ranked games in your history yet.</p>
      ) : (
        <SessionPicker groups={groups} selected={selected} onSelect={setSelected} />
      )}
      <p className="text-xs text-muted" aria-live="polite">
        {sessions.length === 0
          ? "Click a day to pick it, and another day of the same patch to take everything in between."
          : `${sessions.length} session${sessions.length === 1 ? "" : "s"} · ${games} games · ${wins}W ${games - wins}L`}
      </p>
      <Field label="Description" error={errors.description?.message}>
        {(props) => <Input {...props} placeholder="Optional, e.g. “Before bootcamp”" {...register("description")} />}
      </Field>
      <div className="mt-1 flex justify-end">
        <Button type="submit" loading={isSubmitting} disabled={sessions.length === 0}>
          Start analysis
        </Button>
      </div>
    </form>
  );
}

function JobProgressView({
  jobId,
  playerId,
  onRetried,
  onClose,
  onFinished,
}: {
  jobId: string;
  playerId: number;
  onRetried: (jobId: string) => void;
  onClose: () => void;
  onFinished: () => void;
}) {
  const { status, error } = useJobProgress(jobId);
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const toast = useToast();
  const finished = useRef(false);

  const retry = useMutation({
    mutationFn: () => unwrap(api.POST("/snapshots/jobs/{job_id}/retry", { params: { path: { job_id: jobId } } })),
    onSuccess: (retried) => onRetried(retried.job_id),
    onError: (retryError) => toast.error(retryError.message),
  });

  const done = status?.status === "done";
  const snapshotId = done ? (status.snapshot_id ?? null) : null;

  useEffect(() => {
    if (!done || finished.current) return;
    finished.current = true;
    void queryClient.invalidateQueries({ queryKey: queryKeys.snapshots(playerId) });
    toast.success("Analysis ready");
    if (snapshotId !== null) void navigate(`/players/${playerId}/snapshots/${snapshotId}`);
  }, [done, snapshotId, playerId, queryClient, toast, navigate]);

  const failed = status?.status === "error" || error !== null;
  useEffect(() => {
    if (done || failed) onFinished();
  }, [done, failed, onFinished]);
  const failure = status?.error ?? (error instanceof Error ? error.message : null);
  const progress = done ? 100 : (status?.progress ?? 0);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-4 text-sm" aria-live="polite">
        <span className="font-normal text-text">{failed ? "Analysis failed" : describeJob(status)}</span>
        <span className="text-muted tabular-nums">{Math.round(progress)}%</span>
      </div>
      <ProgressBar
        value={progress}
        label="Analysis progress"
        barClassName={failed ? "bg-none bg-stat-red" : undefined}
      />
      {status && status.attempts > 1 && !failed && (
        <p className="text-xs text-muted">Attempt {status.attempts}: the Riot API was busy, so the worker is retrying.</p>
      )}
      {failed && (
        <p role="alert" className="border border-stat-red/40 bg-stat-red/10 px-3 py-2 text-sm text-stat-red">
          {failure ?? "Something went wrong while analysing the games."}
        </p>
      )}
      {!done && !failed && (
        <p className="text-xs text-muted">You can close this window: the analysis keeps running and its progress stays in the corner.</p>
      )}
      <div className="flex justify-end gap-2">
        <Button variant="ghost" onClick={onClose}>
          {done || failed ? "Close" : "Run in background"}
        </Button>
        {status?.status === "error" && (
          <Button loading={retry.isPending} onClick={() => retry.mutate()}>
            {!retry.isPending && <RotateCw className="size-4" aria-hidden="true" />}
            Retry
          </Button>
        )}
      </div>
    </div>
  );
}

export function CreateSnapshotDialog({
  playerId,
  playerName,
  open,
  onOpenChange,
}: {
  playerId: number;
  playerName: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const { isPremium } = useAuth();
  // `attempt` forces the tracking to be mounted again even if the retry keeps the same job_id.
  const [job, setJob] = useState<{ id: string; attempt: number } | null>(null);
  const finished = useRef(false);
  const markFinished = useCallback(() => {
    finished.current = true;
  }, []);

  const handleOpenChange = (next: boolean) => {
    if (!next) {
      if (job) void queryClient.invalidateQueries({ queryKey: queryKeys.snapshots(playerId) });
      // If it is still running, its progress moves to the box at the bottom right.
      if (job && !finished.current) addBackgroundJob({ jobId: job.id, playerId, playerName });
      setJob(null);
    }
    onOpenChange(next);
  };

  return (
    <Dialog
      open={open}
      onOpenChange={handleOpenChange}
      title="New snapshot"
      description="Pick the days to analyse. A snapshot stays within one patch build."
    >
      {!isPremium ? (
        <PremiumTeaser />
      ) : job ? (
        <JobProgressView
          key={`${job.id}:${job.attempt}`}
          jobId={job.id}
          playerId={playerId}
          onRetried={(id) => {
            finished.current = false;
            setJob((current) => ({ id, attempt: (current?.attempt ?? 0) + 1 }));
          }}
          onClose={() => handleOpenChange(false)}
          onFinished={markFinished}
        />
      ) : (
        <SnapshotForm
          playerId={playerId}
          onQueued={(id) => {
            finished.current = false;
            setJob({ id, attempt: 0 });
          }}
        />
      )}
    </Dialog>
  );
}
