/**
 * What the replay analysis stores in the replay analysis (app/service/replays.py and research/replays/coach.py) and the
 * pure functions with which the dashboard turns it into a map, lists and charts.
 */

import { MINIMAP } from "@/lib/ddragon";
import { formatDateTime } from "@/lib/format";
import { palette } from "@/lib/palette";

export type Tone = "bad" | "good" | "neutral";
export type MomentKind =
  | "death"
  | "camps"
  | "fog"
  | "gank"
  | "fight"
  | "objective"
  | "swing"
  | "flash"
  | "back"
  | "roam"
  | "opening"
  | "play"
  | "pair"
  | "ward"
  | "setup"
  | "trade"
  | "damage"
  | "dive"
  | "tower"
  | "plate";

/** A moment of a match, with its minute and its place on the map (coach.analyse). */
export interface Moment {
  id: number;
  t: number;
  end?: number;
  clock: string;
  x: number | null;
  z: number | null;
  where: string | null;
  kind: MomentKind;
  tone: Tone;
  severity: 1 | 2 | 3;
  title: string;
  text: string;
  gold?: number;
  value?: number;
  wp_before?: number;
  wp_after?: number;
  tags?: string[];
  killer?: string;
  dead_for?: number;
  camps?: string[];
  camp_spots?: [number, number][];
  objective?: string;
  /** The pit of the objective being set up (or not), to draw it next to where the player was. */
  objective_spot?: [number, number];
  opening?: OpeningState | SupportOpening;
  play?: Play;
}

/** A play by the jungler with live camps (research/replays/moments.py, `plays`): what they stopped farming and what
 * each participant got out of it, against what they would have farmed in that time. */
export interface Play {
  camps: string[];
  camp_gold: number;
  cost_gold: number;
  cost_xp: number;
  ledger: { champion: string; side: "ally" | "enemy"; gold: number; xp: number; died: number }[];
  net_gold: number;
  net_xp: number;
  /** Gold, XP and objectives together, in gold. */
  value: number;
  kills: number;
  deaths: number;
  objectives: string[];
}

/** The marksman's lane when their support leaves base (research/replays/openings.py, `botlane`), where they open, and
 * what came out. `wave`: 0 at their turret, 1 at the enemy's; `minions`: theirs minus the enemy's. */
export interface SupportOpening {
  role: "support";
  opens: "mid" | "bot";
  /** Probability that a Challenger or Grandmaster support opens through the middle on that map. */
  prob_mid: number | null;
  clear: boolean;
  lane: {
    state: string;
    wave: number;
    minions: number;
    adc_alive: boolean;
    adc_in_base: boolean;
    adc_hp: number;
    adc_at: number;
    enemies: number;
  };
  mid: { wave: number; enemy_hp: number; ally_hp: number };
  after: { adc_died: boolean; adc_exposed: boolean; wards: number; mid_backed: boolean; kills: number; reaches_bot: number | null };
  /** The lane when the recall of the one leaving began (the same `state` as `lane`); null if they were leaving after respawning. */
  recalled_on?: string | null;
}

export const isSupportOpening = (opening: OpeningState | SupportOpening): opening is SupportOpening =>
  "role" in opening;

/** A support ward (coach.wards): where and when it was placed, in which window, with what risk and what it showed. */
export interface Ward {
  t: number;
  clock: string;
  x: number;
  z: number;
  type: "totem" | "control" | "support";
  /** The window in which it was placed: setting up an objective, with the wave pushed, on leaving base, or none. */
  when: "objective" | "priority" | "reset" | "none";
  risk: "low" | "medium" | "high";
  /** Seconds it showed someone that its team wasn't seeing. */
  seconds: number;
  jungler: boolean;
  swept: boolean;
  lived: number;
  /** Died within the following 15 s without coming from a fight. */
  died: boolean;
}

export const WARD_WINDOWS = ["objective", "priority", "reset", "none"] as const;
export const WARD_RISKS = ["low", "medium", "high"] as const;

export interface WardGroup {
  key: string;
  wards: number;
  /** Those that showed someone. */
  useful: number;
  seconds: number;
  jungler: number;
  died: number;
}

