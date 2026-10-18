import type { QueryClient } from "@tanstack/react-query";

import type { Schemas } from "@/lib/api/client";
import { queryKeys } from "@/lib/queryKeys";

type Player = Schemas["PlayerResponse"];

/** Replaces a player in the list and in its detail without requesting anything again. */
export function updateCachedPlayer(queryClient: QueryClient, player: Player): void {
  queryClient.setQueryData<Schemas["Page_PlayerResponse_"]>(
    queryKeys.playerList(),
    (page) => page && { ...page, items: page.items.map((item) => (item.id === player.id ? player : item)) },
  );
  queryClient.setQueryData(queryKeys.player(player.id), player);
}

/** PUT /players/{id} requires the complete object: start from the current state and apply the change. */
export function playerUpdate(player: Player, patch: Partial<Schemas["PlayerUpdate"]>): Schemas["PlayerUpdate"] {
  return {
    game_name: player.game_name,
    tag_line: player.tag_line,
    role: player.role,
    nickname: player.nickname ?? "",
    notes: player.notes ?? "",
    target_rank: player.target_rank,
    ...patch,
  };
}
