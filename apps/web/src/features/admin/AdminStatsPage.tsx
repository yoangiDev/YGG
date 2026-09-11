import { useQuery } from "@tanstack/react-query";
import { Database, Swords, UserCheck, Users } from "lucide-react";
import type { ComponentType, SVGProps } from "react";

import { Card, CardHeader, Skeleton } from "@/components/ui/Card";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { api, unwrap } from "@/lib/api/client";
import { formatNumber } from "@/lib/format";
import { palette } from "@/lib/palette";
import { queryKeys } from "@/lib/queryKeys";
import { normalizeTier, RANK_COLORS, tierOrder } from "@/lib/rank";

function StatCard({
  label,
  value,
  detail,
  icon: Icon,
}: {
  label: string;
  value: number;
  detail?: string;
  icon: ComponentType<SVGProps<SVGSVGElement>>;
}) {
  return (
    <Card className="flex items-start gap-4 p-5">
      <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-primary/12 text-primary-light">
        <Icon className="size-5" aria-hidden="true" />
      </span>
      <div>
        <p className="text-[11px] font-semibold tracking-[0.12em] text-muted uppercase">{label}</p>
        <p className="mt-1 text-2xl font-bold text-fg tabular-nums">{formatNumber(value, 0)}</p>
        {detail && <p className="text-xs text-muted">{detail}</p>}
      </div>
    </Card>
  );
}

function Bars({ rows }: { rows: { label: string; count: number; color: string }[] }) {
  const max = Math.max(1, ...rows.map((row) => row.count));
  if (rows.length === 0) return <EmptyState title="No data yet" />;
  return (
    <ul className="flex flex-col gap-2.5 p-5">
      {rows.map((row) => (
        <li key={row.label} className="grid grid-cols-[7rem_1fr_3rem] items-center gap-3 text-sm">
          <span className="truncate text-fg">{row.label}</span>
          <span className="h-2 overflow-hidden rounded-full bg-surface-2" aria-hidden="true">
            <span className="block h-full rounded-full" style={{ width: `${(row.count / max) * 100}%`, background: row.color }} />
          </span>
          <span className="text-right text-muted tabular-nums">{row.count}</span>
        </li>
      ))}
    </ul>
  );
}

export function AdminStatsPage() {
  const stats = useQuery({ queryKey: queryKeys.admin.stats, queryFn: () => unwrap(api.GET("/admin/stats/")) });

  if (stats.isPending) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4" aria-busy="true">
        {Array.from({ length: 4 }, (_, index) => (
          <Skeleton key={index} className="h-28 rounded-xl" />
        ))}
      </div>
    );
  }
  if (stats.isError) {
    return (
      <Card>
        <ErrorState error={stats.error} onRetry={() => void stats.refetch()} />
      </Card>
    );
  }

  const data = stats.data;
  const tiers = [...data.tier_distribution]
    .sort((a, b) => tierOrder(b.tier) - tierOrder(a.tier))
    .map((row) => {
      const tier = normalizeTier(row.tier);
      return { label: tier ? tier.charAt(0) + tier.slice(1).toLowerCase() : "Unranked", count: row.count, color: tier ? RANK_COLORS[tier] : palette.gray };
    });
  const regions = [...data.region_distribution]
    .sort((a, b) => b.count - a.count)
    .map((row) => ({ label: row.region.toUpperCase(), count: row.count, color: palette.primary }));

  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Users" value={data.total_users} detail={`${data.active_users} active · ${data.inactive_users} inactive`} icon={Users} />
        <StatCard label="Tracked players" value={data.total_players} icon={Swords} />
        <StatCard label="Snapshots" value={data.total_snapshots} icon={UserCheck} />
        <StatCard label="Stored matches" value={data.total_matches} icon={Database} />
      </div>
      <div className="grid gap-6 lg:grid-cols-3">
        <Card>
          <CardHeader title="Players by tier" />
          <Bars rows={tiers} />
        </Card>
        <Card>
          <CardHeader title="Players by region" />
          <Bars rows={regions} />
        </Card>
        <Card>
          <CardHeader title="Most active users" description="By tracked players." />
          {data.top_users.length === 0 ? (
            <EmptyState title="No users yet" />
          ) : (
            <ol className="flex flex-col gap-1 p-3">
              {data.top_users.map((user, index) => (
                <li key={user.username} className="flex items-center gap-3 rounded-lg px-2 py-1.5 text-sm">
                  <span className="w-5 text-right text-xs text-muted tabular-nums">{index + 1}</span>
                  <span className="min-w-0 flex-1 truncate text-fg">{user.username}</span>
                  <span className="text-xs text-muted tabular-nums">{user.player_count} players</span>
                </li>
              ))}
            </ol>
          )}
        </Card>
      </div>
    </div>
  );
}
