import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router";

import { RankEmblem } from "@/components/player/PlayerBits";
import { Card, Skeleton } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { ErrorState } from "@/components/ui/States";
import { api, unwrap } from "@/lib/api/client";
import { formatNumber } from "@/lib/format";
import { queryKeys } from "@/lib/queryKeys";
import { RANK_COLORS } from "@/lib/rank";
import { REGIONS, toRegion } from "@/lib/roles";

/** The Grandmaster and Challenger cutoffs of the server chosen in the bar's "Rank cutoffs" menu. They
 * update by themselves: the server refreshes them on expiry (4 h) and this screen requests them again every 10 minutes. */
export function CutoffsPage() {
  const region = toRegion(useSearchParams()[0].get("region")) ?? "EUW";
  const cutoffs = useQuery({
    queryKey: queryKeys.cutoffs(region),
    queryFn: () => unwrap(api.GET("/league/cutoffs", { params: { query: { region } } })),
    staleTime: 10 * 60_000,
    refetchInterval: 10 * 60_000,
  });

  const tiers = [
    { tier: "GRANDMASTER" as const, name: "Grandmaster", lp: cutoffs.data?.grandmaster_cutoff_lp },
    { tier: "CHALLENGER" as const, name: "Challenger", lp: cutoffs.data?.challenger_cutoff_lp },
  ];

  return (
    <>
      <PageHeader title="Rank cutoffs" accent={REGIONS.find((r) => r.value === region)?.label} />
      {cutoffs.isError ? (
        <Card>
          <ErrorState error={cutoffs.error} onRetry={() => void cutoffs.refetch()} />
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {tiers.map(({ tier, name, lp }) => (
            <Card key={tier} className="relative overflow-hidden p-6">
              <div aria-hidden="true" className="absolute inset-x-0 top-0 h-0.5" style={{ background: RANK_COLORS[tier] }} />
              <div className="flex items-center gap-5">
                <RankEmblem tier={tier} size={88} />
                <div>
                  <h2 className="microtext text-muted">{name}</h2>
                  {lp === undefined ? (
                    <Skeleton className="mt-2 h-9 w-32" />
                  ) : (
                    <p className="mt-1 text-2xl font-bold tabular-nums" style={{ color: RANK_COLORS[tier] }}>
                      {formatNumber(lp, 0)}
                      <span className="ml-1.5 text-base font-bold text-muted">LP</span>
                    </p>
                  )}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
