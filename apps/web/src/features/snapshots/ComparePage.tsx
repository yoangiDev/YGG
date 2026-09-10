import { ArrowLeft, Minus, TrendingDown, TrendingUp } from "lucide-react";
import { useMemo } from "react";
import { Link, useParams, useSearchParams } from "react-router";

import { PageHeader } from "@/components/ui/PageHeader";
import { NotFound } from "@/app/RouteError";
import { PerformanceRadar } from "@/components/charts/PerformanceRadar";
import { Card, CardHeader, Skeleton } from "@/components/ui/Card";
import { Select } from "@/components/ui/Field";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { cn } from "@/lib/cn";
import { formatDate, formatMetric, formatSigned } from "@/lib/format";
import { palette } from "@/lib/palette";
import { parseId } from "@/lib/params";
import { isNegativeMetric, statTone, toneText } from "@/lib/stats";

import { useDashboard, useSnapshotList, type Dashboard } from "./queries";

export function ComparePage() {
  const playerId = parseId(useParams().playerId);
  if (playerId === null) return <NotFound />;
  return <CompareView playerId={playerId} />;
}

function rangeLabel(from: string, to: string): string {
  return `${formatDate(from)} – ${formatDate(to)}`;
}

function CompareView({ playerId }: { playerId: number }) {
  const [params, setParams] = useSearchParams();
  const a = parseId(params.get("a"));
  const b = parseId(params.get("b"));

  const snapshots = useSnapshotList(playerId);
  const left = useDashboard(a);
  const right = useDashboard(b);

  const select = (key: "a" | "b", value: string) =>
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        if (value) next.set(key, value);
        else next.delete(key);
        return next;
      },
      { replace: true },
    );

  const options = snapshots.data?.items ?? [];

  return (
    <>
      <PageHeader
        back={
          <Link to={`/players/${playerId}`} className="mb-2 inline-flex items-center gap-1 text-xs text-muted hover:text-fg">
            <ArrowLeft className="size-3.5" aria-hidden="true" />
            Back to player
          </Link>
        }
        title="Compare snapshots"
        description="See what changed between two periods of the same player."
      />

      <Card className="mb-6 grid gap-4 p-4 sm:grid-cols-2">
        {(["a", "b"] as const).map((key) => (
          <label key={key} className="flex flex-col gap-1.5">
            <span className="flex items-center gap-2 text-[11px] font-semibold tracking-[0.12em] text-muted uppercase">
              <span
                aria-hidden="true"
                className="inline-block size-2.5 rounded-full"
                style={{ background: key === "a" ? palette.primary : palette.gold }}
              />
              {key === "a" ? "Baseline" : "Compared with"}
            </span>
            <Select value={String((key === "a" ? a : b) ?? "")} onChange={(event) => select(key, event.target.value)}>
              <option value="">Choose a snapshot</option>
              {options.map((snapshot) => (
                <option key={snapshot.id} value={snapshot.id}>
                  {rangeLabel(snapshot.date_from, snapshot.date_to)} · {snapshot.match_count} games
                  {snapshot.description ? ` · ${snapshot.description}` : ""}
                </option>
              ))}
            </Select>
          </label>
        ))}
      </Card>

      {a === null || b === null ? (
        <Card>
          <EmptyState title="Pick two snapshots" description="Choose a baseline period and the one you want to compare it with." />
        </Card>
      ) : left.isPending || right.isPending ? (
        <div className="grid gap-6 lg:grid-cols-2" aria-busy="true">
          <Skeleton className="h-96 rounded-xl" />
          <Skeleton className="h-96 rounded-xl" />
        </div>
      ) : left.isError || right.isError ? (
        <Card>
          <ErrorState
            error={left.error ?? right.error}
            onRetry={() => {
              void left.refetch();
              void right.refetch();
            }}
          />
        </Card>
      ) : (
        <Comparison left={left.data} right={right.data} />
      )}
    </>
  );
}

function Comparison({ left, right }: { left: Dashboard; right: Dashboard }) {
  const leftLabel = rangeLabel(left.date_from, left.date_to);
  const rightLabel = rangeLabel(right.date_from, right.date_to);

  const rows = useMemo(() => {
    const byKey = new Map(right.role_averages.map((metric) => [metric.key, metric]));
    return left.role_averages.map((metric) => ({ before: metric, after: byKey.get(metric.key) }));
  }, [left, right]);

  return (
    <div className="grid gap-6 lg:grid-cols-5">
      <Card className="min-w-0 lg:col-span-2">
        <CardHeader title="Radar" description={`${left.games_played} vs ${right.games_played} games`} />
        <div className="p-4">
          <PerformanceRadar
            axes={left.radar_data.axes}
            series={[
              { id: "a", label: leftLabel, color: palette.primary, dataset: left.radar_data.player_dataset, fillOpacity: 0.15 },
              { id: "b", label: rightLabel, color: palette.gold, dataset: right.radar_data.player_dataset, fillOpacity: 0.1 },
            ]}
          />
        </div>
      </Card>

      <Card className="min-w-0 lg:col-span-3">
        <CardHeader
          title="Metrics"
          description={left.active_role !== right.active_role ? "The two snapshots are from different roles." : "Green means better."}
        />
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border/60 text-left text-[11px] tracking-wider text-muted uppercase">
                <th scope="col" className="px-5 py-2.5 font-semibold">
                  Metric
                </th>
                <th scope="col" className="px-3 py-2.5 text-right font-semibold">
                  Baseline
                </th>
                <th scope="col" className="px-3 py-2.5 text-right font-semibold">
                  Compared
                </th>
                <th scope="col" className="px-5 py-2.5 text-right font-semibold">
                  Change
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map(({ before, after }) => (
                <tr key={before.key} className="border-b border-border/40 last:border-0">
                  <th scope="row" className="px-5 py-2.5 text-left font-medium text-fg">
                    {before.label}
                  </th>
                  <td className={cn("px-3 py-2.5 text-right tabular-nums", toneText[statTone(before.key, before.status)])}>
                    {formatMetric(before.value, before.unit)}
                  </td>
                  <td
                    className={cn(
                      "px-3 py-2.5 text-right tabular-nums",
                      after ? toneText[statTone(after.key, after.status)] : "text-muted",
                    )}
                  >
                    {after ? formatMetric(after.value, after.unit) : "—"}
                  </td>
                  <td className="px-5 py-2.5 text-right">
                    {after ? <Delta metricKey={before.key} before={before.value} after={after.value} unit={before.unit} /> : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function Delta({ metricKey, before, after, unit }: { metricKey: string; before: number; after: number; unit: string }) {
  const delta = after - before;
  const digits = Math.abs(before) >= 100 ? 0 : 2;
  const neutral = Math.abs(delta) < 10 ** -digits / 2;
  const improved = isNegativeMetric(metricKey) ? delta < 0 : delta > 0;
  const Icon = neutral ? Minus : delta > 0 ? TrendingUp : TrendingDown;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 tabular-nums",
        neutral ? "text-muted" : improved ? "text-stat-green" : "text-stat-red",
      )}
    >
      <Icon className="size-3.5" aria-hidden="true" />
      {formatSigned(delta, digits)}
      {unit === "%" ? " pp" : ""}
      <span className="sr-only">{neutral ? "(no change)" : improved ? "(better)" : "(worse)"}</span>
    </span>
  );
}
