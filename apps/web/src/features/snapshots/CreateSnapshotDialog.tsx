import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { RotateCw } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router";
import { z } from "zod";

import { Button } from "@/components/ui/Button";
import { ProgressBar } from "@/components/ui/Card";
import { Field, Input } from "@/components/ui/Field";
import { Dialog } from "@/components/ui/Overlay";
import { useToast } from "@/components/ui/Toast";
import { api, unwrap } from "@/lib/api/client";
import { dateInputToUnix, toDateInput } from "@/lib/format";
import { queryKeys } from "@/lib/queryKeys";

import { useJobProgress, type JobStatus } from "./jobProgress";

function nowUnix(): number {
  return Math.floor(Date.now() / 1000);
}

function daysAgo(days: number): string {
  const date = new Date();
  date.setUTCDate(date.getUTCDate() - days);
  return toDateInput(date);
}

const PRESETS = [
  { label: "Last 7 days", days: 7 },
  { label: "Last 30 days", days: 30 },
  { label: "Last 90 days", days: 90 },
] as const;

const schema = z
  .object({
    dateFrom: z.string().min(1, "Pick a start date"),
    dateTo: z.string().min(1, "Pick an end date"),
    description: z.string().trim().max(200, "Use at most 200 characters"),
  })
  .refine((values) => values.dateFrom <= values.dateTo, {
    path: ["dateTo"],
    message: "The end date must be after the start date",
  })
  .refine((values) => values.dateFrom <= toDateInput(new Date()), {
    path: ["dateFrom"],
    message: "The start date cannot be in the future",
  });

function SnapshotForm({ playerId, onQueued }: { playerId: number; onQueued: (jobId: string) => void }) {
  const [formError, setFormError] = useState<string | null>(null);
  const today = toDateInput(new Date());
  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: zodResolver(schema),
    defaultValues: { dateFrom: daysAgo(30), dateTo: today, description: "" },
  });

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    const now = nowUnix();
    try {
      const job = await unwrap(
        api.POST("/snapshots/", {
          body: {
            player_id: playerId,
            date_from: dateInputToUnix(values.dateFrom),
            date_to: Math.min(dateInputToUnix(values.dateTo, true), now),
            description: values.description,
          },
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
        <p role="alert" className="rounded-lg border border-stat-red/40 bg-stat-red/10 px-3 py-2 text-sm text-stat-red">
          {formError}
        </p>
      )}
      <div role="group" aria-label="Date presets" className="flex flex-wrap gap-1.5">
        {PRESETS.map((preset) => (
          <button
            key={preset.days}
            type="button"
            className="cursor-pointer rounded-full border border-border px-3 py-1 text-xs font-semibold text-muted transition hover:border-primary/60 hover:text-fg"
            onClick={() => {
              setValue("dateFrom", daysAgo(preset.days), { shouldValidate: true });
              setValue("dateTo", today, { shouldValidate: true });
            }}
          >
            {preset.label}
          </button>
        ))}
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="From" error={errors.dateFrom?.message}>
          {(props) => <Input {...props} type="date" max={today} {...register("dateFrom")} />}
        </Field>
        <Field label="To" error={errors.dateTo?.message}>
          {(props) => <Input {...props} type="date" max={today} {...register("dateTo")} />}
        </Field>
      </div>
      <Field label="Description" error={errors.description?.message}>
        {(props) => <Input {...props} placeholder="Optional, e.g. “Before bootcamp”" {...register("description")} />}
      </Field>
      <p className="text-xs text-muted">
        Matches already stored are reused. Only new games are downloaded from Riot, so repeated ranges are fast.
      </p>
      <div className="mt-1 flex justify-end">
        <Button type="submit" loading={isSubmitting}>
          Start analysis
        </Button>
      </div>
    </form>
  );
}

function describe(status: JobStatus | null): string {
  if (!status) return "Connecting…";
  switch (status.status) {
    case "queued":
      return "Queued, waiting for a worker";
    case "processing":
      if (status.progress < 10) return "Finding ranked games";
      if (status.progress < 90) return "Downloading matches and timelines";
      return "Computing metrics";
    case "done":
      return "Analysis complete";
    case "error":
      return "Analysis failed";
  }
}

function JobProgressView({
  jobId,
  playerId,
  onRetried,
  onClose,
}: {
  jobId: string;
  playerId: number;
  onRetried: (jobId: string) => void;
  onClose: () => void;
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
  const failure = status?.error ?? (error instanceof Error ? error.message : null);
  const progress = done ? 100 : (status?.progress ?? 0);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-4 text-sm" aria-live="polite">
        <span className="font-medium text-fg">{failed ? "Analysis failed" : describe(status)}</span>
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
        <p role="alert" className="rounded-lg border border-stat-red/40 bg-stat-red/10 px-3 py-2 text-sm text-stat-red">
          {failure ?? "Something went wrong while analysing the games."}
        </p>
      )}
      {!done && !failed && (
        <p className="text-xs text-muted">You can close this window. The analysis keeps running on the server.</p>
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
  open,
  onOpenChange,
}: {
  playerId: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const queryClient = useQueryClient();
  // `attempt` fuerza a montar de nuevo el seguimiento aunque el reintento conserve el mismo job_id.
  const [job, setJob] = useState<{ id: string; attempt: number } | null>(null);

  const handleOpenChange = (next: boolean) => {
    if (!next) {
      if (job) void queryClient.invalidateQueries({ queryKey: queryKeys.snapshots(playerId) });
      setJob(null);
    }
    onOpenChange(next);
  };

  return (
    <Dialog
      open={open}
      onOpenChange={handleOpenChange}
      title="New analysis"
      description="YGG downloads the ranked games in this period and computes timeline metrics."
    >
      {job ? (
        <JobProgressView
          key={`${job.id}:${job.attempt}`}
          jobId={job.id}
          playerId={playerId}
          onRetried={(id) => setJob((current) => ({ id, attempt: (current?.attempt ?? 0) + 1 }))}
          onClose={() => handleOpenChange(false)}
        />
      ) : (
        <SnapshotForm playerId={playerId} onQueued={(id) => setJob({ id, attempt: 0 })} />
      )}
    </Dialog>
  );
}
