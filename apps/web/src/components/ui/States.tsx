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
    <div className={cn("flex flex-col items-center gap-3 px-6 py-14 text-center", className)}>
      <span className="grid size-14 place-items-center border border-line text-subtle" aria-hidden="true">
        {icon ?? <Inbox className="size-6" />}
      </span>
      <p className="mt-2 text-[15px] font-extrabold tracking-[-0.01em] text-text">{title}</p>
      {description && <p className="max-w-sm text-sm leading-relaxed text-muted">{description}</p>}
      {action && <div className="mt-3">{action}</div>}
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
    <div role="alert" className={cn("flex flex-col items-center gap-3 px-6 py-14 text-center", className)}>
      <span className="grid size-14 place-items-center border border-danger/30 text-danger" aria-hidden="true">
        <TriangleAlert className="size-6" />
      </span>
      <p className="mt-2 text-[15px] font-extrabold tracking-[-0.01em] text-text">Could not load this section</p>
      <p className="max-w-sm text-sm leading-relaxed text-muted">{message}</p>
      {onRetry && (
        <Button variant="outline" size="sm" className="mt-3" onClick={onRetry}>
          <RefreshCw className="size-3.5" aria-hidden="true" />
          Retry
        </Button>
      )}
    </div>
  );
}
