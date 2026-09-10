import type { Schemas } from "@/lib/api/client";
import { formatNumber, formatPercent } from "@/lib/format";
import { palette } from "@/lib/palette";

/** Fases de ygg_core.metrics.aggregates: minuto 8 y minuto 14. */
export function DeathsByPhase({ phases, games }: { phases: Schemas["DeathsByPhase"]; games: number }) {
  const rows = [
    { label: "Early", detail: "0–8 min", value: phases.early_deaths, color: palette.gold },
    { label: "Laning", detail: "8–14 min", value: phases.mid_deaths, color: palette.red },
    { label: "Late", detail: "14+ min", value: phases.late_deaths, color: palette.primary },
  ];
  const total = rows.reduce((sum, row) => sum + row.value, 0);

  return (
    <div>
      <div className="mb-2 flex items-baseline justify-between">
        <h3 className="text-xs font-semibold tracking-[0.12em] text-muted uppercase">Deaths by phase</h3>
        <span className="text-xs text-muted">{games} games</span>
      </div>
      <div className="flex h-2.5 overflow-hidden rounded-full bg-surface-2" aria-hidden="true">
        {total > 0 &&
          rows.map((row) => <div key={row.label} style={{ width: `${(row.value / total) * 100}%`, background: row.color }} />)}
      </div>
      <dl className="mt-3 grid grid-cols-3 gap-2">
        {rows.map((row) => (
          <div key={row.label} className="rounded-lg bg-surface-2/60 px-3 py-2">
            <dt className="flex items-center gap-1.5 text-[11px] text-muted">
              <span className="inline-block size-2 rounded-full" style={{ background: row.color }} aria-hidden="true" />
              {row.label}
            </dt>
            <dd className="mt-0.5 text-lg font-bold text-fg tabular-nums">
              {formatNumber(row.value, 1)}
              <span className="ml-1 text-xs font-normal text-muted">
                {total > 0 ? formatPercent((row.value / total) * 100, 0) : "—"}
              </span>
            </dd>
            <dd className="text-[10px] text-muted">{row.detail}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
