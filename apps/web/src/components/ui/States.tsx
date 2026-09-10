import { Inbox, RefreshCw, TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

import { Button } from "./Button";

export function EmptyState({
  title,
  description,
  action,
  icon,
  className,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  icon?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center gap-3 px-6 py-12 text-center", className)}>
      <span className="text-muted/70" aria-hidden="true">
        {icon ?? <Inbox className="size-9" />}
      </span>
      <p className="text-sm font-semibold text-fg">{title}</p>
      {description && <p className="max-w-sm text-sm text-muted">{description}</p>}
      {action}
    </div>
  );
}

export function ErrorState({
  error,
  onRetry,
  className,
}: {
  error: unknown;
  onRetry?: () => void;
  className?: string;
}) {
  const message = error instanceof Error ? error.message : "Something went wrong.";
  return (
    <div role="alert" className={cn("flex flex-col items-center gap-3 px-6 py-12 text-center", className)}>
      <TriangleAlert className="size-9 text-stat-red" aria-hidden="true" />
      <p className="text-sm font-semibold text-fg">Could not load this section</p>
      <p className="max-w-sm text-sm text-muted">{message}</p>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RefreshCw className="size-3.5" aria-hidden="true" />
          Retry
        </Button>
      )}
    </div>
  );
}
