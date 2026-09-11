import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { lazy, Suspense, useState, type ComponentProps } from "react";
import { Link, useNavigate, useParams } from "react-router";

import { NotFound } from "@/app/RouteError";
import { ArrowIcon } from "@/components/ui/ArrowIcon";
import { Card, Skeleton } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { ErrorState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { api, isApiError, unwrap } from "@/lib/api/client";
import { parseId } from "@/lib/params";
import { queryKeys } from "@/lib/queryKeys";

import { updateCachedPlayer } from "./cache";
import { ChampionStatsPanel } from "./detail/ChampionStatsPanel";
import { MatchHistory } from "./detail/MatchHistory";
import { NotesPanel } from "./detail/NotesPanel";
import { PlayerHeader } from "./detail/PlayerHeader";
import { RoleSummaryPanel } from "./detail/RoleSummaryPanel";
import { SnapshotsPanel } from "./detail/SnapshotsPanel";

// El formulario de análisis (zod, react-hook-form, SSE) se descarga al abrir el diálogo.
const LazyCreateSnapshotDialog = lazy(() =>
  import("@/features/snapshots/CreateSnapshotDialog").then((m) => ({ default: m.CreateSnapshotDialog })),
);

function CreateSnapshotDialog(props: ComponentProps<typeof LazyCreateSnapshotDialog>) {
  if (!props.open) return null;
  return (
    <Suspense fallback={null}>
      <LazyCreateSnapshotDialog {...props} />
    </Suspense>
  );
}

export function PlayerDetailPage() {
  const playerId = parseId(useParams().playerId);
  if (playerId === null) return <NotFound />;
  return <PlayerDetail key={playerId} playerId={playerId} />;
}

function PlayerDetail({ playerId }: { playerId: number }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const navigate = useNavigate();
  const [analysisOpen, setAnalysisOpen] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const player = useQuery({
    queryKey: queryKeys.player(playerId),
    queryFn: () => unwrap(api.GET("/players/{player_id}", { params: { path: { player_id: playerId } } })),
  });

  const refresh = useMutation({
    mutationFn: () => unwrap(api.POST("/players/{player_id}/refresh", { params: { path: { player_id: playerId } } })),
    onSuccess: (updated) => {
      updateCachedPlayer(queryClient, updated);
      toast.success("Rank and icon updated");
    },
    onError: (error) => toast.error(error.message),
  });

  const remove = useMutation({
    mutationFn: () => unwrap(api.DELETE("/players/{player_id}", { params: { path: { player_id: playerId } } })),
    onSuccess: () => {
      toast.success("Player deleted");
      void navigate("/players", { replace: true });
      void queryClient.invalidateQueries({ queryKey: queryKeys.playerList() });
    },
    onError: (error) => toast.error(error.message),
  });

  if (player.isPending) return <PlayerSkeleton />;
  if (player.isError) {
    if (isApiError(player.error, 404)) return <NotFound />;
    return (
      <Card>
        <ErrorState error={player.error} onRetry={() => void player.refetch()} />
      </Card>
    );
  }

  return (
    <>
      <Link
        to="/players"
        className="microtext mb-5 inline-flex items-center gap-2 text-subtle transition-colors hover:text-acid"
      >
        <ArrowIcon direction="left" />
        All players
      </Link>

      <PlayerHeader
        player={player.data}
        refreshing={refresh.isPending}
        onRefresh={() => refresh.mutate()}
        onAnalyse={() => setAnalysisOpen(true)}
        onDelete={() => setConfirmDelete(true)}
      />

      <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1fr)_400px]">
        <MatchHistory playerId={playerId} />
        <aside className="flex min-w-0 flex-col gap-6" aria-label="Player statistics">
          <ChampionStatsPanel playerId={playerId} />
          <SnapshotsPanel playerId={playerId} onAnalyse={() => setAnalysisOpen(true)} />
          <RoleSummaryPanel playerId={playerId} />
          <NotesPanel key={player.data.notes ?? ""} player={player.data} />
        </aside>
      </div>

      <CreateSnapshotDialog playerId={playerId} open={analysisOpen} onOpenChange={setAnalysisOpen} />
      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title={`Delete ${player.data.game_name}#${player.data.tag_line}?`}
        description="Its snapshots are deleted too. Stored matches are kept for other players."
        loading={remove.isPending}
        onConfirm={() => remove.mutate()}
      />
    </>
  );
}

function PlayerSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading player" className="flex flex-col gap-6">
      <Skeleton className="h-52 w-full" />
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_400px]">
        <Skeleton className="h-[32rem]" />
        <Skeleton className="h-[32rem]" />
      </div>
    </div>
  );
}