/** The wards grouped by the window they were placed in or by their risk, in the order of `keys`. */
export function wardGroups(wards: Ward[], by: "when" | "risk", keys: readonly string[]): WardGroup[] {
  return keys.map((key) => {
    const group = wards.filter((w) => w[by] === key);
    return {
      key,
      wards: group.length,
      useful: group.filter((w) => w.seconds > 0).length,
      seconds: group.reduce((sum, w) => sum + w.seconds, 0),
      jungler: group.filter((w) => w.jungler).length,
      died: group.filter((w) => w.died).length,
    };
  });
}

/** One half of the map when the jungler leaves base (research/replays/openings.py, `state`): its camps (gold alive
 * now and in 30 s, and the enemy's), its objective (seconds until it spawns; 0 = alive) and its lane. */
export interface MapSide {
  gold_now?: number;
  gold_30?: number;
  gold_rival?: number;
  crab?: number;
  objective?: number;
  objective_which?: string;
  allies_alive: number;
  rivals_alive: number;
  health_ally: number;
  health_rival: number;
  no_flash_rival: number;
  ult_ally: number;
  gold_diff: number;
  /** Where the wave is: 0 against their turret, 1 against the enemy's. */
  wave: number;
}

export interface OpeningState {
  top: MapSide;
  bot: MapSide;
  mid: MapSide;
  rival: { seen: string; ago: number; cleared: string };
  opens: "top" | "bot";
  /** Probability that a Challenger or Grandmaster opens up top on that map. */
  prob_top: number | null;
  clear: boolean;
}

export interface Metric {
  value: number;
  percentile: number;
  median: number | null;
  winners: number | null;
  losers: number | null;
}

export interface Series {
  t: number[];
  gold: (number | null)[];
  cs: (number | null)[];
  xp: (number | null)[];
  team_gold: (number | null)[];
}

/** A row of the post-game scoreboard (coach.scoreboard). */
export interface ScoreboardPlayer {
  champion: string;
  role: string;
  you: boolean;
  side: "ally" | "enemy";
  kills: number;
  deaths: number;
  assists: number;
  level: number;
  cs: number;
  gold: number;
  damage: number;
  taken: number;
  vision: number;
  wards: number;
  plates: number;
}

export interface TeamTotals {
  kills: number;
  deaths: number;
  gold: number;
  towers: number;
  dragons: number;
  barons: number;
  heralds: number;
  grubs: number;
}

export interface Scoreboard {
  players: ScoreboardPlayer[];
  teams: { ally: TeamTotals; enemy: TeamTotals };
}

/** The match grade (coach.grade): what its moments add and subtract, and where each point comes from. */
export interface RatingPart {
  kind: MomentKind;
  points: number;
  good: number;
  bad: number;
}

export interface Rating {
  /** The points of its moments, brought to a 30-minute match. */
  total: number;
  parts: RatingPart[];
  /** From 1 to 100 against the players of their league in their position; missing if there is nothing to compare it with. */
  score?: number;
  /** What the moments of an ordinary match of their league and position add up to. */
  median?: number;
}

export interface Game {
  match_id: string;
  champion: string;
  role: string;
  win: boolean;
  duration: number;
  played_at?: string;
  opponent?: string | null;
  stats: Record<string, number>;
  flashes: { time: number; use: string; offensive: number; suboptimal: number }[];
  wp: [number, number][] | null; // [second, their team's WP], every 10 s
  moments?: Moment[];
  series?: Series;
  numbers?: Record<string, number | null>;
  /** Support only: each ward they placed. */
  wards?: Ward[];
  scoreboard?: Scoreboard;
  rating?: Rating;
}

export interface Reference {
  median: number;
  winners: number;
  losers: number;
}

/** How much those who win have to differ from those who lose, over the largest of the three, for the bar that compares them
 * to say anything. In the 16.19 reference deaths and fights with less gold differ by 26-53%; the rest
 * (camps, fog, openings, flash, backs, departures) by less than 21%, and the two marks fall on top of each other. */
const SEPARATES = 0.25;

export const separates = (ref: Reference) =>
  Math.abs(ref.winners - ref.losers) > SEPARATES * Math.max(Math.abs(ref.median), Math.abs(ref.winners), Math.abs(ref.losers));

