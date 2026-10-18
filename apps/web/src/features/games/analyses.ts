import { useQuery } from "@tanstack/react-query";

import type { PremiumData } from "@/features/snapshots/PremiumResult";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { queryKeys } from "@/lib/queryKeys";

export type Match = Schemas["MatchResponse"];
export type Analysis = Schemas["GameAnalysisResponse"];
export type Quota = Schemas["Quota"];

const patchOf = (version: string) => version.split(".").slice(0, 2).join(".");

/** The matches that can be analysed: those of the current patch (that of the most recent in the list, which goes from newest
 * to oldest), which is the only thing Riot lets you download. */
export function eligible(matches: Match[]): Match[] {
  const patch = matches[0]?.game_version ? patchOf(matches[0].game_version) : null;
  return patch ? matches.filter((match) => patchOf(match.game_version) === patch) : [];
}

/** Your match analyses and the quota. While any is being analysed (30-60 s), it is checked again every few seconds. */
export function useGameAnalyses() {
  return useQuery({
    queryKey: queryKeys.gameAnalyses,
    queryFn: () => unwrap(api.GET("/games/analyses")),
    refetchInterval: (query) => (query.state.data?.items.some((a) => a.status === "processing") ? 5000 : false),
  });
}

/** The 1-to-100 grade of a finished analysis. */
export const scoreOf = (analysis: Analysis | undefined): number | undefined =>
  (analysis?.result as PremiumData | null | undefined)?.games[0]?.rating?.score;

/** "5h 12m" until `iso`. */
export function untilLabel(iso: string): string {
  const minutes = Math.max(1, Math.round((new Date(iso).getTime() - Date.now()) / 60_000));
  return minutes >= 60 ? `${Math.floor(minutes / 60)}h ${minutes % 60}m` : `${minutes}m`;
}

/** Whether the analyses allowed in the last 24 hours have been used up. */
export const spent = (quota: Quota | undefined): boolean =>
  quota?.limit !== null && quota?.limit !== undefined && quota.used >= quota.limit;
