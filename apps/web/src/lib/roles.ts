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

/** Riot uses several names for the same role depending on the endpoint. */
const ALIASES: Record<string, Role> = {
  MIDDLE: "MID",
  BOT: "BOTTOM",
  ADC: "BOTTOM",
  UTILITY: "SUPPORT",
  SUP: "SUPPORT",
};

function normalizeRole(value: string | null | undefined): Role {
  const upper = (value ?? "").trim().toUpperCase();
  if (upper in LABELS) return upper as Role;
  return ALIASES[upper] ?? "ALL";
}

export function roleLabel(value: string | null | undefined): string {
  return LABELS[normalizeRole(value)];
}

export function roleIcon(value: string | null | undefined): string | null {
  const role = normalizeRole(value);
  // PNG and not WebP: they are ~1 KB icons and the original PNG weighs less (scripts/optimize_assets.py picks the smaller).
  return role === "ALL" ? null : `/img/roles/${ICONS[role]}.png`;
}

export const REGIONS = [
  { value: "EUW", label: "Europe West" },
  { value: "NA", label: "North America" },
  { value: "LAS", label: "Latin America South" },
  { value: "LAN", label: "Latin America North" },
  { value: "KR", label: "Korea" },
  { value: "EUNE", label: "Europe Nordic & East" },
  { value: "BR", label: "Brazil" },
] as const;

export type Region = (typeof REGIONS)[number]["value"];

/** The region if it is one supported by the API ("euw1" or "euw" → "EUW"); null if not. */
export function toRegion(value: string | null | undefined): Region | null {
  const upper = (value ?? "").toUpperCase().replace(/\d+$/, "");
  return REGIONS.find((region) => region.value === upper)?.value ?? null;
}

export function regionLabel(value: string | null | undefined): string {
  const upper = (value ?? "").toUpperCase();
  return REGIONS.find((region) => region.value === upper)?.value ?? upper.replace(/\d+$/, "");
}
