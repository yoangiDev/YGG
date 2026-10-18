/**
 * TanStack Query keys in one place. They are hierarchical: invalidating
 * ["players", 7] also refreshes that player's summary, matches and
 * snapshots.
 */
export const queryKeys = {
  me: ["auth", "me"] as const,
  ddragon: ["ddragon"] as const,

  players: ["players"] as const,
  playerList: () => ["players", "list"] as const,
  player: (playerId: number) => ["players", playerId] as const,
  playerSummary: (playerId: number) => ["players", playerId, "summary"] as const,
  playerMatches: (playerId: number) => ["players", playerId, "matches"] as const,
  playerChampions: (playerId: number) => ["players", playerId, "champions"] as const,
  playerElo: (playerId: number) => ["players", playerId, "elo"] as const,
  playerSeasonChampions: (playerId: number) => ["players", playerId, "champions", "season"] as const,
  snapshots: (playerId: number) => ["players", playerId, "snapshots"] as const,

  snapshot: (snapshotId: number) => ["snapshots", snapshotId] as const,
  dashboards: (snapshotId: number) => ["snapshots", snapshotId, "dashboard"] as const,
  dashboard: (snapshotId: number, compare: string | null = null) =>
    ["snapshots", snapshotId, "dashboard", compare] as const,
  snapshotMatches: (snapshotId: number) => ["snapshots", snapshotId, "matches"] as const,
  premium: (snapshotId: number) => ["snapshots", snapshotId, "premium"] as const,
  premiumCoverage: ["snapshots", "premium", "coverage"] as const,
  matchWpa: (snapshotId: number, matchId: string) => ["snapshots", snapshotId, "matches", matchId, "wpa"] as const,

  matchDetails: (matchId: string) => ["matches", matchId, "details"] as const,
  matchLobbyRank: (matchId: string) => ["matches", matchId, "lobby-rank"] as const,

  cutoffs: (region: string) => ["cutoffs", region] as const,

  gameAnalyses: ["games", "analyses"] as const,

  admin: {
    all: ["admin"] as const,
    stats: ["admin", "stats"] as const,
    users: (offset: number) => ["admin", "users", offset] as const,
    players: (offset: number) => ["admin", "players", offset] as const,
  },
};