/** What repeats in their matches (coach.patterns). `weight`: 0 like those who win, 1 like those who lose. */
export interface Pattern {
  kind: string;
  title: string;
  text: string;
  tone: Tone;
  weight: number;
  moments: string[];
  per_game?: number;
  count?: number;
  gold?: number;
  value?: number;
  unseen_share?: number;
  taken?: number;
  reference?: Reference | null;
  /** The support's vision score (0-100; 50 is the median of their league) and what it is made of. */
  score?: number;
  parts?: ScorePart[];
}

/** A part of the vision score: its mean, the median of their league and their percentile set so that more is better. */
export interface ScorePart {
  key: string;
  label: string;
  value: number;
  median: number;
  score: number;
  better: "higher" | "lower";
}

export interface PremiumData {
  summary: {
    tier: string;
    role: string;
    games: number;
    wins: number;
    metrics: Record<string, Metric>;
    patterns?: Pattern[];
    /** The matches of their main role, which is where the patterns come from (they are compared with that role). */
    role_games?: number;
  };
  games: Game[];
  missing: Record<string, string>;
}

/** Claude's coach review (app/service/review.py). The `moments` are `match:moment` keys. */
export interface Review {
  headline: string;
  coach_summary: string;
  lessons: { title: string; why: string; fix: string; moments: string[] }[];
  strengths: { title: string; detail: string; moments: string[] }[];
  game_notes: { match_id: string; note: string }[];
  moment_notes: { moment: string; note: string }[];
  next_game: string[];
  model?: string;
}

/** Reviews from before the coach dashboard had another shape: they are recognised by lacking `coach_summary`. */
export function isCoachReview(review: unknown): review is Review {
  return typeof review === "object" && review !== null && "coach_summary" in review && "lessons" in review;
}

export const KINDS: Record<MomentKind, string> = {
  death: "Deaths",
  camps: "Camps",
  fog: "Fog of war",
  gank: "Ganks",
  fight: "Fights",
  objective: "Objectives",
  swing: "Turning points",
  flash: "Flash",
  back: "Recalls",
  roam: "Roams",
  opening: "Openings",
  play: "Plays",
  pair: "Camp pairs",
  ward: "Vision",
  setup: "Objective setups",
  trade: "Trades",
  damage: "Damage in fights",
  dive: "Waves you can't hold",
  tower: "Mid turret",
  plate: "Turret plates",
};

export const TONE_COLOR: Record<Tone, string> = { bad: palette.red, good: palette.green, neutral: palette.gold };

export const momentKey = (matchId: string, id: number) => `${matchId}:${id}`;

export interface Located {
  key: string;
  game: Game;
  gameIndex: number;
  moment: Moment;
}

/** The moments of a match, in the order they must be shown: the most serious first. */
export function gameMoments(index: Map<string, Located>, matchId: string): Located[] {
  return [...index.values()].filter((m) => m.game.match_id === matchId).sort((a, b) => a.moment.t - b.moment.t);
}

/** Each moment of each match by its `match:moment` key, which is how the patterns and the review cite them. */
export function indexMoments(games: Game[]): Map<string, Located> {
  const index = new Map<string, Located>();
  games.forEach((game, gameIndex) => {
    for (const moment of game.moments ?? []) {
      const key = momentKey(game.match_id, moment.id);
      index.set(key, { key, game, gameIndex, moment });
    }
  });
  return index;
}

/** Game position → minimap SVG coordinates (that of MINIMAP: z grows upward, so it goes negative). */
export function mapPoint(x: number, z: number): { cx: number; cy: number } {
  return { cx: x, cy: -z };
}

export const MAP_VIEWBOX = `${MINIMAP.x[0]} ${-MINIMAP.z[1]} ${MINIMAP.x[1] - MINIMAP.x[0]} ${MINIMAP.z[1] - MINIMAP.z[0]}`;

/** Their team's WP (0-100) at second `t`, from the nearest point of the curve. */
export function wpAt(game: Game, t: number): number | null {
  if (!game.wp?.length) return null;
  const best = game.wp.reduce((a, b) => (Math.abs(b[0] - t) < Math.abs(a[0] - t) ? b : a));
  return Math.round(best[1] * 100);
}

