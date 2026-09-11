import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, Trash } from "lucide-react";

import { ProfileIcon, RankBadge, RoleIcon, WinRate } from "@/components/player/PlayerBits";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Select } from "@/components/ui/Field";
import { useToast } from "@/components/ui/Toast";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { queryKeys } from "@/lib/queryKeys";
import { normalizeTier } from "@/lib/rank";
import { PLAYABLE_ROLES, regionLabel, roleLabel, type Role } from "@/lib/roles";

import { playerUpdate, updateCachedPlayer } from "../cache";

type Player = Schemas["PlayerResponse"];

export function PlayerHeader({
  player,
  refreshing,
  onRefresh,
  onAnalyse,
  onDelete,
}: {
  player: Player;
  refreshing: boolean;
  onRefresh: () => void;
  onAnalyse: () => void;
  onDelete: () => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const tier = normalizeTier(player.tier);
  const region = player.region.toUpperCase();

  // Para la barra de progreso de Master y Grandmaster hacen falta los cortes de LP de la región.
  const cutoffs = useQuery({
    queryKey: queryKeys.cutoffs(region),
    queryFn: () => unwrap(api.GET("/league/cutoffs", { params: { query: { region } } })),
    enabled: tier === "MASTER" || tier === "GRANDMASTER",
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
    <Card featured className="relative animate-rise overflow-hidden p-6 sm:p-8">
      <div
        aria-hidden="true"
        className="tech-grid pointer-events-none absolute inset-0 opacity-50 [mask-image:linear-gradient(to_right,transparent_10%,black_60%,transparent_98%)]"
      />
      <div className="relative flex flex-col gap-7 lg:flex-row lg:items-center">
        <ProfileIcon
          iconId={player.profile_icon_id}
          name={player.game_name}
          size={96}
          className="border border-acid/30 shadow-[0_0_0_6px_rgba(200,245,63,0.06)]"
        />

        <div className="min-w-0 flex-1">
          <p className="eyebrow">
            {regionLabel(player.region)}
            <span className="diamond" aria-hidden="true" />
            Ranked solo
          </p>
          <h1 className="headline mt-3 truncate pb-1 text-[38px] text-text sm:text-[54px]">
            {player.game_name}
            <span className="text-acid">#{player.tag_line}</span>
          </h1>
          {player.nickname && <p className="mt-1 text-sm text-muted">{player.nickname}</p>}

          <div className="mt-6 flex flex-wrap items-center gap-x-10 gap-y-5">
            <RankBadge
              tier={player.tier}
              division={player.rank}
              lp={player.lp}
              size={56}
              showProgress
              cutoffs={
                cutoffs.data
                  ? { grandmaster: cutoffs.data.grandmaster_cutoff_lp, challenger: cutoffs.data.challenger_cutoff_lp }
                  : undefined
              }
            />
            <WinRate wins={player.wins ?? 0} losses={player.losses ?? 0} />
            <label className="flex items-center gap-3">
              <RoleIcon role={player.role} size={20} />
              <span className="sr-only">Main role</span>
              <Select
                className="h-9 w-36 text-xs font-bold"
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
          </div>
        </div>

        <div className="flex flex-wrap gap-2.5 lg:w-56 lg:flex-col lg:items-stretch">
          <Button size="lg" arrow onClick={onAnalyse}>
            New analysis
          </Button>
          <Button variant="outline" loading={refreshing} onClick={onRefresh}>
            {!refreshing && <RefreshCw className="size-3.5" aria-hidden="true" />}
            Update rank
          </Button>
          <Button variant="danger" onClick={onDelete}>
            <Trash className="size-3.5" aria-hidden="true" />
            Delete
          </Button>
        </div>
      </div>
    </Card>
  );
}
