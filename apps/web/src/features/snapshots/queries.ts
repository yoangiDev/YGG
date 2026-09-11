import { useQuery } from "@tanstack/react-query";

import { api, unwrap, type Schemas } from "@/lib/api/client";
import { queryKeys } from "@/lib/queryKeys";

export type Dashboard = Schemas["SnapshotDashboardResponse"];
export type Match = Schemas["MatchResponse"];

export interface CompareTarget {
  gameName: string;
  tagLine: string;
  region: string;
}

export function compareKey(target: CompareTarget | null): string | null {
  return target ? `${target.gameName}#${target.tagLine}@${target.region}` : null;
}

export function fetchDashboard(snapshotId: number, compare: CompareTarget | null = null): Promise<Dashboard> {
  return unwrap(
    api.GET("/snapshots/{snapshot_id}/dashboard", {
      params: {
        path: { snapshot_id: snapshotId },
        query: compare
          ? { compare_game_name: compare.gameName, compare_tag_line: compare.tagLine, compare_region: compare.region }
          : {},
      },
    }),
  );
}

export function useDashboard(snapshotId: number | null) {
  return useQuery({
    queryKey: queryKeys.dashboard(snapshotId ?? 0),
    queryFn: () => fetchDashboard(snapshotId ?? 0),
    enabled: snapshotId !== null,
    staleTime: 5 * 60_000,
  });
}

const MATCH_PAGE = 200;

/** Todas las partidas del snapshot. La API pagina (P9); aquí se piden páginas hasta completar el total. */
export function useSnapshotMatches(snapshotId: number) {
  return useQuery({
    queryKey: queryKeys.snapshotMatches(snapshotId),
    queryFn: async () => {
      const items: Match[] = [];
      for (let offset = 0; ; offset += MATCH_PAGE) {
        const page = await unwrap(
          api.GET("/matches/snapshot/{snapshot_id}", {
            params: { path: { snapshot_id: snapshotId }, query: { limit: MATCH_PAGE, offset } },
          }),
        );
        items.push(...page.items);
        if (page.items.length === 0 || items.length >= page.total) return items;
      }
    },
    staleTime: 5 * 60_000,
  });
}

export function useSnapshotList(playerId: number) {
  return useQuery({
    queryKey: queryKeys.snapshots(playerId),
    queryFn: () =>
      unwrap(api.GET("/snapshots/player/{player_id}", { params: { path: { player_id: playerId }, query: { limit: 100 } } })),
  });
}
