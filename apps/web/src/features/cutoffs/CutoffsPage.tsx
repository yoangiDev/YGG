import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { useSearchParams } from "react-router";

import { PageHeader } from "@/app/AppLayout";
import { RankEmblem } from "@/components/player/PlayerBits";
import { Button } from "@/components/ui/Button";
import { Card, Skeleton } from "@/components/ui/Card";
import { Select } from "@/components/ui/Field";
import { ErrorState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { api, unwrap } from "@/lib/api/client";
import { formatDateTime, formatNumber, timeAgo } from "@/lib/format";
import { queryKeys } from "@/lib/queryKeys";
import { RANK_COLORS } from "@/lib/rank";
import { REGIONS } from "@/lib/roles";

export function CutoffsPage() {
  const [params, setParams] = useSearchParams();
  const region = (params.get("region") ?? "EUW").toUpperCase();
  const queryClient = useQueryClient();
  const toast = useToast();

  const cutoffs = useQuery({
    queryKey: queryKeys.cutoffs(region),
    queryFn: () => unwrap(api.GET("/league/cutoffs", { params: { query: { region } } })),
    staleTime: 10 * 60_000,
  });

  const refresh = useMutation({
    mutationFn: () => unwrap(api.GET("/league/cutoffs", { params: { query: { region, refresh: true } } })),
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.cutoffs(region), data);
      toast.success(`${region} cutoffs updated`);
    },
    onError: (error) => toast.error(error.message),
  });

  const tiers = [
    { tier: "GRANDMASTER" as const, name: "Grandmaster", lp: cutoffs.data?.grandmaster_cutoff_lp },
    { tier: "CHALLENGER" as const, name: "Challenger", lp: cutoffs.data?.challenger_cutoff_lp },
  ];

  return (
    <>
      <PageHeader
        title="Rank cutoffs"
        description="Minimum LP needed to hold Grandmaster and Challenger in each region."
        actions={
          <>
            <label className="sr-only" htmlFor="region">
              Region
            </label>
            <Select
              id="region"
              className="w-56"
              value={region}
              onChange={(event) => {
                setParams({ region: event.target.value }, { replace: true });
              }}
            >
              {REGIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.value} · {option.label}
                </option>
              ))}
            </Select>
            <Button variant="outline" loading={refresh.isPending} onClick={() => refresh.mutate()}>
              {!refresh.isPending && <RefreshCw className="size-4" aria-hidden="true" />}
              Refresh
            </Button>
          </>
        }
      />

      {cutoffs.isError ? (
        <Card>
          <ErrorState error={cutoffs.error} onRetry={() => void cutoffs.refetch()} />
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {tiers.map(({ tier, name, lp }) => (
            <Card key={tier} className="relative overflow-hidden p-6">
              <div
                aria-hidden="true"
                className="absolute inset-x-0 top-0 h-0.5"
                style={{ background: RANK_COLORS[tier] }}
              />
              <div className="flex items-center gap-5">
                <RankEmblem tier={tier} size={88} />
                <div>
                  <h2 className="text-xs font-semibold tracking-[0.14em] text-muted uppercase">{name}</h2>
                  {lp === undefined ? (
                    <Skeleton className="mt-2 h-9 w-32" />
                  ) : (
                    <p className="mt-1 text-4xl font-bold tabular-nums" style={{ color: RANK_COLORS[tier] }}>
                      {formatNumber(lp, 0)}
                      <span className="ml-1.5 text-base font-semibold text-muted">LP</span>
                    </p>
                  )}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {cutoffs.data && (
        <p className="mt-4 text-xs text-muted">
          Platform {cutoffs.data.platform.toUpperCase()} · updated{" "}
          <time dateTime={cutoffs.data.fetched_at} title={formatDateTime(cutoffs.data.fetched_at)}>
            {timeAgo(cutoffs.data.fetched_at)}
          </time>{" "}
          · refreshed automatically every 4 hours
        </p>
      )}
    </>
  );
}
