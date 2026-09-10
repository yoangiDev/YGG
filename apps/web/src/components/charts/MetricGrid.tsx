import type { Schemas } from "@/lib/api/client";
import { cn } from "@/lib/cn";
import { formatMetric } from "@/lib/format";
import { isNegativeMetric, statTone, statusLabel, toneBorder, toneText } from "@/lib/stats";

type Metric = Schemas["RoleAverageMetric"];

export function MetricCard({ metric }: { metric: Metric }) {
  const tone = statTone(metric.key, metric.status);
  const comparator = isNegativeMetric(metric.key) ? "≤" : "≥";
  return (
    <div className={cn("h-full rounded-xl border bg-surface/95 p-4", toneBorder[tone])}>
      <p className="truncate text-[11px] font-semibold tracking-[0.08em] text-muted uppercase" title={metric.label}>
        {metric.label}
      </p>
      <p className={cn("mt-1.5 text-2xl font-bold tabular-nums", toneText[tone])}>{formatMetric(metric.value, metric.unit)}</p>
      <p className="mt-1 text-xs text-muted">
        <span className={cn("font-semibold", toneText[tone])}>{statusLabel(metric.status)}</span>
        <span aria-hidden="true"> · </span>
        <span>
          target {comparator} {formatMetric(metric.threshold, metric.unit)}
        </span>
      </p>
    </div>
  );
}

/** Medias del rol activo con el color semántico que decide el backend (excellent/good/normal/bad). */
export function MetricGrid({ metrics }: { metrics: Metric[] }) {
  return (
    <ul aria-label="Role metrics" className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
      {metrics.map((metric) => (
        <li key={metric.key}>
          <MetricCard metric={metric} />
        </li>
      ))}
    </ul>
  );
}
