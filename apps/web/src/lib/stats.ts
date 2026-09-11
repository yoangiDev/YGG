/**
 * Colores semánticos de las métricas (docs/FRONTEND_COLOR_GUIDE.md).
 *
 * El backend decide el estado (excellent/good/normal/bad) con sus umbrales; el
 * frontend solo lo traduce a color. Cambiar un umbral en ygg-core se refleja
 * aquí sin tocar nada.
 */

export type StatTone = "gold" | "blue" | "green" | "gray" | "red";

export const toneText: Record<StatTone, string> = {
  gold: "text-stat-gold",
  blue: "text-stat-blue",
  green: "text-stat-green",
  gray: "text-stat-gray",
  red: "text-stat-red",
};

export const toneBorder: Record<StatTone, string> = {
  gold: "border-stat-gold/40",
  blue: "border-stat-blue/40",
  green: "border-stat-green/40",
  gray: "border-stat-gray/30",
  red: "border-stat-red/40",
};

export const toneBackground: Record<StatTone, string> = {
  gold: "bg-stat-gold",
  blue: "bg-stat-blue",
  green: "bg-stat-green",
  gray: "bg-stat-gray",
  red: "bg-stat-red",
};

const STATUS_LABELS: Record<string, string> = {
  excellent: "Excellent",
  good: "Good",
  normal: "Average",
  bad: "Needs work",
};

export function isNegativeMetric(key: string): boolean {
  return /death|muerte/i.test(key);
}

/** En las métricas de muertes lo "normal" es neutro y lo "malo" es rojo; en el resto, lo malo es gris. */
export function statTone(key: string, status: string): StatTone {
  const normalized = status.toLowerCase();
  if (normalized === "excellent") return "gold";
  if (normalized === "good") return "blue";
  if (isNegativeMetric(key)) return normalized === "bad" ? "red" : "gray";
  return normalized === "normal" ? "green" : "gray";
}

export function statusLabel(status: string): string {
  return STATUS_LABELS[status.toLowerCase()] ?? status;
}

export function winRateTone(winRate: number): StatTone {
  if (winRate >= 55) return "gold";
  if (winRate >= 50) return "blue";
  if (winRate >= 45) return "green";
  return "gray";
}

export function kdaTone(kda: number): StatTone {
  if (kda >= 5) return "gold";
  if (kda >= 4) return "blue";
  if (kda >= 3) return "green";
  return "gray";
}

/** Puntuación de rendimiento 0-100 relativa a la partida (el mejor de los 10 tiene 100). */
export function scoreTone(score: number): StatTone {
  if (score >= 90) return "gold";
  if (score >= 75) return "blue";
  if (score >= 55) return "green";
  return "gray";
}
