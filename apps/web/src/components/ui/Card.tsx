import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/cn";

export function Card({ className, ...props }: HTMLAttributes<HTMLElement>) {
  return <section className={cn("rounded-xl border border-border bg-surface/95", className)} {...props} />;
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
    <header className={cn("flex items-start justify-between gap-4 border-b border-border/60 px-5 py-4", className)}>
      <div className="min-w-0">
        <h2 className="text-sm font-bold tracking-[0.14em] text-primary-light uppercase">{title}</h2>
        {description && <p className="mt-1 text-xs text-muted">{description}</p>}
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
        "animate-shimmer rounded-md bg-[linear-gradient(90deg,var(--color-surface-2)_25%,hsl(252_25%_18%)_50%,var(--color-surface-2)_75%)] bg-[length:200%_100%]",
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
  /** Color sólido de la barra (por ejemplo, el del rango). Sustituye al degradado. */
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
      className={cn("h-1.5 overflow-hidden rounded-full bg-white/10", className)}
    >
      <div
        className={cn("h-full rounded-full bg-gradient-to-r from-primary to-primary-light transition-[width]", barClassName)}
        style={color ? { width: `${clamped}%`, background: color } : { width: `${clamped}%` }}
      />
    </div>
  );
}
