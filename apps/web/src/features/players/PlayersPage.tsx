import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, RefreshCw, Search, Trash, Users } from "lucide-react";
import { useDeferredValue, useMemo, useState } from "react";
import { Link } from "react-router";

import { PageHeader } from "@/app/AppLayout";
import { ProfileIcon, RankBadge, RoleIcon, WinRate } from "@/components/player/PlayerBits";
import { Button } from "@/components/ui/Button";
import { Card, Skeleton } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Input, Select } from "@/components/ui/Field";
import { Tooltip } from "@/components/ui/Overlay";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { queryKeys } from "@/lib/queryKeys";
import { rankScore } from "@/lib/rank";
import { regionLabel } from "@/lib/roles";

import { AddPlayerDialog } from "./AddPlayerDialog";
import { updateCachedPlayer } from "./cache";

type Player = Schemas["PlayerResponse"];
type SortKey = "rank" | "name" | "recent";

const SORTERS: Record<SortKey, (a: Player, b: Player) => number> = {
  rank: (a, b) => rankScore(b.tier, b.rank, b.lp) - rankScore(a.tier, a.rank, a.lp),
  name: (a, b) => a.game_name.localeCompare(b.game_name, undefined, { sensitivity: "base" }),
  recent: (a, b) => b.id - a.id,
};

function TableSkeleton() {
  return (
    <div className="flex flex-col gap-3 p-4" aria-hidden="true">
      {Array.from({ length: 4 }, (_, index) => (
        <div key={index} className="flex items-center gap-3">
          <Skeleton className="size-9 rounded-full" />
          <Skeleton className="h-4 flex-1" />
          <Skeleton className="h-8 w-32" />
        </div>
      ))}
    </div>
  );
}

