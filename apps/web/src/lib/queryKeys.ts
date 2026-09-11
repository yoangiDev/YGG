/**
 * Claves de TanStack Query en un solo sitio. Son jerárquicas: invalidar
 * ["players", 7] refresca también el resumen, las partidas y los snapshots de
 * ese jugador.
 */
export const queryKeys = {
  me: ["auth", "me"] as const,
  ddragon: ["ddragon"] as const,

  players: ["players"] as const,
  playerList: () => ["players", "list"] as const,
  player: (playerId: number) => ["players", playerId] as const,
  playerSummary: (playerId: number) => ["players", playerId, "summary"] as const,
  playerMatches: (playerId: number) => ["players", playerId, "matches"] as const,
  mostPlayed: (playerId: number) => ["players", playerId, "most-played"] as const,
  snapshots: (playerId: number) => ["players", playerId, "snapshots"] as const,

  snapshot: (snapshotId: number) => ["snapshots", snapshotId] as const,
  dashboards: (snapshotId: number) => ["snapshots", snapshotId, "dashboard"] as const,
  dashboard: (snapshotId: number, compare: string | null = null) =>
    ["snapshots", snapshotId, "dashboard", compare] as const,
  snapshotMatches: (snapshotId: number) => ["snapshots", snapshotId, "matches"] as const,

  cutoffs: (region: string) => ["cutoffs", region] as const,

  admin: {
    all: ["admin"] as const,
    stats: ["admin", "stats"] as const,
    users: (offset: number) => ["admin", "users", offset] as const,
    players: (offset: number) => ["admin", "players", offset] as const,
  },
};
