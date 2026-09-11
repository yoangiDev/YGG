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
  /** Rótulo en verde sobre el título (por ejemplo, «New analysis»). */
  kicker?: string;
  children: ReactNode;
  className?: string;
}

/** Modal recto con pestaña ácida; en móvil se abre como hoja inferior (DESIGN.md §8.5). */
export function Dialog({ open, onOpenChange, title, description, kicker, children, className }: DialogProps) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-[110] bg-[rgba(5,7,7,0.72)] backdrop-blur-[2px] data-[state=open]:animate-[fade-in_.2s_ease]" />
        <DialogPrimitive.Content
          className={cn(
            "acid-tab-lg fixed top-1/2 left-1/2 z-[120] w-[min(92vw,40rem)] -translate-x-1/2 -translate-y-1/2 overflow-y-auto",
            "max-h-[min(92dvh,720px)] border border-acid/28 p-7 shadow-popover focus:outline-none",
            "bg-[linear-gradient(135deg,rgba(200,245,63,0.05),transparent_40%),#101412] data-[state=open]:animate-rise",
            "max-sm:top-auto max-sm:bottom-0 max-sm:left-0 max-sm:w-full max-sm:translate-x-0 max-sm:translate-y-0",
            "max-sm:border-x-0 max-sm:border-b-0 max-sm:px-5 max-sm:pb-[max(1.5rem,env(safe-area-inset-bottom))]",
            className,
          )}
          {...(description ? {} : { "aria-describedby": undefined })}
        >
          <div className="mb-6 flex items-start justify-between gap-6">
            <div className="min-w-0">
              {kicker && <p className="eyebrow mb-3 text-[10px] tracking-[0.18em]">{kicker}</p>}
              <DialogPrimitive.Title className="headline text-[26px] text-text sm:text-[32px]">{title}</DialogPrimitive.Title>
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
          className="z-[130] max-w-72 border border-line bg-popover px-2.5 py-1.5 text-xs font-medium text-soft shadow-dropdown"
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
  return <TabsPrimitive.List className={cn("flex gap-7 overflow-x-auto border-b border-line", className)} {...props} />;
}

/** Pestaña en mayúsculas con subrayado ácido que crece de izquierda a derecha. */
export function TabsTrigger({ className, ...props }: ComponentProps<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      className={cn(
        "relative -mb-px inline-flex cursor-pointer items-center gap-2 pb-3.5 text-[11px] font-black tracking-[0.14em] whitespace-nowrap text-subtle uppercase transition-colors",
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
        className={cn("z-[130] min-w-56 border border-line bg-[#0c0f10] p-1 shadow-dropdown data-[state=open]:animate-rise", className)}
        {...props}
      />
    </DropdownPrimitive.Portal>
  );
}

export function DropdownMenuItem({ className, ...props }: ComponentProps<typeof DropdownPrimitive.Item>) {
  return (
    <DropdownPrimitive.Item
      className={cn(
        "flex cursor-pointer items-center gap-2.5 px-3 py-2.5 text-[13px] font-bold text-soft outline-none select-none",
        "data-[disabled]:opacity-50 data-[highlighted]:bg-acid/[0.08] data-[highlighted]:text-acid",
        className,
      )}
      {...props}
    />
  );
}

export const DropdownMenuSeparator = () => <DropdownPrimitive.Separator className="my-1 h-px bg-line" />;
