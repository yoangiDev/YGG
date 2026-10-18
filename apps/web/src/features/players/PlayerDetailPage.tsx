import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { lazy, Suspense, useState, type ComponentProps } from "react";
import { useNavigate } from "react-router";

import { NotFound } from "@/app/RouteError";
import { Card, Skeleton } from "@/components/ui/Card";
import { ErrorState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/features/auth/AuthProvider";
import { PremiumTeaser } from "@/features/snapshots/PremiumPanel";
import { api, isApiError, unwrap } from "@/lib/api/client";
import { queryKeys } from "@/lib/queryKeys";

import { setActiveAccount } from "./accounts";
import { updateCachedPlayer } from "./cache";
import { ChampionStatsPanel } from "./detail/ChampionStatsPanel";
import { MatchHistory } from "./detail/MatchHistory";
import { PlayerHeader } from "./detail/PlayerHeader";
import { RoleSummaryPanel } from "./detail/RoleSummaryPanel";
import { SnapshotsPanel } from "./detail/SnapshotsPanel";
import { UnlinkDialog } from "./UnlinkDialog";

// The analysis form (zod, react-hook-form, SSE) is downloaded when the dialog opens.
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

/** Your linked account's page (`AccountPage` opens it directly: there is one per YGG account). */
export function PlayerDetail({ playerId }: { playerId: number }) {
  const { isPremium } = useAuth();
  const queryClient = useQueryClient();
  const toast = useToast();
  const navigate = useNavigate();
  const [snapshotOpen, setSnapshotOpen] = useState(false);
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
      toast.success("Account unlinked");
      setActiveAccount(null); // the active one becomes the first that remains
      void navigate("/account", { replace: true });
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
      <PlayerHeader
        player={player.data}
        refreshing={refresh.isPending}
        onRefresh={() => refresh.mutate()}
        onDelete={() => setConfirmDelete(true)}
      />

      {/* items-start: without it, the history stretches to the height of the side column and leaves an empty gap. */}
      <div className="mt-6 grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_400px]">
        <div className="min-w-0">
          <MatchHistory playerId={playerId} trackedPuuid={player.data.puuid} />
        </div>
        <aside className="flex min-w-0 flex-col gap-6" aria-label="Player statistics">
          {isPremium ? (
            <SnapshotsPanel playerId={playerId} onAnalyse={() => setSnapshotOpen(true)} />
          ) : (
            <PremiumTeaser />
          )}
          <ChampionStatsPanel playerId={playerId} />
          <RoleSummaryPanel playerId={playerId} />
        </aside>
      </div>

      <CreateSnapshotDialog
        playerId={playerId}
        playerName={`${player.data.game_name}#${player.data.tag_line}`}
        open={snapshotOpen}
        onOpenChange={setSnapshotOpen}
      />
      <UnlinkDialog
        player={player.data}
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
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
