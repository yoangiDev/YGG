import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/cn";

/**
 * Tarjeta recta sobre el fondo oscuro. `featured` añade el borde con acento, el
 * degradado y la pestaña ácida (DESIGN.md §8.3): úsalo solo en lo destacado.
 */
export function Card({ className, featured = false, ...props }: HTMLAttributes<HTMLElement> & { featured?: boolean }) {
  return (
    <section
      className={cn(
        "border border-line bg-panel/85",
        featured && "card-featured acid-tab shadow-float",
        className,
      )}
      {...props}
    />
  );
}

export function CardHeader({
  title,
  description,
  action,
  className,
}: {
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <header className={cn("flex items-start justify-between gap-4 border-b border-line px-5 py-4", className)}>
      <div className="min-w-0">
        <h2 className="flex items-center gap-2.5 text-[12px] font-black tracking-[0.16em] text-text uppercase">
          <span className="diamond" aria-hidden="true" />
          {title}
        </h2>
        {description && <p className="mt-1.5 text-xs text-subtle">{description}</p>}
      </div>
      {action}
    </header>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={cn(
        "animate-shimmer bg-[linear-gradient(90deg,#15191b_25%,#1f2527_50%,#15191b_75%)] bg-[length:200%_100%]",
        className,
      )}
    />
  );
}

export function ProgressBar({
  value,
  label,
  className,
  barClassName,
  color,
}: {
  value: number;
  label: string;
  className?: string;
  barClassName?: string;
  /** Color sólido de la barra (por ejemplo, el del rango). Por defecto, el acento. */
  color?: string;
}) {
  const clamped = Math.min(100, Math.max(0, value));
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(clamped)}
      className={cn("h-1 overflow-hidden bg-white/10", className)}
    >
      <div
        className={cn("h-full bg-acid transition-[width] duration-500 ease-snap", barClassName)}
        style={color ? { width: `${clamped}%`, background: color } : { width: `${clamped}%` }}
      />
    </div>
  );
}
