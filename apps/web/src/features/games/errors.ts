import type { Located, Moment, MomentKind, Tone } from "@/features/snapshots/premiumData";
import { formatSigned } from "@/lib/format";

/**
 * A mistake's identity: how much it weighed (its verdict), where it happened and what came after. Everything comes from what the engine
 * already measures for each moment; here it is only given shape.
 */

export type VerdictKey = "blunder" | "mistake" | "slip" | "great" | "good" | "tradeoff" | "teamloss" | "teamwin";

export interface Verdict {
  key: VerdictKey;
  name: string;
  /** The chess annotation players already know: ?? blunder, ? mistake, ?! slip, ! good play. */
  glyph: string;
}

/** What the team decides, not the player: the grade already leaves it out («fights, objectives and the game's swings are your team's»). */
const TEAM_KINDS = new Set<MomentKind>(["objective", "fight", "swing"]);

/**
 * The verdict comes from the severity (1-3) the engine gives, not from the win chance, which isn't calibrated yet. A team
 * loss isn't a player's «Mistake»: it is said as what it is.
 */
export function verdictOf(moment: Pick<Moment, "tone" | "severity" | "kind">): Verdict {
  if (TEAM_KINDS.has(moment.kind) && moment.tone !== "neutral") {
    return moment.tone === "bad" ? { key: "teamloss", name: "Team loss", glyph: "−" } : { key: "teamwin", name: "Team win", glyph: "+" };
  }
  if (moment.tone === "bad") {
    if (moment.severity === 3) return { key: "blunder", name: "Blunder", glyph: "??" };
    if (moment.severity === 2) return { key: "mistake", name: "Mistake", glyph: "?" };
    return { key: "slip", name: "Slip", glyph: "?!" };
  }
  if (moment.tone === "good") {
    return moment.severity === 3 ? { key: "great", name: "Great play", glyph: "!!" } : { key: "good", name: "Good play", glyph: "!" };
  }
  return { key: "tradeoff", name: "Trade-off", glyph: "=" };
}

/** «the bot side river» → «Bot side river». */
export function placeLabel(where: string | null | undefined): string {
  const text = (where ?? "").replace(/^the /i, "");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

const clockOf = (seconds: number) => `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;

/** What a moment cost (or gave), in one line: «−310 gold · 20 s dead». */
export function costOf(moment: Moment): string {
  const parts: string[] = [];
  if (moment.gold) parts.push(`${formatSigned(moment.gold, 0)} gold`);
  else if (moment.value) parts.push(`${formatSigned(moment.value, 1)} WP`);
  if (moment.dead_for) parts.push(`${Math.round(moment.dead_for)} s dead`);
  return parts.join(" · ");
}

export interface Step {
  /** Which icon it carries: the moment's kind, or dead time and win chance, which aren't moments. */
  kind: MomentKind | "time" | "wp";
  label: string;
  sub?: string;
  tone: Tone;
  /** If the step is another moment of the game, its key: one click shows it on the map. */
  key?: string;
}

/** What falls while a player is dead is decided by the respawn plus the walk back (match_grade.md: N = 12 s). */
const RETURN_SECONDS = 12;
const NO_DEATH_SECONDS = 30;
/** What counts as «fell while you were away»: objectives, turrets, fights and swings. */
const FOLLOWS = new Set<MomentKind>(["objective", "tower", "fight", "swing"]);

/**
 * A mistake's chain: the mistake, the time it took from you, what fell meanwhile and what changed the game. Only
 * mistakes have it, and only if there are at least three links; otherwise there is no chain to tell.
 */
export function consequencesOf(located: Located, all: Located[]): Step[] {
  const { moment } = located;
  if (moment.tone !== "bad") return [];

  const steps: Step[] = [
    { kind: moment.kind, label: moment.title, sub: [moment.clock, moment.killer].filter(Boolean).join(" · "), tone: "bad", key: located.key },
  ];
  if (moment.dead_for) {
    steps.push({ kind: "time", label: `${Math.round(moment.dead_for)} s dead`, sub: `back at ${clockOf(moment.t + moment.dead_for)}`, tone: "bad" });
  }

  const end = moment.t + (moment.dead_for ? moment.dead_for + RETURN_SECONDS : NO_DEATH_SECONDS);
  const fell = all
    .filter((o) => o.key !== located.key && o.moment.tone === "bad" && FOLLOWS.has(o.moment.kind) && o.moment.t > moment.t && o.moment.t <= end)
    .slice(0, 2);
  for (const o of fell) {
    steps.push({ kind: o.moment.kind, label: o.moment.title, sub: `${Math.round(o.moment.t - moment.t)} s later`, tone: "bad", key: o.key });
  }

  if (moment.wp_before !== undefined && moment.wp_after !== undefined && moment.wp_before !== moment.wp_after) {
    steps.push({ kind: "wp", label: `Win chance ${moment.wp_before}% → ${moment.wp_after}%`, tone: moment.wp_after < moment.wp_before ? "bad" : "good" });
  }
  return steps.length >= 3 ? steps : [];
}
