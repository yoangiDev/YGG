import { cn } from "@/lib/cn";

export type ArrowDirection = "ne" | "right" | "left" | "down";

// Puntas rectas (linecap square, linejoin miter), a juego con las esquinas del sistema.
const PATHS: Record<ArrowDirection, string> = {
  ne: "M4 12 12 4M5.5 4H12v6.5",
  right: "M2.5 8h11M9 3.5 13.5 8 9 12.5",
  left: "M13.5 8h-11M7 3.5 2.5 8 7 12.5",
  down: "M8 2.5v11M3.5 9 8 13.5 12.5 9",
};

export function ArrowIcon({ direction = "ne", className }: { direction?: ArrowDirection; className?: string }) {
  return (
    <svg
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="square"
      strokeLinejoin="miter"
      aria-hidden="true"
      className={cn("size-[13px] shrink-0", className)}
    >
      <path d={PATHS[direction]} />
    </svg>
  );
}
