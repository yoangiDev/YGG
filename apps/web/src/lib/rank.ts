export const TIERS = [
  "IRON",
  "BRONZE",
  "SILVER",
  "GOLD",
  "PLATINUM",
  "EMERALD",
  "DIAMOND",
  "MASTER",
  "GRANDMASTER",
  "CHALLENGER",
] as const;

export type Tier = (typeof TIERS)[number];

export const RANK_COLORS: Record<Tier, string> = {
  IRON: "#8a8a9a",
  BRONZE: "#c0693a",
  SILVER: "#7a8fa8",
  GOLD: "#c8960f",
  PLATINUM: "#00b09e",
  EMERALD: "#2ecc6e",
  DIAMOND: "#5090f0",
  MASTER: "#a050d0",
  GRANDMASTER: "#e04030",
  CHALLENGER: "#f0d020",
};

/** The rank colour for text on a dark background: lightened 28% so that Master and Grandmaster reach 4.5:1. */
export const rankTextColor = (tier: Tier | null) => (tier ? `color-mix(in srgb, ${RANK_COLORS[tier]} 72%, white)` : "var(--color-stat-gray)");

const DEFAULT_CUTOFFS = { grandmaster: 1100, challenger: 1600 } as const;

export interface Cutoffs {
  grandmaster: number;
  challenger: number;
}

export function normalizeTier(tier: string | null | undefined): Tier | null {
  const upper = tier?.trim().toUpperCase();
  return TIERS.find((candidate) => candidate === upper) ?? null;
}

export function isApexTier(tier: Tier | null): boolean {
  return tier === "MASTER" || tier === "GRANDMASTER" || tier === "CHALLENGER";
}

export function rankImage(tier: string | null | undefined): string {
  const normalized = normalizeTier(tier);
  return `/img/ranks/${normalized ? normalized.toLowerCase() : "unranked"}.webp`;
}

function titleCase(value: string): string {
  return value.charAt(0) + value.slice(1).toLowerCase();
}

/** Next to the emblem, which already states the rank: "II · 45 LP", or just "320 LP" from Master up. */
export function lpLabel(tier: string | null | undefined, division?: string | null, lp?: number | null): string {
  const normalized = normalizeTier(tier);
  if (!normalized) return "Unranked";
  const points = `${lp ?? 0} LP`;
  return isApexTier(normalized) || !division ? points : `${division} · ${points}`;
}

/** "Gold II · 45 LP", "Master · 320 LP" (no division) or "Unranked". */
export function rankLabel(tier: string | null | undefined, division?: string | null, lp?: number | null): string {
  const normalized = normalizeTier(tier);
  if (!normalized) return "Unranked";
  const name = isApexTier(normalized) || !division ? titleCase(normalized) : `${titleCase(normalized)} ${division}`;
  return `${name} · ${lp ?? 0} LP`;
}

/**
 * Progress within the rank, in [0, 1]. In Master and Grandmaster there are no
 * divisions: it is measured against the region's LP cutoff to move up.
 */
export function rankProgress(tier: string | null | undefined, lp: number | null | undefined, cutoffs: Cutoffs = DEFAULT_CUTOFFS): number {
  const normalized = normalizeTier(tier);
  const points = Math.max(0, lp ?? 0);
  if (!normalized) return 0;
  if (normalized === "CHALLENGER") return 1;
  const target =
    normalized === "MASTER" ? cutoffs.grandmaster : normalized === "GRANDMASTER" ? cutoffs.challenger : 100;
  return target > 0 ? Math.min(1, points / target) : 1;
}

/** Position of the tier on the ladder (IRON = 0) or -1 if unranked. */
export function tierOrder(tier: string | null | undefined): number {
  const normalized = normalizeTier(tier);
  return normalized ? TIERS.indexOf(normalized) : -1;
}

const DIVISION_ORDER: Record<string, number> = { IV: 0, III: 1, II: 2, I: 3 };
const APEX_BASE = TIERS.indexOf("MASTER") * 400;

/**
 * LP on a continuous ladder, for drawing the elo: 100 per division and, from
 * Master (no divisions), the LP over the Master base. Null if unranked.
 */
export function ladderPoints(tier: string | null | undefined, division: string | null | undefined, lp: number | null | undefined): number | null {
  const normalized = normalizeTier(tier);
  if (!normalized) return null;
  const points = Math.max(0, lp ?? 0);
  if (isApexTier(normalized)) return APEX_BASE + points;
  return tierOrder(normalized) * 400 + (DIVISION_ORDER[division ?? ""] ?? 0) * 100 + Math.min(points, 100);
}

/**
 * Sortable number (higher = better). Below Master tier, division
 * and LP count; from Master up they share a ladder and LP rules.
 */
export function rankScore(tier: string | null | undefined, division: string | null | undefined, lp: number | null | undefined): number {
  const normalized = normalizeTier(tier);
  if (!normalized) return -1;
  const points = Math.max(0, lp ?? 0);
  if (isApexTier(normalized)) return APEX_BASE + points * 10 + tierOrder(normalized);
  return tierOrder(normalized) * 400 + (DIVISION_ORDER[division ?? ""] ?? 0) * 100 + Math.min(points, 100);
}
