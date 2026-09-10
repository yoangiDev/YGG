import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash } from "lucide-react";
import { useState } from "react";

import { RankBadge, WinRate } from "@/components/player/PlayerBits";
import { Button } from "@/components/ui/Button";
import { Card, Skeleton } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Pager } from "@/components/ui/Pager";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { cn } from "@/lib/cn";
import { queryKeys } from "@/lib/queryKeys";
import { regionLabel } from "@/lib/roles";

import { usePageParam } from "./AdminUsersPage";

type AdminPlayer = Schemas["AdminPlayerOut"];

const PAGE_SIZE = 25;

export function AdminPlayersPage() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [page, setPage] = usePageParam();
  const [toDelete, setToDelete] = useState<AdminPlayer | null>(null);
  const offset = page * PAGE_SIZE;

  const players = useQuery({
    queryKey: queryKeys.admin.players(offset),
    queryFn: () => unwrap(api.GET("/admin/players/", { params: { query: { limit: PAGE_SIZE, offset } } })),
    placeholderData: keepPreviousData,
  });

  const remove = useMutation({
    mutationFn: (id: number) => unwrap(api.DELETE("/admin/players/{player_id}", { params: { path: { player_id: id } } })),
    onSuccess: () => {
      setToDelete(null);
      toast.success("Player deleted");
      void queryClient.invalidateQueries({ queryKey: queryKeys.admin.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.players });
    },
    onError: (error) => toast.error(error.message),
  });

  return (
    <Card>
      {players.isPending ? (
        <div className="flex flex-col gap-2 p-4">
          {Array.from({ length: 5 }, (_, index) => (
            <Skeleton key={index} className="h-11" />
          ))}
        </div>
      ) : players.isError ? (
        <ErrorState error={players.error} onRetry={() => void players.refetch()} />
      ) : players.data.total === 0 ? (
        <EmptyState title="No tracked players" />
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className={cn("w-full text-sm", players.isPlaceholderData && "opacity-60")}>
              <thead>
                <tr className="border-b border-border/60 text-left text-[11px] tracking-wider text-muted uppercase">
                  <th scope="col" className="px-4 py-3 font-semibold">
                    Player
                  </th>
                  <th scope="col" className="px-4 py-3 font-semibold">
                    Owner
                  </th>
                  <th scope="col" className="px-4 py-3 font-semibold">
                    Rank
                  </th>
                  <th scope="col" className="hidden px-4 py-3 font-semibold md:table-cell">
                    Record
                  </th>
                  <th scope="col" className="px-4 py-3">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {players.data.items.map((player) => (
                  <tr key={player.id} className="border-b border-border/40 last:border-0">
                    <td className="px-4 py-3">
                      <p className="font-semibold text-fg">
                        {player.game_name}
                        <span className="font-normal text-muted">#{player.tag_line}</span>
                      </p>
                      <p className="text-xs text-muted">
                        {regionLabel(player.region)}
                        {player.nickname ? ` · ${player.nickname}` : ""}
                      </p>
                    </td>
                    <td className="px-4 py-3 text-muted">{player.owner_username}</td>
                    <td className="px-4 py-3">
                      <RankBadge tier={player.tier} division={player.rank} lp={player.lp} size={28} />
                    </td>
                    <td className="hidden px-4 py-3 md:table-cell">
                      <WinRate wins={player.wins} losses={player.losses} compact />
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label={`Delete ${player.game_name}#${player.tag_line}`}
                        onClick={() => setToDelete(player)}
                      >
                        <Trash className="size-4" aria-hidden="true" />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pager page={page} pageSize={PAGE_SIZE} total={players.data.total} onPageChange={setPage} />
        </>
      )}
      <ConfirmDialog
        open={toDelete !== null}
        onOpenChange={(open) => {
          if (!open) setToDelete(null);
        }}
        title={`Delete ${toDelete ? `${toDelete.game_name}#${toDelete.tag_line}` : "player"}?`}
        description={`This removes the player from ${toDelete?.owner_username ?? "its owner"}'s account, with all its snapshots.`}
        loading={remove.isPending}
        onConfirm={() => {
          if (toDelete) remove.mutate(toDelete.id);
        }}
      />
    </Card>
  );
}
