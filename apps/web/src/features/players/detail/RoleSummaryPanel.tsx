import { useQuery } from "@tanstack/react-query";

import { RoleIcon } from "@/components/player/PlayerBits";
import { Card, CardHeader, Skeleton } from "@/components/ui/Card";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { api, unwrap } from "@/lib/api/client";
import { cn } from "@/lib/cn";
import { formatNumber, formatPercent, formatSigned } from "@/lib/format";
import { queryKeys } from "@/lib/queryKeys";
import { roleLabel } from "@/lib/roles";
import { kdaTone, toneText, winRateTone } from "@/lib/stats";

export function RoleSummaryPanel({ playerId }: { playerId: number }) {
  const summary = useQuery({
    queryKey: queryKeys.playerSummary(playerId),
    queryFn: () => unwrap(api.GET("/players/{player_id}/summary", { params: { path: { player_id: playerId } } })),
  });

  return (
    <Card>
      <CardHeader title="By role" description="All stored games." />
      {summary.isPending ? (
        <Skeleton className="m-5 h-24" />
      ) : summary.isError ? (
        <ErrorState error={summary.error} onRetry={() => void summary.refetch()} />
      ) : summary.data.length === 0 ? (
        <EmptyState title="No games yet" />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left">
                <th scope="col" className="microtext px-5 py-2.5 text-subtle">
                  Role
                </th>
                <th scope="col" className="microtext px-2 py-2.5 text-right text-subtle">
                  WR
                </th>
                <th scope="col" className="microtext px-2 py-2.5 text-right text-subtle">
                  KDA
                </th>
                <th scope="col" className="microtext px-5 py-2.5 text-right text-subtle">
                  GD@14
                </th>
              </tr>
            </thead>
            <tbody>
              {summary.data.map((row) => (
                <tr key={row.role} className="border-b border-line last:border-b-0">
                  <th scope="row" className="px-5 py-3 text-left font-normal">
                    <span className="flex items-center gap-2.5">
                      <RoleIcon role={row.role} size={18} />
                      <span className="font-bold text-text">{roleLabel(row.role)}</span>
                      <span className="text-xs text-subtle tabular-nums">{row.games}</span>
                    </span>
                  </th>
                  <td className={cn("px-2 py-3 text-right font-bold tabular-nums", toneText[winRateTone(row.win_rate)])}>
                    {formatPercent(row.win_rate, 0)}
                  </td>
                  <td className={cn("px-2 py-3 text-right font-bold tabular-nums", toneText[kdaTone(row.kda)])}>
                    {formatNumber(row.kda, 2)}
                  </td>
                  <td
                    className={cn(
                      "px-5 py-3 text-right font-bold tabular-nums",
                      row.gold_diff_14 === null ? "text-subtle" : row.gold_diff_14 >= 0 ? "text-stat-green" : "text-stat-red",
                    )}
                  >
                    {row.gold_diff_14 === null ? "—" : formatSigned(row.gold_diff_14)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