export function PlayersPage() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search);
  const [sort, setSort] = useState<SortKey>("rank");
  const [adding, setAdding] = useState(false);
  const [toDelete, setToDelete] = useState<Player | null>(null);

  const players = useQuery({
    queryKey: queryKeys.playerList(),
    queryFn: () => unwrap(api.GET("/players/", { params: { query: { limit: 200 } } })),
  });

  const refresh = useMutation({
    mutationFn: (playerId: number) =>
      unwrap(api.POST("/players/{player_id}/refresh", { params: { path: { player_id: playerId } } })),
    onSuccess: (player) => {
      updateCachedPlayer(queryClient, player);
      toast.success(`${player.game_name} updated`);
    },
    onError: (error) => toast.error(error.message),
  });

  const remove = useMutation({
    mutationFn: (playerId: number) => unwrap(api.DELETE("/players/{player_id}", { params: { path: { player_id: playerId } } })),
    onSuccess: async () => {
      setToDelete(null);
      toast.success("Player deleted");
      await queryClient.invalidateQueries({ queryKey: queryKeys.players });
    },
    onError: (error) => toast.error(error.message),
  });

  const visible = useMemo(() => {
    const query = deferredSearch.trim().toLowerCase();
    const items = (players.data?.items ?? []).filter(
      (player) =>
        !query ||
        `${player.game_name}#${player.tag_line} ${player.nickname ?? ""} ${player.region}`.toLowerCase().includes(query),
    );
    return [...items].sort(SORTERS[sort]);
  }, [players.data, deferredSearch, sort]);

  const refreshingId = refresh.isPending ? refresh.variables : null;
  const total = players.data?.total ?? 0;

  return (
    <>
      <PageHeader
        title="Players"
        description={players.data ? `${total} tracked account${total === 1 ? "" : "s"}` : "Accounts you follow"}
        actions={
          <Button onClick={() => setAdding(true)}>
            <Plus className="size-4" aria-hidden="true" />
            Add player
          </Button>
        }
      />

      <Card>
        <div className="flex flex-col gap-3 border-b border-border/60 p-4 sm:flex-row sm:items-center">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted" aria-hidden="true" />
            <Input
              type="search"
              aria-label="Search players"
              placeholder="Search by Riot ID, nickname or region"
              className="pl-9"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
          <Select
            aria-label="Sort players"
            className="sm:w-44"
            value={sort}
            onChange={(event) => setSort(event.target.value as SortKey)}
          >
            <option value="rank">Highest rank</option>
            <option value="name">Name</option>
            <option value="recent">Recently added</option>
          </Select>
        </div>

        {players.isPending ? (
          <TableSkeleton />
        ) : players.isError ? (
          <ErrorState error={players.error} onRetry={() => void players.refetch()} />
        ) : players.data.items.length === 0 ? (
          <EmptyState
            icon={<Users className="size-10" />}
            title="No players yet"
            description="Add a Riot account to start analysing its ranked games."
            action={
              <Button size="sm" onClick={() => setAdding(true)}>
                Add your first player
              </Button>
            }
          />
        ) : visible.length === 0 ? (
          <EmptyState icon={<Search className="size-9" />} title="No results" description={`Nothing matches “${search}”.`} />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/60 text-left text-[11px] tracking-wider text-muted uppercase">
                  <th scope="col" className="px-4 py-3 font-semibold">
                    Player
                  </th>
                  <th scope="col" className="hidden px-4 py-3 font-semibold md:table-cell">
                    Role
                  </th>
                  <th scope="col" className="px-4 py-3 font-semibold">
                    Rank
                  </th>
                  <th scope="col" className="hidden px-4 py-3 font-semibold sm:table-cell">
                    Win rate
                  </th>
                  <th scope="col" className="px-4 py-3">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {visible.map((player) => (
                  <tr key={player.id} className="border-b border-border/40 transition last:border-0 hover:bg-surface-2/50">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <ProfileIcon iconId={player.profile_icon_id} name={player.game_name} size={36} />
                        <div className="min-w-0">
                          <Link
                            to={`/players/${player.id}`}
                            className="block max-w-56 truncate font-semibold text-fg hover:text-primary-light"
                          >
                            {player.game_name}
                            <span className="font-normal text-muted">#{player.tag_line}</span>
                          </Link>
                          <p className="truncate text-xs text-muted">
                            {regionLabel(player.region)}
                            {player.nickname ? ` · ${player.nickname}` : ""}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="hidden px-4 py-3 md:table-cell">
                      <RoleIcon role={player.role} size={22} />
                    </td>
                    <td className="px-4 py-3">
                      <RankBadge tier={player.tier} division={player.rank} lp={player.lp} size={34} />
                    </td>
                    <td className="hidden px-4 py-3 sm:table-cell">
                      <WinRate wins={player.wins ?? 0} losses={player.losses ?? 0} />
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex justify-end gap-1">
                        <Tooltip content="Update rank and icon from Riot">
                          <Button
                            variant="ghost"
                            size="icon"
                            aria-label={`Update ${player.game_name}`}
                            loading={refreshingId === player.id}
                            onClick={() => refresh.mutate(player.id)}
                          >
                            {refreshingId !== player.id && <RefreshCw className="size-4" aria-hidden="true" />}
                          </Button>
                        </Tooltip>
                        <Tooltip content="Delete player">
                          <Button
                            variant="ghost"
                            size="icon"
                            aria-label={`Delete ${player.game_name}`}
                            onClick={() => setToDelete(player)}
                          >
                            <Trash className="size-4" aria-hidden="true" />
                          </Button>
                        </Tooltip>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <AddPlayerDialog open={adding} onOpenChange={setAdding} />
      <ConfirmDialog
        open={toDelete !== null}
        onOpenChange={(open) => {
          if (!open) setToDelete(null);
        }}
        title={`Delete ${toDelete?.game_name ?? "player"}?`}
        description="Its snapshots are deleted too. Stored matches are kept for other players."
        loading={remove.isPending}
        onConfirm={() => {
          if (toDelete) remove.mutate(toDelete.id);
        }}
      />
    </>
  );
}
