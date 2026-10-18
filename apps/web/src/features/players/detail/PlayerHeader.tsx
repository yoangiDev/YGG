import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, Trash } from "lucide-react";

import { ProfileIcon, RankBadge, RoleIcon, WinRate } from "@/components/player/PlayerBits";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { PageTitle } from "@/components/ui/PageTitle";
import { Select } from "@/components/ui/Field";
import { useToast } from "@/components/ui/Toast";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { queryKeys } from "@/lib/queryKeys";
import { normalizeTier } from "@/lib/rank";
import { PLAYABLE_ROLES, regionLabel, roleLabel, toRegion, type Role } from "@/lib/roles";

import { playerUpdate, updateCachedPlayer } from "../cache";
import { EloSection } from "./EloPanel";

type Player = Schemas["PlayerResponse"];
export function PlayerHeader({
  player,
  refreshing,
  onRefresh,
  onDelete,
}: {
  player: Player;
  refreshing: boolean;
  onRefresh: () => void;
  onDelete: () => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const tier = normalizeTier(player.tier);
  const region = toRegion(player.region);

  // The Master and Grandmaster progress bar needs the region's LP cutoffs.
  const cutoffs = useQuery({
    queryKey: queryKeys.cutoffs(region ?? ""),
    queryFn: () => unwrap(api.GET("/league/cutoffs", { params: { query: { region: region ?? "EUW" } } })),
    enabled: region !== null && (tier === "MASTER" || tier === "GRANDMASTER"),
    staleTime: 10 * 60_000,
  });

  const updateRole = useMutation({
    mutationFn: (role: Role) =>
      unwrap(
        api.PUT("/players/{player_id}", {
          params: { path: { player_id: player.id } },
          body: playerUpdate(player, { role }),
        }),
      ),
    onSuccess: (updated) => {
      updateCachedPlayer(queryClient, updated);
      toast.success(`Main role set to ${roleLabel(updated.role)}`);
    },
    onError: (error) => toast.error(error.message),
  });

  return (
    <Card featured className="relative animate-rise overflow-hidden p-4 sm:p-5">
      <div className="relative flex flex-wrap items-center gap-x-6 gap-y-3">
        <ProfileIcon iconId={player.profile_icon_id} name={player.game_name} size={64} className="border border-acid/30" />

        <div className="min-w-0">
          <PageTitle>{`${player.game_name}#${player.tag_line}`}</PageTitle>
          <h1 className="headline truncate pb-0.5 text-xl text-text">
            {player.game_name}
            <span className="text-acid">#{player.tag_line}</span>
          </h1>
          <p className="text-xs text-muted">
            {regionLabel(player.region)}
            {player.nickname && <span> · {player.nickname}</span>}
          </p>
        </div>

        <div className="ml-auto flex flex-wrap items-center gap-x-8 gap-y-3">
          <RankBadge
            tier={player.tier}
            division={player.rank}
            lp={player.lp}
            size={44}
            showProgress
            cutoffs={
              cutoffs.data
                ? { grandmaster: cutoffs.data.grandmaster_cutoff_lp, challenger: cutoffs.data.challenger_cutoff_lp }
                : undefined
            }
          />
          <WinRate wins={player.wins ?? 0} losses={player.losses ?? 0} />
          <label className="flex items-center gap-2">
            <RoleIcon role={player.role} size={20} />
            <span className="sr-only">Main role</span>
            <Select
              className="h-9 w-32 text-xs font-bold"
              value={player.role}
              disabled={updateRole.isPending}
              onChange={(event) => updateRole.mutate(event.target.value as Role)}
            >
              {[...PLAYABLE_ROLES, "ALL" as const].map((role) => (
                <option key={role} value={role}>
                  {roleLabel(role)}
                </option>
              ))}
            </Select>
          </label>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" loading={refreshing} onClick={onRefresh}>
              {!refreshing && <RefreshCw className="size-3.5" aria-hidden="true" />}
              Update rank
            </Button>
            <Button variant="danger" size="sm" onClick={onDelete}>
              <Trash className="size-3.5" aria-hidden="true" />
              Unlink
            </Button>
          </div>
        </div>
      </div>

      <EloSection player={player} />
    </Card>
  );
}
