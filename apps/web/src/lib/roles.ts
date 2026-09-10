import type { Schemas } from "@/lib/api/client";

export type Role = Schemas["Role"];

export const PLAYABLE_ROLES = ["TOP", "JUNGLE", "MID", "BOTTOM", "SUPPORT"] as const satisfies readonly Role[];

const LABELS: Record<Role, string> = {
  TOP: "Top",
  JUNGLE: "Jungle",
  MID: "Mid",
  BOTTOM: "Bot",
  SUPPORT: "Support",
  ALL: "All roles",
};

const ICONS: Record<Exclude<Role, "ALL">, string> = {
  TOP: "top",
  JUNGLE: "jungle",
  MID: "middle",
  BOTTOM: "bottom",
  SUPPORT: "support",
};

/** Riot usa varios nombres para el mismo rol según el endpoint. */
const ALIASES: Record<string, Role> = {
  MIDDLE: "MID",
  BOT: "BOTTOM",
  ADC: "BOTTOM",
  UTILITY: "SUPPORT",
  SUP: "SUPPORT",
};

export function normalizeRole(value: string | null | undefined): Role {
  const upper = (value ?? "").trim().toUpperCase();
  if (upper in LABELS) return upper as Role;
  return ALIASES[upper] ?? "ALL";
}

export function roleLabel(value: string | null | undefined): string {
  return LABELS[normalizeRole(value)];
}

export function roleIcon(value: string | null | undefined): string | null {
  const role = normalizeRole(value);
  // PNG y no WebP: son iconos de ~1 KB y el PNG original pesa menos (scripts/optimize_assets.py elige el menor).
  return role === "ALL" ? null : `/img/roles/${ICONS[role]}.png`;
}

export const REGIONS = [
  { value: "EUW", label: "Europe West" },
  { value: "EUNE", label: "Europe Nordic & East" },
  { value: "NA", label: "North America" },
  { value: "KR", label: "Korea" },
  { value: "BR", label: "Brazil" },
  { value: "LAN", label: "Latin America North" },
  { value: "LAS", label: "Latin America South" },
  { value: "OCE", label: "Oceania" },
  { value: "TR", label: "Türkiye" },
  { value: "JP", label: "Japan" },
  { value: "RU", label: "Russia" },
  { value: "PH", label: "Philippines" },
  { value: "SG", label: "Singapore" },
  { value: "TH", label: "Thailand" },
  { value: "TW", label: "Taiwan" },
  { value: "VN", label: "Vietnam" },
] as const;

export function regionLabel(value: string | null | undefined): string {
  const upper = (value ?? "").toUpperCase();
  return REGIONS.find((region) => region.value === upper)?.value ?? upper.replace(/\d+$/, "");
}
