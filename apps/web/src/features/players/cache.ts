import type { QueryClient } from "@tanstack/react-query";

import type { Schemas } from "@/lib/api/client";
import { queryKeys } from "@/lib/queryKeys";

type Player = Schemas["PlayerResponse"];

/** Sustituye un jugador en la lista y en su detalle sin volver a pedir nada. */
export function updateCachedPlayer(queryClient: QueryClient, player: Player): void {
  queryClient.setQueryData<Schemas["Page_PlayerResponse_"]>(
    queryKeys.playerList(),
    (page) => page && { ...page, items: page.items.map((item) => (item.id === player.id ? player : item)) },
  );
  queryClient.setQueryData(queryKeys.player(player.id), player);
}

/** PUT /players/{id} exige el objeto completo: se parte del estado actual y se aplica el cambio. */
export function playerUpdate(player: Player, patch: Partial<Schemas["PlayerUpdate"]>): Schemas["PlayerUpdate"] {
  return {
    game_name: player.game_name,
    tag_line: player.tag_line,
    role: player.role,
    nickname: player.nickname ?? "",
    notes: player.notes ?? "",
    ...patch,
  };
}
