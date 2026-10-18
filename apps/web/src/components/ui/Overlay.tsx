import * as DialogPrimitive from "@radix-ui/react-dialog";
import * as DropdownPrimitive from "@radix-ui/react-dropdown-menu";
import * as TabsPrimitive from "@radix-ui/react-tabs";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import { X } from "lucide-react";
import type { ComponentProps, ReactNode } from "react";

import { cn } from "@/lib/cn";

// ── Dialog ────────────────────────────────────────────────────────────────────

// Dialogs are opened from buttons that aren't a `Dialog.Trigger`, and Radix only returns focus to that trigger: without
// this, on closing the focus fell on <body> and the keyboard went back to the top of the page. The last element focused
// outside a dialog is remembered, since the page loads: looking at the focus on opening isn't enough (an autoFocus field has already
// taken it) nor on mounting the dialog (some are mounted right as they open).
let lastFocusOutsideDialog: HTMLElement | null = null;
if (typeof document !== "undefined") {
  document.addEventListener("focusin", (event) => {
    if (event.target instanceof HTMLElement && !event.target.closest("[role=dialog]")) lastFocusOutsideDialog = event.target;
  });
}

interface DialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  /** Green label above the title (for example, «New analysis»). */
  kicker?: string;
  children: ReactNode;
  className?: string;
}

/** Straight modal with an acid tab; on mobile it opens as a bottom sheet (DESIGN.md §8.5). */
export function Dialog({ open, onOpenChange, title, description, kicker, children, className }: DialogProps) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-[110] bg-[rgba(5,7,7,0.72)] backdrop-blur-[2px] data-[state=open]:animate-[fade-in_.2s_ease]" />
        <DialogPrimitive.Content
          onCloseAutoFocus={(event) => {
            const back = lastFocusOutsideDialog;
            if (back?.isConnected && back !== document.body) {
              event.preventDefault();
              back.focus();
            }
          }}
          className={cn(
            "acid-tab-lg fixed top-1/2 left-1/2 z-[120] w-[min(92vw,40rem)] -translate-x-1/2 -translate-y-1/2 overflow-y-auto",
            "max-h-[min(92dvh,720px)] border border-acid/28 p-7 shadow-popover focus:outline-none",
            "bg-popover bg-[linear-gradient(135deg,rgba(200,245,63,0.05),transparent_40%)] data-[state=open]:animate-rise",
            "max-sm:top-auto max-sm:bottom-0 max-sm:left-0 max-sm:w-full max-sm:translate-x-0 max-sm:translate-y-0",
            "max-sm:border-x-0 max-sm:border-b-0 max-sm:px-5 max-sm:pb-[max(1.5rem,env(safe-area-inset-bottom))]",
            className,
          )}
          {...(description ? {} : { "aria-describedby": undefined })}
        >
          <div className="mb-6 flex items-start justify-between gap-6">
            <div className="min-w-0">
              {kicker && <p className="eyebrow mb-3 text-xs tracking-[0.18em]">{kicker}</p>}
              <DialogPrimitive.Title className="headline text-xl text-text sm:text-xl">{title}</DialogPrimitive.Title>
              {description && (
                <DialogPrimitive.Description className="mt-3 text-sm leading-relaxed text-muted">
                  {description}
                </DialogPrimitive.Description>
              )}
            </div>
            <DialogPrimitive.Close
              className="grid size-9 shrink-0 cursor-pointer place-items-center border border-line text-soft transition-colors hover:border-acid hover:text-acid"
              aria-label="Close"
            >
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
          className="z-[130] max-w-72 border border-line bg-popover px-2.5 py-1.5 text-xs font-normal text-soft shadow-dropdown"
        >
          {content}
          <TooltipPrimitive.Arrow className="fill-popover" />
        </TooltipPrimitive.Content>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  );
}

// ── Tabs ──────────────────────────────────────────────────────────────────────

export const Tabs = TabsPrimitive.Root;
export const TabsContent = TabsPrimitive.Content;

export function TabsList({ className, ...props }: ComponentProps<typeof TabsPrimitive.List>) {
  // The line below is an inner shadow and not a border: that way the active tab's underline doesn't spill out of the
  // container and the row can scroll horizontally when the tabs don't fit (mobile).
  return <TabsPrimitive.List className={cn("flex gap-5 overflow-x-auto shadow-[inset_0_-1px_0_var(--color-line)] sm:gap-7", className)} {...props} />;
}

/** Uppercase tab with an acid underline that grows from left to right. */
export function TabsTrigger({ className, ...props }: ComponentProps<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      className={cn(
        "relative inline-flex shrink-0 cursor-pointer items-center gap-2 pb-3.5 text-xs font-black tracking-[0.14em] whitespace-nowrap text-subtle uppercase transition-colors",
        "after:absolute after:inset-x-0 after:bottom-0 after:h-0.5 after:origin-left after:scale-x-0 after:bg-acid after:transition-transform after:duration-300",
        "hover:text-text data-[state=active]:text-acid data-[state=active]:after:scale-x-100",
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
        sideOffset={8}
        align="end"
        className={cn("z-[130] min-w-56 border border-line bg-popover p-1 shadow-dropdown data-[state=open]:animate-rise", className)}
        {...props}
      />
    </DropdownPrimitive.Portal>
  );
}

export function DropdownMenuItem({ className, ...props }: ComponentProps<typeof DropdownPrimitive.Item>) {
  return (
    <DropdownPrimitive.Item
      className={cn(
        "flex cursor-pointer items-center gap-2.5 px-3 py-2.5 text-sm font-bold text-soft outline-none select-none",
        "data-[disabled]:opacity-50 data-[highlighted]:bg-acid/[0.08] data-[highlighted]:text-acid",
        className,
      )}
      {...props}
    />
  );
}

export const DropdownMenuSeparator = () => <DropdownPrimitive.Separator className="my-1 h-px bg-line" />;
