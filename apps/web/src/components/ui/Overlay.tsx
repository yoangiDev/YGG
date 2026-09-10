import * as DialogPrimitive from "@radix-ui/react-dialog";
import * as DropdownPrimitive from "@radix-ui/react-dropdown-menu";
import * as TabsPrimitive from "@radix-ui/react-tabs";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import { X } from "lucide-react";
import type { ComponentProps, ReactNode } from "react";

import { cn } from "@/lib/cn";

// ── Dialog ────────────────────────────────────────────────────────────────────

interface DialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children: ReactNode;
  className?: string;
}

export function Dialog({ open, onOpenChange, title, description, children, className }: DialogProps) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-black/60 backdrop-blur-[2px]" />
        <DialogPrimitive.Content
          className={cn(
            "fixed top-1/2 left-1/2 z-50 max-h-[90dvh] w-[min(92vw,30rem)] -translate-x-1/2 -translate-y-1/2 overflow-y-auto",
            "rounded-2xl border border-primary/25 bg-surface p-6 shadow-2xl focus:outline-none",
            className,
          )}
          {...(description ? {} : { "aria-describedby": undefined })}
        >
          <div className="mb-5 flex items-start justify-between gap-4">
            <div>
              <DialogPrimitive.Title className="text-base font-bold text-fg">{title}</DialogPrimitive.Title>
              {description && (
                <DialogPrimitive.Description className="mt-1 text-sm text-muted">{description}</DialogPrimitive.Description>
              )}
            </div>
            <DialogPrimitive.Close className="rounded-md p-1 text-muted hover:bg-surface-2 hover:text-fg" aria-label="Close">
              <X className="size-4" aria-hidden="true" />
            </DialogPrimitive.Close>
          </div>
          {children}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

// ── Tooltip ───────────────────────────────────────────────────────────────────

export const TooltipProvider = TooltipPrimitive.Provider;

export function Tooltip({ content, children }: { content: ReactNode; children: ReactNode }) {
  return (
    <TooltipPrimitive.Root delayDuration={150}>
      <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Content
          sideOffset={6}
          className="z-50 max-w-72 rounded-md border border-border bg-surface-2 px-2.5 py-1.5 text-xs text-fg shadow-lg"
        >
          {content}
          <TooltipPrimitive.Arrow className="fill-surface-2" />
        </TooltipPrimitive.Content>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  );
}

// ── Tabs ──────────────────────────────────────────────────────────────────────

export const Tabs = TabsPrimitive.Root;
export const TabsContent = TabsPrimitive.Content;

export function TabsList({ className, ...props }: ComponentProps<typeof TabsPrimitive.List>) {
  return (
    <TabsPrimitive.List
      className={cn("inline-flex gap-1 rounded-xl border border-primary/15 bg-[#0f0d18] p-1", className)}
      {...props}
    />
  );
}

export function TabsTrigger({ className, ...props }: ComponentProps<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      className={cn(
        "inline-flex cursor-pointer items-center gap-2 rounded-lg px-4 py-2 text-xs font-semibold tracking-wider text-muted uppercase transition",
        "hover:text-fg data-[state=active]:bg-gradient-to-r data-[state=active]:from-[#8b48d4] data-[state=active]:to-[#6b2fa0] data-[state=active]:text-white",
        className,
      )}
      {...props}
    />
  );
}

// ── Dropdown ──────────────────────────────────────────────────────────────────

export const DropdownMenu = DropdownPrimitive.Root;
export const DropdownMenuTrigger = DropdownPrimitive.Trigger;

export function DropdownMenuContent({ className, ...props }: ComponentProps<typeof DropdownPrimitive.Content>) {
  return (
    <DropdownPrimitive.Portal>
      <DropdownPrimitive.Content
        sideOffset={6}
        align="end"
        className={cn("z-50 min-w-48 rounded-lg border border-border bg-surface-2 p-1 shadow-xl", className)}
        {...props}
      />
    </DropdownPrimitive.Portal>
  );
}

export function DropdownMenuItem({ className, ...props }: ComponentProps<typeof DropdownPrimitive.Item>) {
  return (
    <DropdownPrimitive.Item
      className={cn(
        "flex cursor-pointer items-center gap-2 rounded-md px-3 py-2 text-sm text-fg outline-none select-none",
        "data-[highlighted]:bg-primary/15 data-[disabled]:opacity-50",
        className,
      )}
      {...props}
    />
  );
}

export const DropdownMenuSeparator = () => <DropdownPrimitive.Separator className="my-1 h-px bg-border" />;
