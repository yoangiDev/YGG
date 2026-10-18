import { ArrowRight, CircleCheck, Crosshair, Lightbulb } from "lucide-react";
import { useRef, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { ChampionIcon } from "@/components/player/PlayerBits";
import { cn } from "@/lib/cn";
import { formatNumber, formatSigned } from "@/lib/format";
import { categorical, palette } from "@/lib/palette";

import { GameCard, gameCardId } from "./GameCard";
import { KIND_ICONS } from "./MomentExplorer";
import { WardMap } from "./WardMap";
import {
  gameMoments,
  indexMoments,
  isCoachReview,
  KINDS,
  type Located,
  type Metric,
  type MomentKind,
  type Pattern,
  type PremiumData,
  type Review,
  type ScorePart,
  separates,
  TONE_COLOR,
  type TrendRow,
  trendRows,
} from "./premiumData";

export type { PremiumData, Review } from "./premiumData";

/** English name of each column of the features table (research/replays/features.py). */
const LABELS: Record<string, string> = {
  kills: "Kills", deaths: "Deaths", assists: "Assists", cs: "CS", cs_jungle: "Jungle CS", gold: "Gold",
  level: "Level", damage: "Damage to champions", damage_received: "Damage taken", vision: "Vision score", wards: "Wards placed",
  wards_killed: "Wards killed", cc_to_others: "CC on enemies (s)", plates: "Plates you got gold from", plate_gold: "Gold from plates",
  lane_cs: "Lane CS at 14", lane_plates: "Plates you finished at 14", lane_gold: "Lane gold at 14",
  lane_plates_lane: "Lane plates at 14", lane_plates_against: "Plates given up at 14",
  resources_damage_done: "Lane damage dealt", resources_damage_received: "Lane damage taken",
  resources_health_mean: "Average HP in lane", resources_health_minimum: "Lowest HP in lane", resources_mana_mean: "Average mana in lane",
  blind_rival_side: "Time in enemy territory", blind_half_rival: "Time in enemy half",
  blind_half_rival_blind: "Enemy half, jungler unknown", blind_half_rival_no_river: "Enemy half, river unwarded",
  blind_half_rival_with_the_wave: "Enemy half, with the wave", blind_at_home: "Time on your side",
  blind_overextend: "Overextended", blind_overextend_blind: "Overextended, jungler unknown",
  blind_overextend_no_river: "Overextended, river unwarded", blind_overextend_with_the_wave: "Overextended with the wave",
  blind_half_rival_dies: "Deaths in enemy half", blind_overextend_dies: "Deaths while overextended",
  blind_half_rival_and_was: "Enemy half, jungler was there", blind_overextend_and_was: "Overextended, jungler was there",
  vision_useful: "Wards that revealed someone", vision_seconds_of_info: "Seconds of ward info",
  vision_to_jungler: "Wards that found the jungler", vision_exempt: "Wards not needed",
  dying_deaths: "Deaths after 14:00", dying_seconds_dead: "Seconds dead after 14:00",
  dying_respawn_mean: "Average respawn after 14:00 (s)", dying_gold_per_second: "Gold per second alive after 14:00",
  dying_damage_per_second: "Damage per second alive after 14:00", dying_gold_lost: "Gold lost while dead after 14:00",
  dying_damage_lost: "Damage lost while dead after 14:00", dying_charges_recovered: "Ward charges back while dead",
  finishes_hits: "Last hits", finishes_missed: "Missed last hits", finishes_hit_rate: "Last-hit rate",
  back1_health_lost: "HP lost before 1st back", back2_health_lost: "HP lost before 2nd back",
  freezes: "Freezes", freeze_seconds: "Seconds freezing", freeze_cs_denied: "CS denied by freezing",
  backs: "Backs", backs_cs_lost: "CS lost to back timing",
  prio: "Waves crashed", prio_unused: "Crashed waves not used", prio_cs_lost: "CS lost after crashing",
  departures: "Times leaving lane", departures_no_wave: "Left lane without the wave",
  departures_cs_lost: "CS lost leaving lane", departures_taking_nothing: "Leaves that gained nothing",
  sidelane_turns: "Side-lane turns", sidelane_seconds: "Seconds side-laning", sidelane_cs: "Side-lane CS",
  sidelane_to_tower: "Side waves to the tower", sidelane_deaths: "Side-lane deaths",
  trades: "Lane trades", trades_dies: "Trades that ended in death", trades_summoners: "Summoners spent in trades",
  punishments: "Punished enemies alone", punished: "Times punished alone",
  flashes: "Flashes", flash_objective: "Flashes at objectives", flash_teamfight: "Flashes in teamfights",
  flash_skirmish: "Flashes in skirmishes", flash_out_of_fight: "Flashes outside fights",
  flash_offensive: "Offensive flashes", flash_suboptimal: "Wasted flashes",
  fights: "Fights", outnumbered_fights: "Fights with an item deficit", teamfights: "Teamfights",
  teamfight_damage: "Teamfight damage", teamfight_damage_mean: "Damage per teamfight", setups: "Objective setup",
  idle_delay: "Camp clear delay", idle_clears_lost: "Camp clears lost", idle_gold: "Gold lost to idle camps",
  idle_xp: "XP lost to idle camps", idle_points: "Idle camp cost",
  recall_gold_max: "Most gold carried", recall_seconds_above: "Seconds above recall gold",
  jungler_invisible: "Seconds unseen", jungler_visible: "Seconds seen", jungler_streak: "Longest time unseen",
  jungler_shows_up: "Times showing up", jungler_taking_nothing: "Show-ups that gained nothing",
  roam_seconds: "Seconds while support roams", roam_health_lost: "HP lost while support roams",
  roam_deaths: "Deaths while support roams", roam_invocadores: "Summoners spent while support roams",
  roam_r: "Ultimates while support roams", roam_accompanied_health_lost: "HP lost with support",
  roam_accompanied_deaths: "Deaths with support", roam_acompanado_invocadores: "Summoners with support",
  roam_acompanado_r: "Ultimates with support", roam_accompanied_seconds: "Seconds with support",
  jungler_in_lane: "Times seen in a lane", pairs_clears: "Small-camp clears", pairs_paired: "Camps cleared with their pair",
  pairs_broken: "Camp pairs split", pairs_stolen: "Pairs lost to a steal", pairs_unpaired: "Clears already out of step",
  plays: "Plays before 14:00", plays_good_ones: "Plays that paid", plays_bad_ones: "Plays that didn't pay",
  plays_value: "Net value of plays (gold)", plays_cost_gold: "Gold of clears delayed by plays",
  plays_with_camps: "Plays with camps up",
  guard_wards: "Wards placed (whole game)", guard_wards_10: "Wards per 10 min",
  guard_useful_share: "Wards that revealed someone", guard_info_per_ward: "Seconds of info per ward",
  guard_to_jungler_10: "Wards on their jungler per 10 min", guard_objective_share: "Wards around objectives",
  guard_loose_share: "Wards with no window", guard_risk_high_share: "High-risk wards",
  guard_costs_it: "Deaths placing a ward", guard_sweeps_share: "Wards swept by the enemy",
  support_item_since: "Support item gets wards (s)", support_item_seconds: "Seconds on the map with the item",
  support_item_empty: "Seconds with the item empty", support_item_empty_share: "Time with the item empty",
  support_item_wards: "Wards from the support item", support_item_trips: "Returns to base", support_item_charges_wasted: "Wards unused on recall",
  support_item_wasted_per_trip: "Wards unused per recall", control_bought: "Control ward buy events",
  control_placed: "Control wards placed", control_placed_10: "Control wards per 10 min", sweeps_10: "Sweeps per 10 min",
};
const label = (key: string) => LABELS[key] ?? key.replaceAll("_", " ");
export const ROLE_NAMES: Record<string, string> = { JUNGLE: "Jungle", TOP: "Top", MIDDLE: "Mid", BOTTOM: "ADC", UTILITY: "Support" };
const KIND_COLORS: Record<string, string> = {
  death: palette.red, camps: palette.gold, fog: categorical.violet, fight: categorical.orange, objective: palette.blue, swing: categorical.pink,
  flash: categorical.yellow, back: palette.gray, roam: categorical.teal, opening: categorical.indigo, play: categorical.sky, pair: categorical.amber,
  ward: categorical.mint, setup: categorical.periwinkle, trade: categorical.fuchsia, damage: categorical.rose, dive: categorical.tangerine, tower: categorical.cornflower,
  plate: categorical.yellow,
};

/** The finished replay analysis: a coach dashboard with each match's moments on the map. */
export function PremiumResult({ result, review: rawReview }: { result: PremiumData; review: Review | null }) {
  const { summary, games, missing } = result;
  const review = isCoachReview(rawReview) ? rawReview : null;
  const index = indexMoments(games);
  const patterns = summary.patterns ?? [];
  const first = patterns.find((p) => p.tone === "bad")?.moments[0] ?? null;
  const [selected, setSelected] = useState<string | null>(first && index.has(first) ? first : null);
  const [openGame, setOpenGame] = useState<string | null>(games[0]?.match_id ?? null);
  const explorer = useRef<HTMLElement>(null);

  if (index.size === 0) {
    return (
      <p className="text-sm text-muted">
        This analysis was made before the coach dashboard existed. Run it again to see every moment of your games on the map.
      </p>
    );
  }

  /** Show a moment: opens its match, chooses it and takes the page to it. */
  function focus(key: string) {
    const found = index.get(key);
    if (!found) return;
    setSelected(key);
    setOpenGame(found.game.match_id);
    // after painting, which is when the card is already open and in place
    window.setTimeout(() => {
      const card = document.getElementById(gameCardId(found.game.match_id));
      (card ?? explorer.current)?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 0);
  }

  return (
    <div className="flex flex-col gap-6">
      <CoachHeader result={result} review={review} patterns={patterns} />
      <Missing missing={missing} analysed={games.length} />

      <Section
        title="What decides your games"
        description={`Each card compares you with the players of your tier and role who win and who lose. Click one to see those moments on the map.${
          summary.role_games !== undefined && summary.role_games < summary.games
            ? ` From your ${summary.role_games} ${ROLE_NAMES[summary.role] ?? summary.role} games.`
            : ""
        }`}
      >
        <PatternCards patterns={patterns} index={index} onFocus={focus} />
      </Section>

      <section ref={explorer} className="scroll-mt-4">
        <Section
          title="Game by game, moment by moment"
          description="Each game with its scoreboard, the rating of what you did in it and every moment on the map, with the exact in-game minute to rewatch it."
        >
          <div className="flex flex-col gap-3">
            {games.map((game, i) => (
              <GameCard
                key={game.match_id}
                game={game}
                gameIndex={i}
                moments={gameMoments(index, game.match_id)}
                review={review}
                open={openGame === game.match_id}
                onToggle={() => setOpenGame(openGame === game.match_id ? null : game.match_id)}
                selected={selected}
                onSelect={setSelected}
              />
            ))}
          </div>
        </Section>
      </section>

      {games.some((g) => g.wards?.length) && (
        <Section
          title="Your vision, ward by ward"
          description="Every ward you placed as support: what it showed, the window you placed it in and what you risked to place it."
        >
          <WardMap games={games} />
        </Section>
      )}

      {review ? (
        <Lessons review={review} index={index} onFocus={focus} />
      ) : (
        <Section title="Moments to rewatch first" description="The costliest moments across your games.">
          <MomentChips keys={topMoments(index)} index={index} onFocus={focus} />
        </Section>
      )}

      {games.length > 1 && (
        <Section title="Your games in numbers" description="How each game went, in the order you played them. W and L under each bar.">
          <Trends result={result} />
        </Section>
      )}

      <Section title="Your numbers against your tier" description="The concepts where winners and losers of your tier and role differ most, and where you stand (higher is better).">
        <DecisiveChart metrics={summary.metrics} />
      </Section>
      {review?.model && <p className="text-xs text-subtle">Review written by {review.model} from the measured data.</p>}
    </div>
  );
}

function topMoments(index: Map<string, Located>, count = 8): string[] {
  return [...index.values()]
    .filter((m) => m.moment.tone === "bad")
    .sort((a, b) => b.moment.severity - a.moment.severity || Math.abs(b.moment.value ?? 0) - Math.abs(a.moment.value ?? 0))
    .slice(0, count)
    .map((m) => m.key);
}

export function Section({
  title,
  description,
  children,
  as: Heading = "h3",
  action,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
  /** The title's level: a match's page hangs its sections directly from the h1. */
  as?: "h2" | "h3";
  /** A control to the right of the title (a match's page: see all of the section's text). */
  action?: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-3 border-t border-line pt-5">
      <div className="flex items-end justify-between gap-3">
        <div>
          <Heading className="text-base font-black text-text">{title}</Heading>
          {description && <p className="mt-0.5 text-xs text-muted">{description}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function CoachHeader({ result, review, patterns }: { result: PremiumData; review: Review | null; patterns: Pattern[] }) {
  const { summary, games } = result;
  const champions = Object.entries(
    games.reduce<Record<string, number>>((acc, g) => ({ ...acc, [g.champion]: (acc[g.champion] ?? 0) + 1 }), {}),
  ).sort((a, b) => b[1] - a[1]);
  const worst = patterns.filter((p) => p.tone === "bad");
  const headline = review?.headline ?? (worst[0] ? `${worst[0].title}: the first thing to fix.` : "Your games, moment by moment.");
  const paragraphs = review ? review.coach_summary.split(/\n\s*\n/) : worst.slice(0, 2).map((p) => p.text);
  return (
    <div className="relative overflow-hidden border border-stat-gold/30 bg-panel-light/40 p-5">
      <p className="microtext text-xs text-stat-gold">Coach review</p>
      <h2 className="mt-1.5 text-lg leading-snug font-black text-text md:text-xl">{headline}</h2>
      <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
        <Chip>
          {summary.games} games · <span className="text-stat-green">{summary.wins}W</span>{" "}
          <span className="text-stat-red">{summary.games - summary.wins}L</span>
        </Chip>
        <Chip>{ROLE_NAMES[summary.role] ?? summary.role}</Chip>
        <Chip>Compared with {summary.tier.charAt(0) + summary.tier.slice(1).toLowerCase()}</Chip>
        {champions.map(([champion, count]) => (
          <Chip key={champion}>
            <ChampionIcon name={champion} size={16} />
            {champion} ×{count}
          </Chip>
        ))}
      </div>
      <div className="mt-4 flex max-w-3xl flex-col gap-2.5 text-sm leading-relaxed text-soft">
        {paragraphs.map((p, i) => (
          <p key={i}>{p}</p>
        ))}
      </div>
      {!review && (
        <p className="mt-3 text-xs text-subtle">
          The written coach review appears here when the analysis runs with Claude enabled; every moment below already explains itself.
        </p>
      )}
    </div>
  );
}

/** The snapshot's matches that couldn't be analysed, grouped by reason: without this only how many were
 * missing and the first reason were visible, and a new build within the same patch looked like matches were simply lost. */
function Missing({ missing, analysed }: { missing: Record<string, string>; analysed: number }) {
  const ids = Object.keys(missing);
  if (ids.length === 0) return null;
  const byReason = new Map<string, string[]>();
  for (const [id, reason] of Object.entries(missing)) byReason.set(reason, [...(byReason.get(reason) ?? []), id]);
  return (
    <details className="border border-line bg-panel-light/40 px-3 py-2 text-xs">
      <summary className="cursor-pointer text-muted">
        <span className="font-bold text-soft">{ids.length}</span> of your {analysed + ids.length} games could not be analysed
      </summary>
      <ul className="mt-2 flex flex-col gap-1.5">
        {[...byReason].map(([reason, games]) => (
          <li key={reason}>
            <p className="text-soft">
              <span className="font-bold text-text tabular-nums">{games.length}</span> · {reason}
            </p>
            <p className="text-xs break-all text-subtle">{games.join(", ")}</p>
          </li>
        ))}
      </ul>
    </details>
  );
}

export function Chip({ children }: { children: React.ReactNode }) {
  return <span className="inline-flex items-center gap-1.5 rounded-full border border-line bg-white/[0.03] px-2.5 py-1 font-bold text-soft">{children}</span>;
}

/** Where the player stands between the average of those who win and that of those who lose in their league and role, if they separate. */
function Meter({ pattern }: { pattern: Pattern }) {
  const ref = pattern.reference;
  const you = pattern.per_game;
  if (!ref || you === undefined || !separates(ref)) return null;
  const values = [ref.winners, ref.losers, you];
  const low = Math.min(...values);
  const high = Math.max(...values);
  const pad = (high - low) * 0.25 || 1;
  const at = (v: number) => `${((v - (low - pad)) / (high - low + 2 * pad)) * 100}%`;
  return (
    <div className="relative mt-7 mb-5 h-1.5 rounded-full bg-white/10" aria-hidden="true">
      <Mark at={at(ref.winners)} color={palette.green} label={`Winners ${formatNumber(ref.winners, 1)}`} below />
      <Mark at={at(ref.losers)} color={palette.red} label={`Losers ${formatNumber(ref.losers, 1)}`} below />
      <span className="absolute top-1/2 size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-ink bg-acid" style={{ left: at(you) }} />
      <span className="absolute -top-5 -translate-x-1/2 text-xs font-black whitespace-nowrap text-acid" style={{ left: at(you) }}>
        You {formatNumber(you, 1)}
      </span>
    </div>
  );
}

/** The vision score (0-100; 50 is the median of their league) and each part with its own percentile. */
function ScoreParts({ score, parts }: { score: number; parts: ScorePart[] }) {
  return (
    <div className="my-3">
      <p className="flex items-baseline gap-2">
        <span className="text-xl leading-none font-black tabular-nums" style={{ color: tone(score) }}>
          {score}
        </span>
        <span className="text-xs text-muted">/ 100 · 50 is your tier&apos;s median</span>
      </p>
      <ul className="mt-2 flex flex-col gap-1.5">
        {parts.map((part) => (
          <li key={part.key} className="grid grid-cols-[minmax(0,1fr)_5rem_1.75rem] items-center gap-2 text-xs">
            <span className="truncate text-soft" title={`You ${formatNumber(part.value, 2)} · tier median ${formatNumber(part.median, 2)}`}>
              {part.label}
              {part.better === "lower" && <span className="text-subtle"> (less is better)</span>}
            </span>
            <span className="relative h-1.5 rounded-full bg-white/10" aria-hidden="true">
              <span className="absolute inset-y-0 left-1/2 w-px bg-line-button" />
              <span className="absolute inset-y-0 left-0 rounded-full" style={{ width: `${part.score}%`, background: tone(part.score) }} />
            </span>
            <span className="text-right text-text tabular-nums">{part.score}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Mark({ at, color, label, below }: { at: string; color: string; label: string; below?: boolean }) {
  return (
    <>
      <span className="absolute top-1/2 h-3 w-0.5 -translate-x-1/2 -translate-y-1/2" style={{ left: at, background: color }} />
      <span className={cn("absolute -translate-x-1/2 text-xs whitespace-nowrap", below ? "top-2.5" : "-top-5")} style={{ left: at, color }}>
        {label}
      </span>
    </>
  );
}

export function PatternCards({
  patterns,
  index,
  onFocus,
  columns = "md:grid-cols-2 xl:grid-cols-3",
  isOpen,
  onToggle,
  titleAs: Title = "h4",
}: {
  patterns: Pattern[];
  index: Map<string, Located>;
  onFocus: (key: string) => void;
  /** The grid's columns: on a match's page, with the map fixed alongside, the reading is narrower. */
  columns?: string;
  /** With onToggle, each card's text is trimmed to two lines until it is requested in full. */
  isOpen?: (kind: string) => boolean;
  onToggle?: (kind: string) => void;
  /** The level of each card's title: it hangs from the section that contains them. */
  titleAs?: "h3" | "h4";
}) {
  if (patterns.length === 0) return <p className="text-sm text-muted">Not enough games to see patterns yet.</p>;
  return (
    <div className={cn("grid gap-3", columns)}>
      {patterns.map((pattern) => {
        const Icon = pattern.kind in KIND_ICONS ? KIND_ICONS[pattern.kind as MomentKind] : Crosshair;
        const firstKey = pattern.moments.find((k) => index.has(k));
        const full = !onToggle || isOpen?.(pattern.kind);
        return (
          <article
            key={pattern.kind}
            className="flex flex-col border border-line bg-panel-light/60 p-4"
            style={{ borderTopColor: TONE_COLOR[pattern.tone], borderTopWidth: 3 }}
          >
            <header className="flex items-center gap-2">
              <Icon className="size-4" style={{ color: TONE_COLOR[pattern.tone] }} aria-hidden="true" />
              <Title className="text-sm font-black text-text">{pattern.title}</Title>
              <span
                className={cn(
                  "ml-auto rounded-full px-2 py-0.5 text-xs font-black uppercase",
                  pattern.tone === "bad" && "bg-stat-red/15 text-stat-red",
                  pattern.tone === "good" && "bg-stat-green/15 text-stat-green",
                  pattern.tone === "neutral" && "bg-white/[0.06] text-muted",
                )}
              >
                {pattern.tone === "bad" ? "Costing you" : pattern.tone === "good" ? "Strength" : "Watch"}
              </span>
            </header>
            {pattern.score !== undefined && pattern.parts ? <ScoreParts score={pattern.score} parts={pattern.parts} /> : <Meter pattern={pattern} />}
            <p className={cn("text-sm leading-relaxed text-soft", !full && "line-clamp-2")}>{pattern.text}</p>
            {pattern.gold ? <p className="mt-2 text-xs font-bold text-stat-red tabular-nums">{formatSigned(pattern.gold, 0)} gold in total</p> : null}
            <div className="mt-auto flex items-center justify-between gap-3 pt-3">
              {firstKey ? (
                <button
                  type="button"
                  onClick={() => onFocus(firstKey)}
                  className="-my-1.5 inline-flex cursor-pointer items-center gap-1.5 py-1.5 text-xs font-bold text-acid hover:underline"
                >
                  See {pattern.moments.filter((k) => index.has(k)).length > 1 ? "these moments" : "this moment"} on the map
                  <ArrowRight className="size-3.5" aria-hidden="true" />
                </button>
              ) : (
                <span />
              )}
              {onToggle && (
                <button
                  type="button"
                  aria-expanded={full}
                  onClick={() => onToggle(pattern.kind)}
                  className="-my-1.5 cursor-pointer py-1.5 text-xs font-bold text-muted hover:text-text"
                >
                  {full ? "Less" : "More"}
                </button>
              )}
            </div>
          </article>
        );
      })}
    </div>
  );
}

/** `single`: a single match's page, where the champion and «G1» of each card say nothing. */
export function MomentChips({
  keys,
  index,
  onFocus,
  single = false,
}: {
  keys: string[];
  index: Map<string, Located>;
  onFocus: (key: string) => void;
  single?: boolean;
}) {
  const found = keys.map((k) => index.get(k)).filter((m): m is Located => m !== undefined);
  if (found.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      {found.map((m) => {
        const Icon = KIND_ICONS[m.moment.kind];
        return (
          <button
            key={m.key}
            type="button"
            onClick={() => onFocus(m.key)}
            className="inline-flex cursor-pointer items-center gap-1.5 rounded-full border border-line px-2.5 py-1 text-xs text-soft transition hover:border-acid/60 hover:text-text"
          >
            {!single && <ChampionIcon name={m.game.champion} size={16} />}
            {!single && <span className={m.game.win ? "text-stat-green" : "text-stat-red"}>G{m.gameIndex + 1}</span>}
            <Icon className="size-3.5" style={{ color: TONE_COLOR[m.moment.tone] }} aria-hidden="true" />
            <span className="font-bold tabular-nums">{m.moment.clock}</span>
            <span className="max-w-44 truncate">{m.moment.title}</span>
          </button>
        );
      })}
    </div>
  );
}

function Lessons({ review, index, onFocus }: { review: Review; index: Map<string, Located>; onFocus: (key: string) => void }) {
  return (
    <>
      <LessonList review={review} index={index} onFocus={onFocus} />
      <div className="grid gap-4 md:grid-cols-2">
        <Strengths review={review} index={index} onFocus={onFocus} />
        <NextGame review={review} />
      </div>
    </>
  );
}

type LessonProps = { review: Review; index: Map<string, Located>; onFocus: (key: string) => void };

function LessonList({ review, index, onFocus }: LessonProps) {
  return (
    <Section title="What to work on" description="From the coach, most important first. Each lesson links to the moments that show it.">
      <ol className="flex flex-col gap-3">
        {review.lessons.map((lesson, i) => (
          <li key={lesson.title} className="border border-line bg-panel-light/60 p-4">
            <p className="flex items-center gap-3 text-base font-black text-text">
              <span className="grid size-7 shrink-0 place-items-center rounded-full bg-stat-gold/15 text-sm font-black text-stat-gold">{i + 1}</span>
              {lesson.title}
            </p>
            <p className="mt-2 text-sm leading-relaxed text-soft">{lesson.why}</p>
            <p className="mt-2 flex gap-2 text-sm text-text">
              <Lightbulb className="mt-0.5 size-4 shrink-0 text-acid" aria-hidden="true" />
              {lesson.fix}
            </p>
            <div className="mt-3">
              <MomentChips keys={lesson.moments} index={index} onFocus={onFocus} />
            </div>
          </li>
        ))}
      </ol>
    </Section>
  );
}

function Strengths({ review, index, onFocus }: LessonProps) {
  return (
    <Section title="What you already do well">
      <ul className="flex flex-col gap-2">
        {review.strengths.map((s) => (
          <li key={s.title} className="border border-stat-green/25 bg-stat-green/[0.04] p-3">
            <p className="text-sm font-bold text-text">{s.title}</p>
            <p className="mt-0.5 text-sm text-soft">{s.detail}</p>
            <div className="mt-2">
              <MomentChips keys={s.moments} index={index} onFocus={onFocus} />
            </div>
          </li>
        ))}
      </ul>
    </Section>
  );
}

export function NextGame({ review, as }: { review: Review; as?: "h2" | "h3" }) {
  return (
    <Section as={as} title="For your next game">
      <ul className="flex flex-col gap-2">
        {review.next_game.map((tip) => (
          <li key={tip} className="flex gap-2.5 text-sm text-soft">
            <CircleCheck className="mt-0.5 size-4 shrink-0 text-acid" aria-hidden="true" />
            {tip}
          </li>
        ))}
      </ul>
    </Section>
  );
}

const chartTooltip = { contentStyle: { background: palette.surface2, border: `1px solid ${palette.border}`, fontSize: 12 } };

function Trends({ result }: { result: PremiumData }) {
  const band = (row: TrendRow, from: number, to: number) =>
    row.rating !== null && row.rating >= from && row.rating < to ? row.rating : null;
  type Row = TrendRow & { tick: string; ahead: number | null; behind: number | null };
  const rows: Row[] = trendRows(result.games).map((row) => ({
    ...row,
    tick: `${row.label} ${row.win ? "W" : "L"}`,
    ahead: row.gold14 !== null && row.gold14 > 0 ? row.gold14 : null,
    behind: row.gold14 !== null && row.gold14 < 0 ? row.gold14 : null,
    ratingLow: band(row, 0, 45),
    ratingMid: band(row, 45, 75),
    ratingHigh: band(row, 75, 101),
  }));
  const kinds = Object.keys(KIND_COLORS).filter((k) => rows.some((r) => typeof r[k] === "number"));
  const jungle = result.summary.role === "JUNGLE";
  const support = result.summary.role === "UTILITY";
  const laner = ["TOP", "MIDDLE", "BOTTOM"].includes(result.summary.role);
  const has = (key: keyof TrendRow) => rows.some((r) => typeof r[key] === "number");
  const axis = { stroke: palette.muted, fontSize: 11 };
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <Chart title="Gold vs your lane opponent at 14:00" note="Green: ahead. Red: behind.">
        <BarChart data={rows} margin={{ left: -8, right: 8, top: 4, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke={palette.grid} />
          <XAxis dataKey="tick" {...axis} />
          <YAxis {...axis} tickFormatter={(v: number) => `${v > 0 ? "+" : ""}${v}`} />
          <Tooltip {...chartTooltip} formatter={(v) => formatSigned(Number(v), 0)} />
          <Bar dataKey="ahead" name="Ahead" stackId="g" fill={palette.green} radius={[3, 3, 0, 0]} />
          <Bar dataKey="behind" name="Behind" stackId="g" fill={palette.red} radius={[0, 0, 3, 3]} />
        </BarChart>
      </Chart>
      {has("rating") && (
        <Chart
          title="Your rating, game by game"
          note="1 to 100, from what your own moments added and cost, against the players of your tier and role. Winning isn't part of it."
        >
          <BarChart data={rows} margin={{ left: -16, right: 8, top: 4, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke={palette.grid} />
            <XAxis dataKey="tick" {...axis} />
            <YAxis domain={[0, 100]} ticks={[0, 50, 100]} {...axis} />
            <Tooltip {...chartTooltip} />
            <ReferenceLine y={62.5} stroke={palette.muted} strokeDasharray="4 4" />
            {/* one bar per stretch (only one has a value in each match): that way each grade gets its own colour */}
            {([["ratingLow", palette.red], ["ratingMid", palette.gold], ["ratingHigh", palette.green]] as const).map(
              ([key, color]) => (
                <Bar key={key} dataKey={key} name="Rating" stackId="r" fill={color} radius={[3, 3, 0, 0]} />
              ),
            )}
          </BarChart>
        </Chart>
      )}
      <Chart title="Mistakes per game" note="Each colour is a kind of mistake from the map above.">
        <BarChart data={rows} margin={{ left: -16, right: 8, top: 4, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke={palette.grid} />
          <XAxis dataKey="tick" {...axis} />
          <YAxis allowDecimals={false} {...axis} />
          <Tooltip {...chartTooltip} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          {kinds.map((k) => (
            <Bar key={k} dataKey={k} name={KINDS[k as MomentKind]} stackId="m" fill={KIND_COLORS[k]} />
          ))}
        </BarChart>
      </Chart>
      <Chart title="Deaths before and after 14:00">
        <BarChart data={rows} margin={{ left: -16, right: 8, top: 4, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke={palette.grid} />
          <XAxis dataKey="tick" {...axis} />
          <YAxis allowDecimals={false} {...axis} />
          <Tooltip {...chartTooltip} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Bar dataKey="deathsEarly" name="Before 14:00" stackId="d" fill={palette.gold} />
          <Bar dataKey="deathsLate" name="After 14:00" stackId="d" fill={palette.red} radius={[3, 3, 0, 0]} />
        </BarChart>
      </Chart>
      {jungle && (
        <Chart
          title="Jungle gold lost and taken before 14:00"
          note="Your small camps left standing or stolen by their jungler, and the camps you took from them, at their real value."
        >
          <BarChart data={rows} margin={{ left: -8, right: 8, top: 4, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke={palette.grid} />
            <XAxis dataKey="tick" {...axis} />
            <YAxis {...axis} />
            <Tooltip {...chartTooltip} formatter={(v) => `${formatNumber(Number(v), 0)} gold`} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Bar dataKey="campGold" name="Left standing" stackId="lost" fill={palette.gold} />
            <Bar dataKey="stolenGold" name="Stolen by their jungler" stackId="lost" fill={palette.red} radius={[3, 3, 0, 0]} />
            <Bar dataKey="invadedGold" name="Taken from their jungle" fill={palette.green} radius={[3, 3, 0, 0]} />
          </BarChart>
        </Chart>
      )}
      {jungle && (
        <Chart
          title="Map openings before 14:00: with or against the high-elo read"
          note="Times you left base with a clear best side: the side Challenger and Grandmaster junglers take, or the other."
        >
          <BarChart data={rows} margin={{ left: -16, right: 8, top: 4, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke={palette.grid} />
            <XAxis dataKey="tick" {...axis} />
            <YAxis allowDecimals={false} {...axis} />
            <Tooltip {...chartTooltip} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Bar dataKey="openingsMatched" name="Same read" stackId="o" fill={palette.green} />
            <Bar dataKey="openingsAgainst" name="Against the read" stackId="o" fill={palette.red} radius={[3, 3, 0, 0]} />
          </BarChart>
        </Chart>
      )}
      {jungle && (
        <Chart title="Show-ups that got nothing, 2:00–14:00" note="Times the enemy saw you without a kill, a summoner or a laner sent back.">
          <BarChart data={rows} margin={{ left: -16, right: 8, top: 4, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke={palette.grid} />
            <XAxis dataKey="tick" {...axis} />
            <YAxis allowDecimals={false} {...axis} />
            <Tooltip {...chartTooltip} />
            <Bar dataKey="showupsNothing" name="Show-ups for nothing" fill={categorical.violet} radius={[3, 3, 0, 0]} />
          </BarChart>
        </Chart>
      )}
      {jungle && has("playsGood") && (
        <Chart
          title="Plays made with camps up, before 14:00"
          note="Each play against the farm it delayed, counting everyone involved on both teams."
        >
          <BarChart data={rows} margin={{ left: -16, right: 8, top: 4, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke={palette.grid} />
            <XAxis dataKey="tick" {...axis} />
            <YAxis allowDecimals={false} {...axis} />
            <Tooltip {...chartTooltip} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Bar dataKey="playsGood" name="Paid for the camps" stackId="p" fill={palette.green} />
            <Bar dataKey="playsEven" name="Broke even" stackId="p" fill={palette.gold} />
            <Bar dataKey="playsBad" name="Cost more than it gave" stackId="p" fill={palette.red} radius={[3, 3, 0, 0]} />
          </BarChart>
        </Chart>
      )}
      {support && has("openingsMid") && (
        <Chart
          title="Leaving base before 14:00: through mid or straight to bot"
          note="Opening through mid renews vision and pressures their mid laner before you reach your ADC."
        >
          <BarChart data={rows} margin={{ left: -16, right: 8, top: 4, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke={palette.grid} />
            <XAxis dataKey="tick" {...axis} />
            <YAxis allowDecimals={false} {...axis} />
            <Tooltip {...chartTooltip} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Bar dataKey="openingsMid" name="Through mid" stackId="o" fill={palette.blue} />
            <Bar dataKey="openingsBot" name="Straight to bot" stackId="o" fill={palette.gray} radius={[3, 3, 0, 0]} />
          </BarChart>
        </Chart>
      )}
      {support && has("wardsUseful") && (
        <Chart title="Wards placed, and how many showed someone" note="A ward counts when it revealed an enemy nobody on your team was seeing.">
          <BarChart data={rows} margin={{ left: -16, right: 8, top: 4, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke={palette.grid} />
            <XAxis dataKey="tick" {...axis} />
            <YAxis allowDecimals={false} {...axis} />
            <Tooltip {...chartTooltip} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Bar dataKey="wardsUseful" name="Revealed someone" stackId="w" fill={palette.green} />
            <Bar dataKey="wardsSilent" name="Saw nobody" stackId="w" fill={palette.gray} radius={[3, 3, 0, 0]} />
            <Bar dataKey="controlWards" name="Control wards" fill={categorical.pink} radius={[3, 3, 0, 0]} />
          </BarChart>
        </Chart>
      )}
      {support && has("emptySeconds") && (
        <Chart title="Seconds on the map with the support item empty" note="Its wards only refill in the shop.">
          <BarChart data={rows} margin={{ left: -8, right: 8, top: 4, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke={palette.grid} />
            <XAxis dataKey="tick" {...axis} />
            <YAxis {...axis} />
            <Tooltip {...chartTooltip} formatter={(v) => `${formatNumber(Number(v), 0)} s`} />
            <Bar dataKey="emptySeconds" name="Item empty" fill={palette.gold} radius={[3, 3, 0, 0]} />
          </BarChart>
        </Chart>
      )}
      {(jungle || support) && has("setupsPrepared") && (
        <Chart
          title="Objectives after 14:00: there before they spawn, or away for nothing"
          note="Where you were in the 45 s before each dragon, Baron and Herald spawned."
        >
          <BarChart data={rows} margin={{ left: -16, right: 8, top: 4, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke={palette.grid} />
            <XAxis dataKey="tick" {...axis} />
            <YAxis allowDecimals={false} {...axis} />
            <Tooltip {...chartTooltip} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Bar dataKey="setupsPrepared" name="In the area" stackId="s" fill={palette.green} />
            <Bar dataKey="setupsAway" name="Elsewhere, for nothing" stackId="s" fill={palette.red} radius={[3, 3, 0, 0]} />
          </BarChart>
        </Chart>
      )}
      {has("recallsGood") && (
        <Chart
          title="Recalls, by the wave you left behind"
          note="Judged by where the wave was when you pressed it: crashed into their tower or collected under yours costs nothing, a freeze or a rolling wave with no cannon costs all of it."
        >
          <BarChart data={rows} margin={{ left: -16, right: 8, top: 4, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke={palette.grid} />
            <XAxis dataKey="tick" {...axis} />
            <YAxis allowDecimals={false} {...axis} />
            <Tooltip {...chartTooltip} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Bar dataKey="recallsGood" name="On the wave" stackId="rc" fill={palette.green} />
            <Bar dataKey="recallsBad" name="Leaving it behind" stackId="rc" fill={palette.red} radius={[3, 3, 0, 0]} />
          </BarChart>
        </Chart>
      )}
      {has("fightDamage") && (
        <Chart
          title="Your damage in fights"
          note="What you dealt against what the average player on your side dealt in the same fight. An ADC usually does 1.3x."
        >
          <BarChart data={rows} margin={{ left: -16, right: 8, top: 4, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke={palette.grid} />
            <XAxis dataKey="tick" {...axis} />
            <YAxis {...axis} tickFormatter={(v: number) => `${v}x`} />
            <Tooltip {...chartTooltip} formatter={(v) => `${formatNumber(Number(v), 2)}x`} />
            <ReferenceLine y={1.33} stroke={palette.muted} strokeDasharray="4 4" />
            <Bar dataKey="fightDamage" name="Damage vs your side's average" fill={palette.gold} radius={[3, 3, 0, 0]} />
          </BarChart>
        </Chart>
      )}
      {has("tradesWon") && (
        <Chart title="Trades in lane" note="Only the ones that decided something: health, summoners, the wave and who could reset after.">
          <BarChart data={rows} margin={{ left: -16, right: 8, top: 4, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke={palette.grid} />
            <XAxis dataKey="tick" {...axis} />
            <YAxis allowDecimals={false} {...axis} />
            <Tooltip {...chartTooltip} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Bar dataKey="tradesWon" name="Came out ahead" stackId="t" fill={palette.green} />
            <Bar dataKey="tradesLost" name="Came out behind" stackId="t" fill={palette.red} radius={[3, 3, 0, 0]} />
          </BarChart>
        </Chart>
      )}
      {has("platesLane") && (
        <Chart
          title="Turret plates in your lane"
          note="Before 14:00, both outer turrets. A plate is 160 gold shared by whoever is next to it, and every plate of difference is worth 6.5 points of win rate in mid, 6.0 in bot and 4.6 in top."
        >
          <BarChart data={rows} margin={{ left: -16, right: 8, top: 4, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke={palette.grid} />
            <XAxis dataKey="tick" {...axis} />
            <YAxis allowDecimals={false} {...axis} />
            <Tooltip {...chartTooltip} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Bar dataKey="platesLane" name="Your lane took" stackId="p" fill={palette.green} />
            <Bar dataKey="platesAgainst" name="They took off you" stackId="p" fill={palette.red} radius={[3, 3, 0, 0]} />
          </BarChart>
        </Chart>
      )}
      {laner && (
        <Chart title="Seconds in enemy territory without knowing where their jungler is" note="Until 14:00.">
          <BarChart data={rows} margin={{ left: -8, right: 8, top: 4, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke={palette.grid} />
            <XAxis dataKey="tick" {...axis} />
            <YAxis {...axis} />
            <Tooltip {...chartTooltip} />
            <Bar dataKey="blind" name="Seconds blind" fill={categorical.violet} radius={[3, 3, 0, 0]} />
          </BarChart>
        </Chart>
      )}
    </div>
  );
}

function Chart({ title, note, children }: { title: string; note?: string; children: React.ReactElement }) {
  return (
    <figure className="flex flex-col gap-2 border border-line p-3">
      <figcaption>
        <p className="text-sm font-bold text-text">{title}</p>
        {note && <p className="text-xs text-muted">{note}</p>}
      </figcaption>
      <div className="h-52">
        <ResponsiveContainer width="100%" height="100%">
          {children}
        </ResponsiveContainer>
      </div>
    </figure>
  );
}

/** The percentile set so that higher is better: in what those who win do less of (deaths, health lost…),
 * the player's 90 is bad and here comes out as 10. With no winners/losers, it is left as it is. */
function goodness(metric: Metric): number {
  if (metric.winners === null || metric.losers === null) return metric.percentile;
  return metric.winners >= metric.losers ? metric.percentile : 100 - metric.percentile;
}

const tone = (score: number) => (score >= 65 ? palette.green : score < 35 ? palette.red : palette.gray);

const numbersLine = (m: Metric) =>
  `You ${formatNumber(m.value, 1)} · tier median ${formatNumber(m.median ?? 0, 1)} · winners ${formatNumber(m.winners ?? 0, 1)}, losers ${formatNumber(m.losers ?? 0, 1)}`;

/** The concepts that most separate those who win from those who lose in their league and role, with where the player stands. */
export function DecisiveChart({
  metrics,
  columns = "md:grid-cols-2",
  detail = true,
}: {
  metrics: Record<string, Metric>;
  columns?: string;
  /** Without it, each row's line of figures appears only on hover (a match's page requests it with the text). */
  detail?: boolean;
}) {
  const rows = Object.entries(metrics)
    .filter(([, m]) => m.winners !== null && m.losers !== null)
    .map(([key, m]) => ({
      key,
      name: label(key),
      score: Math.round(goodness(m)),
      gap: Math.abs((m.winners ?? 0) - (m.losers ?? 0)) / Math.max(Math.abs(m.median ?? 0), 1),
      m,
    }))
    .sort((a, b) => b.gap - a.gap)
    .slice(0, 10);
  // bars from 0 to 100 in HTML: no chart library is needed, and they read the same with a screen reader
  return (
    <ul className={cn("grid gap-x-8 gap-y-2.5", columns)}>
      {rows.map((row) => (
        <li key={row.key} className="grid grid-cols-[minmax(0,13rem)_1fr_3rem] items-center gap-3 text-xs">
          <span className="truncate text-soft" title={detail ? row.name : `${row.name}: ${numbersLine(row.m)}`}>
            {row.name}
          </span>
          <span className="relative h-2.5 rounded-full bg-panel-light" aria-hidden="true">
            <span className="absolute inset-y-0 left-1/2 w-px bg-line-button" />
            <span className="absolute inset-y-0 left-0 rounded-full" style={{ width: `${row.score}%`, background: tone(row.score) }} />
          </span>
          <span className="text-right text-text tabular-nums">{row.score}</span>
          {detail && <span className="col-span-3 -mt-1.5 text-xs text-muted">{numbersLine(row.m)}</span>}
        </li>
      ))}
    </ul>
  );
}
