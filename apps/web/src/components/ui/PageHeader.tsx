import type { ReactNode } from "react";

/**
 * Cabecera de página: rótulo en verde, titular pesado y acciones.
 * `accent` es la segunda parte del titular, que va en verde (DESIGN.md §3.4).
 */
export function PageHeader({
  title,
  accent,
  eyebrow,
  description,
  actions,
  back,
}: {
  title: ReactNode;
  accent?: ReactNode;
  eyebrow?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  back?: ReactNode;
}) {
  return (
    <div className="mb-8 flex animate-rise flex-col gap-5 sm:mb-10 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        {back}
        {eyebrow && <p className="eyebrow mb-4">{eyebrow}</p>}
        <h1 className="headline truncate pb-1 text-[36px] text-text sm:text-[46px]">
          {title}
          {accent && <span className="text-acid"> {accent}</span>}
        </h1>
        {description && <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2.5">{actions}</div>}
    </div>
  );
}
