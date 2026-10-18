/** What a kill gives in gold: a champion's base bounty (without assists or streaks). */
export const KILL_GOLD = 300;

/** «4.1 kills», «1 kill» or «0.5 of a kill»; empty if the gold doesn't reach even a tenth. */
export function killsLabel(gold: number): string {
  const kills = Math.abs(gold) / KILL_GOLD;
  if (kills < 0.05) return "";
  if (kills >= 10) return `${Math.round(kills)} kills`;
  const rounded = Math.round(kills * 10) / 10;
  if (rounded === 1) return "1 kill";
  return rounded < 1 ? `${rounded} of a kill` : `${rounded.toFixed(1)} kills`;
}
