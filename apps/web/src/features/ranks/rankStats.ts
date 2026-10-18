import { formatNumber, formatPercent, formatSigned } from "@/lib/format";

import raw from "./stats.json";

/**
 * The results of research/replays/leagues.py (--json) over the whole harvest sample. Nothing the
 * tab shows is copied by hand: each figure is requested here by its key, and the test checks that they all exist.
 */
export const TIERS = ["GOLD", "PLATINUM", "EMERALD", "DIAMOND", "MASTER", "GRANDMASTER", "CHALLENGER"] as const;
export const TIER_NAMES = ["Gold", "Platinum", "Emerald", "Diamond", "Master", "Grandmaster", "Challenger"];
export const TIER_SHORT = ["G", "P", "E", "D", "M", "GM", "C"];

export type Role = "TOP" | "JUNGLE" | "MIDDLE" | "BOTTOM" | "UTILITY";
export const ROLES: { role: Role; name: string }[] = [
  { role: "TOP", name: "Top" },
  { role: "JUNGLE", name: "Jungle" },
  { role: "MIDDLE", name: "Mid" },
  { role: "BOTTOM", name: "ADC" },
  { role: "UTILITY", name: "Support" },
];

/** Mean per league (from Gold to Challenger), rank correlation with the league and its z. */
export interface Trend {
  means: number[];
  rho: number;
  z: number;
}

/** Winner against loser of the same position: in what share of matches the winner has more. */
export interface WinSplit {
  all: number;
  low: number;
  high: number;
  z: number;
  z_diff: number;
  n: number;
}

export type Team = "100" | "200";

/** Where the wards of a group of leagues fall: the share of them in each cell, per ten thousand. */
export interface WardGroup {
  wards: number;
  games: number;
  /** cells × cells, row by row from the bottom (z) and left to right (x), at their real place on the map */
  squares: number[];
}

interface RankStats {
  duration: Trend;
  positions: Record<string, Record<string, Trend>>;
  winner: Record<string, Record<string, WinSplit>>;
  situations: Record<string, Record<string, Trend>>;
  objectives: Record<string, Record<string, { wins: number; n: number }>>;
  games: Record<string, number>;
  /** "high" is Grandmaster and Challenger; "rest", from Gold to Master. By team: "100" blue, "200" red */
  map_wards: { side: number; cells: number; high: Record<Team, WardGroup>; rest: Record<Team, WardGroup> };
}

export const stats = raw as RankStats;

/** |z| >= 4, the analysis threshold (p < 0.0001 with ~700 tests). */
export const Z = 4;

export type Ref = { role: Role; key: string } | { table: string; key: string };

export interface Metric {
  ref: Ref;
  label: string;
  /** "%": the datum is a proportion from 0 to 1 */
  unit?: "%" | "s";
  digits?: number;
  /** Multiplies the datum: 0.1 turns what is per 10 minutes into per minute. */
  scale?: number;
}

export function trend(ref: Ref): Trend {
  const found = "role" in ref ? stats.positions[ref.role]?.[ref.key] : stats.situations[ref.table]?.[ref.key];
  if (!found) throw new Error(`No rank data for ${JSON.stringify(ref)}`);
  return found;
}

export function winSplit(role: Role, key: string): WinSplit | undefined {
  return stats.winner[role]?.[key];
}

/** The per-league means in the unit they are shown in (proportions, in %). */
export function tierValues(metric: Metric): number[] {
  const factor = (metric.scale ?? 1) * (metric.unit === "%" ? 100 : 1);
  return trend(metric.ref).means.map((value) => value * factor);
}

export function formatValue(value: number, metric: Metric): string {
  const digits = metric.digits ?? (Math.abs(value) >= 100 ? 0 : Math.abs(value) >= 10 ? 1 : 2);
  if (metric.unit === "%") return formatPercent(value, metric.digits ?? 1);
  const number = formatNumber(value, digits);
  return metric.unit === "s" ? `${number} s` : number;
}

/** From Gold to Challenger, in %: "+17%", "−52%". */
export function relativeChange(values: number[]): string {
  const first = values[0] ?? 0;
  const last = values[values.length - 1] ?? 0;
  return first ? `${formatSigned((100 * (last - first)) / Math.abs(first), 0)}%` : "—";
}

export function isSignificant(metric: Metric): boolean {
  return Math.abs(trend(metric.ref).z) >= Z;
}

/** "2×" when something doubles or more, otherwise "+22%" or "−27%": read at a glance. */
export function friendlyChange(values: number[]): string {
  const first = values[0] ?? 0;
  const last = values[values.length - 1] ?? 0;
  if (first > 0 && last / first >= 1.8) return `${formatNumber(last / first, 1)}×`;
  return relativeChange(values);
}

/**
 * In what share of matches the winner has more of something (less, with `less`), averaged over the roles in which it
 * really separates (|z| >= Z).
 */
export function winnerShare(key: string, less = false): number {
  const shares = ROLES.map(({ role }) => winSplit(role, key))
    .filter((split): split is WinSplit => split !== undefined && Math.abs(split.z) >= Z)
    .map((split) => (less ? 1 - split.all : split.all));
  return shares.length ? shares.reduce((total, share) => total + share, 0) / shares.length : 0.5;
}

/**
 * Share of a team's wards that fall in the enemy half of the map: for blue, above the river diagonal
 * (x + z = side); for red, below. Cells that the diagonal splits through the middle count half.
 */
export function enemyHalfShare(group: WardGroup, team: Team): number {
  const { cells } = stats.map_wards;
  let share = 0;
  group.squares.forEach((value, index) => {
    const side = ((index % cells) + Math.floor(index / cells) + 1 - cells) * (team === "100" ? 1 : -1);
    share += side > 0 ? value : side === 0 ? value / 2 : 0;
  });
  return share / 1e4;
}

/** Share of objectives taken by the team that did more of something before it fell. */
export function objectiveShare(key: string): number {
  const all = stats.objectives[key]?.all;
  return all && all.n ? all.wins / all.n : 0.5;
}
