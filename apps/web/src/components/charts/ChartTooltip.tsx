import type { ReactNode } from "react";

export function ChartTooltipBox({ title, children }: { title: ReactNode; children: ReactNode }) {
  return (
    <div className="min-w-44 rounded-lg border border-border bg-surface-2/95 px-3 py-2 text-xs text-fg shadow-xl backdrop-blur">
      <p className="mb-1.5 font-semibold text-primary-light">{title}</p>
      <div className="flex flex-col gap-1">{children}</div>
    </div>
  );
}

export function Swatch({ color, dashed = false }: { color: string; dashed?: boolean }) {
  return (
    <span
      aria-hidden="true"
      className="inline-block h-0 w-4 shrink-0 border-t-2"
      style={{ borderColor: color, borderTopStyle: dashed ? "dashed" : "solid" }}
    />
  );
}
