import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { GitCompareArrows, Sparkles, Trash } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";

import { ArrowIcon } from "@/components/ui/ArrowIcon";
import { Button, buttonClasses } from "@/components/ui/Button";
import { Card, CardHeader, Skeleton } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { formatDate } from "@/lib/format";
import { queryKeys } from "@/lib/queryKeys";

type Snapshot = Schemas["SnapshotResponse"];

export function SnapshotsPanel({ playerId, onAnalyse }: { playerId: number; onAnalyse: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [selected, setSelected] = useState<number[]>([]);
  const [toDelete, setToDelete] = useState<Snapshot | null>(null);

  const snapshots = useQuery({
    queryKey: queryKeys.snapshots(playerId),
    queryFn: () =>
      unwrap(api.GET("/snapshots/player/{player_id}", { params: { path: { player_id: playerId }, query: { limit: 100 } } })),
  });

  const remove = useMutation({
    mutationFn: (snapshotId: number) =>
      unwrap(api.DELETE("/snapshots/{snapshot_id}", { params: { path: { snapshot_id: snapshotId } } })),
    onSuccess: async (_, snapshotId) => {
      setToDelete(null);
      setSelected((current) => current.filter((id) => id !== snapshotId));
      toast.success("Snapshot deleted");
      await queryClient.invalidateQueries({ queryKey: queryKeys.snapshots(playerId) });
    },
    onError: (error) => toast.error(error.message),
  });

  // Como mucho dos seleccionados: al marcar un tercero se descarta el más antiguo.
  const toggle = (snapshotId: number) =>
    setSelected((current) =>
      current.includes(snapshotId) ? current.filter((id) => id !== snapshotId) : [...current.slice(-1), snapshotId],
    );

  const items = snapshots.data?.items ?? [];
  const [first, second] = selected
    .map((id) => items.find((snapshot) => snapshot.id === id))
    .filter((snapshot): snapshot is Snapshot => snapshot !== undefined)
    .sort((a, b) => a.date_from.localeCompare(b.date_from));

  return (
    <Card>
      <CardHeader
        title="Snapshots"
        description={items.length > 1 ? "Tick two periods to compare them." : "Each analysis freezes a period of games."}
        action={
          first && second ? (
            <Link
              to={`/players/${playerId}/snapshots/compare?a=${first.id}&b=${second.id}`}
              className={buttonClasses({ variant: "primary", size: "sm" })}
            >
              <GitCompareArrows className="size-3.5" aria-hidden="true" />
              Compare
            </Link>
          ) : undefined
        }
      />
      {snapshots.isPending ? (
        <div className="flex flex-col gap-3 p-5" aria-hidden="true">
          <Skeleton className="h-12" />
          <Skeleton className="h-12" />
        </div>
      ) : snapshots.isError ? (
        <ErrorState error={snapshots.error} onRetry={() => void snapshots.refetch()} />
      ) : items.length === 0 ? (
        <EmptyState
          icon={<Sparkles className="size-6" />}
          title="No analyses yet"
          description="Pick a date range and YGG will download and analyse those games."
          action={
            <Button size="sm" arrow onClick={onAnalyse}>
              Run the first analysis
            </Button>
          }
        />
      ) : (
        <ul>
          {items.map((snapshot) => {
            const range = `${formatDate(snapshot.date_from)} – ${formatDate(snapshot.date_to)}`;
            const isSelected = selected.includes(snapshot.id);
            return (
              <li
                key={snapshot.id}
                className="group flex items-center gap-3 border-b border-line px-5 py-3.5 transition-colors last:border-b-0 hover:bg-white/[0.025]"
              >
                <input
                  type="checkbox"
                  className="size-4 shrink-0 cursor-pointer accent-[#c8f53f]"
                  checked={isSelected}
                  onChange={() => toggle(snapshot.id)}
                  aria-label={`Select ${range} for comparison`}
                />
                <Link to={`/players/${playerId}/snapshots/${snapshot.id}`} className="min-w-0 flex-1">
                  <p className="truncate text-sm font-extrabold text-text transition-colors group-hover:text-acid">{range}</p>
                  <p className="mt-0.5 truncate text-xs text-subtle">
                    {snapshot.match_count} games
                    {snapshot.description ? ` · ${snapshot.description}` : ""}
                  </p>
                </Link>
                <ArrowIcon className="text-subtle transition-colors group-hover:text-acid" />
                <Button variant="ghost" size="icon" aria-label={`Delete snapshot ${range}`} onClick={() => setToDelete(snapshot)}>
                  <Trash className="size-3.5" aria-hidden="true" />
                </Button>
              </li>
            );
          })}
        </ul>
      )}
      <ConfirmDialog
        open={toDelete !== null}
        onOpenChange={(open) => {
          if (!open) setToDelete(null);
        }}
        title="Delete this snapshot?"
        description="The analysis is removed. Its matches stay stored and are reused by future analyses."
        loading={remove.isPending}
        onConfirm={() => {
          if (toDelete) remove.mutate(toDelete.id);
        }}
      />
    </Card>
  );
}