export interface TrendRow {
  game: number;
  label: string;
  champion: string;
  win: boolean;
  /** The match grade (1-100), if it could be compared with their league. */
  rating: number | null;
  gold14: number | null;
  wp15: number | null;
  deathsEarly: number;
  deathsLate: number;
  campGold: number | null;
  stolenGold: number | null;
  invadedGold: number | null;
  showupsNothing: number | null;
  blind: number | null;
  openingsMatched: number | null;
  openingsAgainst: number | null;
  playsGood: number | null;
  playsBad: number | null;
  playsEven: number | null;
  openingsMid: number | null;
  openingsBot: number | null;
  wardsUseful: number | null;
  wardsSilent: number | null;
  controlWards: number | null;
  emptySeconds: number | null;
  setupsPrepared: number | null;
  setupsAway: number | null;
  recallsGood: number | null;
  recallsBad: number | null;
  tradesWon: number | null;
  tradesLost: number | null;
  fightDamage: number | null;
  fightsCarried: number | null;
  fightsSilent: number | null;
  platesLane: number | null;
  platesAgainst: number | null;
  mistakes: number;
  [kind: string]: number | string | boolean | null;
}

/** `a - b` if both are known. */
const minus = (a: number | null | undefined, b: number | null | undefined) =>
  a === null || a === undefined || b === null || b === undefined ? null : a - b;

/** One row per match, in order, with what follows from one to the next and the mistakes of each kind. */
export function trendRows(games: Game[]): TrendRow[] {
  return games.map((game, index) => {
    const numbers = game.numbers ?? {};
    const bad = (game.moments ?? []).filter((m) => m.tone === "bad");
    const byKind: Record<string, number> = {};
    for (const moment of bad) byKind[moment.kind] = (byKind[moment.kind] ?? 0) + 1;
    const blind = "blind_half_rival_blind" in game.stats
      ? game.stats.blind_half_rival_blind + (game.stats.blind_overextend_blind ?? 0)
      : null;
    return {
      ...byKind,
      game: index + 1,
      label: `G${index + 1}`,
      champion: game.champion,
      win: game.win,
      rating: game.rating?.score ?? null,
      gold14: numbers.gold_diff_14 ?? null,
      wp15: numbers.wp_15 ?? null,
      deathsEarly: numbers.deaths_early ?? 0,
      deathsLate: numbers.deaths_late ?? 0,
      campGold: numbers.camp_gold_lost ?? null,
      stolenGold: numbers.camp_gold_stolen ?? null,
      invadedGold: numbers.camp_gold_invaded ?? null,
      showupsNothing: numbers.showups_nothing ?? null,
      blind,
      openingsMatched: numbers.openings_matched ?? null,
      openingsAgainst: minus(numbers.openings_clear, numbers.openings_matched ?? 0),
      playsGood: numbers.plays_good ?? null,
      playsBad: numbers.plays_bad ?? null,
      playsEven: minus(minus(numbers.plays, numbers.plays_good ?? 0), numbers.plays_bad ?? 0),
      openingsMid: numbers.openings_mid ?? null,
      openingsBot: minus(numbers.openings, numbers.openings_mid),
      wardsUseful: numbers.wards_useful ?? null,
      wardsSilent: minus(numbers.wards, numbers.wards_useful),
      controlWards: numbers.control_wards ?? null,
      emptySeconds: numbers.item_empty_seconds ?? null,
      setupsPrepared: numbers.setups_prepared ?? null,
      setupsAway: numbers.setups_away ?? null,
      recallsGood: numbers.recalls_good ?? null,
      recallsBad: minus(numbers.recalls_judged, numbers.recalls_good),
      tradesWon: numbers.trades_won ?? null,
      tradesLost: numbers.trades_lost ?? null,
      fightDamage: numbers.fight_damage ?? null,
      fightsCarried: numbers.fights_carried ?? null,
      fightsSilent: numbers.fights_silent ?? null,
      platesLane: numbers.plates_lane ?? null,
      platesAgainst: numbers.plates_against ?? null,
      mistakes: bad.length,
    };
  });
}

/** "24 Sep, 21:32" of when it was played, or null if unknown. */
export function playedAt(game: Game): string | null {
  return game.played_at ? formatDateTime(game.played_at) : null;
}
