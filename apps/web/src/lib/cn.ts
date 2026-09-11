import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/** Combina clases condicionales resolviendo conflictos de Tailwind (la última gana). */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
