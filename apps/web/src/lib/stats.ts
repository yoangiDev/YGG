/**
 * Semantic colours of the metrics (docs/design/color-guide.md).
 *
 * The backend decides the status (excellent/good/normal/bad) with its thresholds; the
 * frontend only translates it to colour. Changing a threshold in ygg-core is reflected
 * here without touching anything.
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
  return /death/i.test(key);
}

/** In death metrics "normal" is neutral and "bad" is red; in the rest, bad is grey. */
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

/**
 * 0-100 grade against the role's Challenger matches (ygg-core match_score): 70 is the target, playing better than
 * two out of three; an average Challenger match scores 63-64. Same bands as the metrics' status.
 */
export function scoreTone(score: number): StatTone {
  if (score >= 85) return "gold";
  if (score >= 70) return "blue";
  if (score >= 55) return "green";
  return "gray";
}
