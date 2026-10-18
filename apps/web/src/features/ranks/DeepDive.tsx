import type { ReactNode } from "react";
import { useSearchParams } from "react-router";

import { RankEmblem } from "@/components/player/PlayerBits";
import { Card, CardHeader } from "@/components/ui/Card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/Overlay";
import { cn } from "@/lib/cn";
import { formatPercent } from "@/lib/format";
import { palette } from "@/lib/palette";

import {
  formatValue,
  isSignificant,
  type Metric,
  relativeChange,
  type Role,
  ROLES,
  stats,
  TIER_NAMES,
  TIER_SHORT,
  tierValues,
  winSplit,
  Z,
} from "./rankStats";

// ── Metrics ───────────────────────────────────────────────────────────────────
// Each one points to its key in stats.json. `ALL_METRICS` gathers them all for the test.

const r = (role: Role, key: string, label: string, extra: Partial<Metric> = {}): Metric => ({ ref: { role, key }, label, ...extra });
const s = (table: string, key: string, label: string, extra: Partial<Metric> = {}): Metric => ({ ref: { table, key }, label, ...extra });
const pct = { unit: "%" } as const;

interface Finding {
  metric: Metric;
  title: string;
  body: ReactNode;
}

const FINDINGS: Finding[] = [
  {
    metric: s("backs", "cs_lost_per_back", "Minions lost per recall"),
    title: "Cleaner recalls",
    body: "Every tier recalls on the same waves: about a third before the cannon wave, a third after it, a third on a normal wave. What changes is the state they leave the lane in. Challenger players lose 26% fewer minions per recall.",
  },
  {
    metric: s("prio", "crash_with_no_use_at_all", "Crashes with no follow-up", pct),
    title: "Prio gets used",
    body: "Crashing a wave buys a few free seconds. In Gold, 1 crash in 11 is followed by nothing at all. In Challenger, it's 1 in 20.",
  },
  {
    metric: s("prio", "crash_rotates_to_another_lane", "Crashes followed by a rotation", pct),
    title: "Prio becomes map pressure",
    body: "After crashing a wave, Challenger players rotate to another lane about two and a half times as often. Lower tiers spend that time in their own lane: recalling, hiding or harassing.",
  },
  {
    metric: r("UTILITY", "departures", "Support roams before 14:00"),
    title: "Supports play the map",
    body: "Supports leave lane twice as often during the laning phase, usually without pushing first. They ward almost 50% more, and farm and deal less damage.",
  },
  {
    metric: r("JUNGLE", "idle_delay", "Idle camp-seconds before 14:00", { unit: "s", digits: 0 }),
    title: "Junglers keep camps cycling",
    body: "Small camps left alive past their respawn cost a Gold jungler 5.3 clears by 14:00, and a Challenger jungler 3.5. Top junglers show up in lanes more often, but less often with camps up (68% → 54% of appearances).",
  },
  {
    metric: r("MIDDLE", "wards_killed", "Wards cleared by mid, per 10 min"),
    title: "Denying vision",
    body: "Mid laners clear almost twice as many wards. Clearing enemy vision rises in every role (+36% to +104%). Placing wards barely changes outside support.",
  },
  {
    metric: r("BOTTOM", "finishes_missed", "ADC missed last hits by 14:00"),
    title: "Fewer missed last hits",
    body: "Minions from their lane that die within reach (700 units) without the laner taking the gold. They fall by about 40% from Gold to Challenger in every lane, tier after tier. Winner and loser of the same lane miss about as many: it climbs, it doesn't decide a game.",
  },
  {
    metric: s("setups", "share_of_the_jungler_support_duo_s_work", "Setup work done by the jungle–support duo", pct),
    title: "Objectives become a duo job",
    body: "The jungle–support duo does more and more of the work before each objective, with 90% more control wards around it. Mid, top and ADC prepare 16–26% less.",
  },
];

const MISTAKES: Metric[] = [
  r("BOTTOM", "finishes_missed", "ADC: missed last hits by 14:00"),
  r("MIDDLE", "finishes_missed", "Mid: missed last hits by 14:00"),
  s("backs", "cs_lost_per_back", "Minions lost per recall"),
  s("clashes", "cs_lost_per_clash", "Minions lost per crashed wave"),
  r("MIDDLE", "prio_cs_lost", "Mid: minions lost around own crashes"),
  r("JUNGLE", "idle_clears_lost", "Jungle: clears lost to idle camps"),
  s("jungler_windows", "with_camps_left_standing", "Jungler shows up with camps idle", pct),
  s("departures", "cs_lost_per_departure", "Minions lost per roam"),
  r("BOTTOM", "sidelane_turns", "ADC alone in a side lane, per 10 min"),
  s("prio", "crash_with_no_use_at_all", "Crashes with no follow-up", pct),
  r("JUNGLE", "recall_seconds_above", "Jungle: seconds holding 1,500+ gold, per 10 min"),
  s("sidelanes", "dies_on_the_turn", "Deaths per side-lane turn", pct),
  s("side_balance", "sidelanes_abandoned_per_10_min_from_14", "Side lanes abandoned, per 10 min"),
  r("JUNGLE", "deaths", "Jungle deaths per 10 min"),
];

const CLIMBERS: Metric[] = [
  r("UTILITY", "departures", "Support roams before 14:00"),
  r("UTILITY", "wards", "Support wards per 10 min"),
  s("departures", "lane_departures_per_game", "Roams per game before 14:00"),
  s("prio", "crash_rotates_to_another_lane", "Crash → rotate to another lane", pct),
  s("prio", "crash_several_uses", "Crash → two or more follow-ups", pct),
  s("setups", "share_of_the_jungler_support_duo_s_work", "Objective setup by jungle + support", pct),
  r("BOTTOM", "wards_killed", "ADC wards cleared per 10 min"),
  s("setups", "control_wards_in_the_area", "Control wards per objective"),
  s("trades", "abilities_per_champion_and_trade", "Abilities per trade"),
  r("MIDDLE", "vision_seconds_of_info", "Mid: seconds of info from own wards"),
  s("prio", "crash_vision", "Crash → ward", pct),
  s("departures", "a_deep_ward", "Roam → deep ward", pct),
  s("wards", "wards_on_the_rival_half_of_the_map", "Wards on the enemy half of the map", pct),
  s("recalls", "cancelled_with_a_rival_on_screen_per_player_and_game", "Recalls cancelled with an enemy on screen"),
];

const UNCHANGED: Metric[] = [
  s("backs", "backs_with_the_cannon_on_the_way", "Recalls with the cannon wave coming", pct),
  s("trades", "damage_per_champion_and_trade", "Damage per champion per trade", { digits: 0 }),
  s("trades", "ends_up_dying", "Trades that end in a death", pct),
  s("departures", "gets_something", "Roams that get something", pct),
  s("jungler_windows", "shows_up_and_gets_something", "Jungle appearances that get something", pct),
  s("sidelanes", "rivals_not_located_while_pushing", "Enemies unaccounted for while side-laning"),
  s("punishments", "the_punished_one_dies", "Punished facechecks that end in a death", pct),
  r("BOTTOM", "blind_rival_side", "ADC: laning time on the enemy side", pct),
  r("TOP", "blind_rival_side", "Top: laning time on the enemy side", pct),
];

const FARMING: Metric[] = [
  r("TOP", "cs", "Top CS per 10 min"),
  r("MIDDLE", "cs", "Mid CS per 10 min"),
  r("BOTTOM", "cs", "ADC CS per 10 min"),
  r("JUNGLE", "cs_jungle", "Jungle camps per 10 min"),
  r("TOP", "lane_cs", "Top CS at 14:00", { digits: 0 }),
  r("MIDDLE", "lane_cs", "Mid CS at 14:00", { digits: 0 }),
  r("BOTTOM", "lane_cs", "ADC CS at 14:00", { digits: 0 }),
];

const RECALLS: Metric[] = [
  r("TOP", "backs", "Top recalls before 14:00"),
  r("MIDDLE", "backs", "Mid recalls before 14:00"),
  r("BOTTOM", "backs", "ADC recalls before 14:00"),
  r("UTILITY", "backs", "Support recalls before 14:00"),
  s("backs", "cs_lost_per_back", "Minions lost per recall"),
  s("backs", "backs_with_the_cannon_on_the_way", "…with the cannon wave coming", pct),
  s("backs", "backs_after_the_cannon", "…right after the cannon wave", pct),
  s("backs", "backs_with_a_normal_wave", "…on a normal wave", pct),
  s("backs", "backs_without_clearing_the_wave", "…without clearing the wave", pct),
  s("recalls", "recalls_per_player_and_game", "Recalls started per player, whole game"),
  s("recalls", "cancelled_recalls_per_player_and_game", "…cancelled"),
  s("recalls", "cancelled_with_a_rival_on_screen_per_player_and_game", "…cancelled with an enemy on screen"),
  s("recalls", "recalls_cut_short_by_a_rival_per_player_and_game", "…cut by an enemy hit or CC"),
  s("recalls", "cancelled_recall", "Share cancelled", pct),
];

const PRIO: Metric[] = [
  s("prio", "cs_lost_per_crash", "Minions lost per crash"),
  s("prio", "crash_with_no_use_at_all", "Nothing", pct),
  s("prio", "crash_goes_back_to_base", "Recall", pct),
  s("prio", "crash_rotates_to_another_lane", "Rotate to another lane", pct),
  s("prio", "crash_vision", "Ward", pct),
  s("prio", "crash_goes_into_the_fog", "Disappear into fog", pct),
  s("prio", "crash_harass_under_tower", "Harass under tower", pct),
  s("prio", "crash_several_uses", "Two or more of the above", pct),
];

const LAST_HITS: Metric[] = [
  r("TOP", "finishes_missed", "Top: missed last hits"),
  r("MIDDLE", "finishes_missed", "Mid: missed last hits"),
  r("BOTTOM", "finishes_missed", "ADC: missed last hits"),
  r("TOP", "finishes_hit_rate", "Top: minions taken when in range", pct),
  r("MIDDLE", "finishes_hit_rate", "Mid: minions taken when in range", pct),
  r("BOTTOM", "finishes_hit_rate", "ADC: minions taken when in range", pct),
  r("TOP", "blind_rival_side", "Top: time on the enemy side", pct),
  r("MIDDLE", "blind_rival_side", "Mid: time on the enemy side", pct),
  r("BOTTOM", "blind_rival_side", "ADC: time on the enemy side", pct),
];

const TRADES: Metric[] = [
  s("trades", "seconds_it_lasts", "Seconds per trade", { unit: "s" }),
  s("trades", "damage_per_champion_and_trade", "Damage per champion per trade", { digits: 0 }),
  s("trades", "abilities_per_champion_and_trade", "Abilities per champion per trade"),
  s("trades", "burns_a_summoner", "Trades that burn a summoner", pct),
  s("trades", "ends_up_dying", "Trades that end in a death", pct),
  s("trades", "health_at_the_end", "Health left after a trade", pct),
  r("MIDDLE", "trades_summoners", "Mid: summoners burned in trades"),
];

const ROLE_METRICS: Record<Role, { summary: ReactNode; metrics: Metric[] }> = {
  TOP: {
    summary:
      "Top laners farm 17% more and lose a third fewer minions around their crashes. They leave lane more often, even without pushing first, clear almost twice as many wards and take more side-lane turns. Objective setup moves away from them to the jungle–support duo.",
    metrics: [
      r("TOP", "cs", "CS per 10 min"),
      r("TOP", "finishes_missed", "Missed last hits by 14:00"),
      r("TOP", "blind_rival_side", "Laning time on the enemy side", pct),
      r("TOP", "prio_cs_lost", "Minions lost around own crashes"),
      r("TOP", "prio_unused", "Crashes left unused, per game"),
      r("TOP", "departures", "Roams before 14:00"),
      r("TOP", "departures_no_wave", "…without pushing first"),
      r("TOP", "wards_killed", "Wards cleared per 10 min"),
      r("TOP", "vision_seconds_of_info", "Seconds of info from own wards"),
      r("TOP", "sidelane_turns", "Side-lane turns per 10 min"),
      r("TOP", "setups", "Objective setup actions"),
      r("TOP", "damage_received", "Damage taken per 10 min", { digits: 0 }),
    ],
  },
  JUNGLE: {
    summary:
      "The clearest jungle mistake in low elo is leaving small camps up: Gold junglers waste about 5 clears by 14:00. Challenger junglers show themselves more often, but less often with camps idle. They go back to spend gold sooner, die less and walk into fewer punished facechecks.",
    metrics: [
      r("JUNGLE", "cs_jungle", "Camps per 10 min"),
      r("JUNGLE", "idle_delay", "Idle camp-seconds before 14:00", { unit: "s", digits: 0 }),
      r("JUNGLE", "idle_clears_lost", "Clears lost to idle camps"),
      r("JUNGLE", "idle_gold", "Gold lost to idle camps", { digits: 0 }),
      r("JUNGLE", "jungler_shows_up", "Times seen before 14:00"),
      s("jungler_windows", "with_camps_left_standing", "Seen with camps idle", pct),
      r("JUNGLE", "recall_seconds_above", "Seconds holding 1,500+ gold, per 10 min"),
      r("JUNGLE", "recall_gold_max", "Most gold held at once", { digits: 0 }),
      r("JUNGLE", "deaths", "Deaths per 10 min"),
      r("JUNGLE", "punished", "Punished facechecks per 10 min"),
      r("JUNGLE", "wards_killed", "Wards cleared per 10 min"),
    ],
  },
  MIDDLE: {
    summary:
      "Mid shows the biggest improvement in wave management: minions lost around crashes are cut by almost half. Their wards produce about 60% more information. They also spend more time pushed up without knowing where the enemy jungler is, and still die less.",
    metrics: [
      r("MIDDLE", "cs", "CS per 10 min"),
      r("MIDDLE", "finishes_missed", "Missed last hits by 14:00"),
      r("MIDDLE", "blind_rival_side", "Laning time on the enemy side", pct),
      r("MIDDLE", "prio_cs_lost", "Minions lost around own crashes"),
      r("MIDDLE", "backs", "Recalls before 14:00"),
      r("MIDDLE", "departures", "Roams before 14:00"),
      r("MIDDLE", "vision_seconds_of_info", "Seconds of info from own wards"),
      r("MIDDLE", "wards_killed", "Wards cleared per 10 min"),
      r("MIDDLE", "trades_summoners", "Summoners burned in trades"),
      r("MIDDLE", "blind_overextend", "Seconds overextended with the jungler unseen", { unit: "s" }),
      r("MIDDLE", "setups", "Objective setup actions"),
    ],
  },
  BOTTOM: {
    summary:
      "ADCs farm 21% more and clear twice as many wards. In high elo they stop side-laning alone (about a third fewer turns, a third fewer deaths there). They leave lane more often during laning instead (probably following their support) and pay for it in minions.",
    metrics: [
      r("BOTTOM", "cs", "CS per 10 min"),
      r("BOTTOM", "lane_cs", "CS at 14:00", { digits: 0 }),
      r("BOTTOM", "finishes_missed", "Missed last hits by 14:00"),
      r("BOTTOM", "blind_rival_side", "Laning time on the enemy side", pct),
      r("BOTTOM", "wards_killed", "Wards cleared per 10 min"),
      r("BOTTOM", "backs", "Recalls before 14:00"),
      r("BOTTOM", "departures", "Roams before 14:00"),
      r("BOTTOM", "departures_no_wave", "…without pushing first"),
      r("BOTTOM", "departures_cs_lost", "Minions lost to roams"),
      r("BOTTOM", "sidelane_turns", "Side-lane turns per 10 min"),
      r("BOTTOM", "sidelane_deaths", "Side-lane deaths per 10 min"),
      r("BOTTOM", "punishments", "Facechecks punished per 10 min"),
    ],
  },
  UTILITY: {
    summary:
      "Support is the role that changes most. The Challenger support roams twice as often, wards almost 50% more and does a larger share of objective setup. They stop acting as a second carry: less CS and less damage. They also die with their ward charges already used, which is what makes a support death cheap.",
    metrics: [
      r("UTILITY", "departures", "Roams before 14:00"),
      r("UTILITY", "departures_no_wave", "…without pushing first"),
      r("UTILITY", "departures_cs_lost", "Minions the lane loses to their roams"),
      r("UTILITY", "wards", "Wards per 10 min"),
      r("UTILITY", "vision", "Vision score per 10 min"),
      r("UTILITY", "vision_to_jungler", "Wards that spot the enemy jungler"),
      r("UTILITY", "setups", "Objective setup actions"),
      r("UTILITY", "backs", "Recalls before 14:00"),
      r("UTILITY", "sidelane_turns", "Side-lane turns per 10 min"),
      r("UTILITY", "damage", "Damage per 10 min", { digits: 0 }),
      r("UTILITY", "cs", "CS per 10 min"),
      r("UTILITY", "dying_charges_recovered", "Ward charges refilled while dead"),
    ],
  },
};

const ROAMS: Metric[] = [
  s("departures", "lane_departures_per_game", "Roams per game before 14:00"),
  s("departures", "support_departures_per_game", "…by supports"),
  s("departures", "mid_departures_per_game", "…by mid laners"),
  s("departures", "leaves_with_the_wave_pushed", "Roams with the wave pushed first", pct),
  s("departures", "gets_something", "Roams that get something", pct),
  s("departures", "a_deep_ward", "…a deep ward", pct),
  s("departures", "a_kill_they_hit_in", "…a kill they take part in", pct),
  s("departures", "leaves_accompanied", "Roams with an ally", pct),
  s("departures", "cs_lost_per_departure", "Minions lost per roam"),
];

const SIDE_LANES: Metric[] = [
  s("sidelanes", "sidelane_turns_per_10_min_from_14", "Side-lane turns per 10 min"),
  s("sidelanes", "dies_on_the_turn", "Turns that end in a death", pct),
  s("sidelanes", "rivals_not_located_while_pushing", "Enemies unaccounted for while pushing"),
  s("sidelanes", "the_rival_answers", "Turns the enemy answers", pct),
  s("sidelanes", "with_the_ult_ready", "Turns with ultimate up", pct),
  s("sidelanes", "cs_per_turn", "CS per turn"),
  s("side_balance", "sidelanes_abandoned_per_10_min_from_14", "Side lanes abandoned, per 10 min"),
  s("side_balance", "gold_lost_per_abandonment", "Gold lost per abandoned lane", { digits: 0 }),
  s("overgroup", "overgroups_per_10_min_from_14", "Overgroups per 10 min"),
  s("overgroup", "minions_lost_per_overgroup", "Minions lost per overgroup"),
];

const OBJECTIVES: Metric[] = [
  s("setups", "control_wards_in_the_area", "Control wards around the objective"),
  s("setups", "share_of_the_jungler_support_duo_s_work", "Setup work by jungle + support", pct),
  s("setups", "players_who_prepare_it", "Players involved in the setup"),
  s("setups", "seconds_of_ward_in_the_area", "Seconds of vision in the area", { unit: "s" }),
  s("setups", "punished_facechecks_in_the_setup", "Facechecks punished during the setup"),
];

const VISION: Metric[] = [
  r("TOP", "wards_killed", "Top wards cleared per 10 min"),
  r("JUNGLE", "wards_killed", "Jungle wards cleared per 10 min"),
  r("MIDDLE", "wards_killed", "Mid wards cleared per 10 min"),
  r("BOTTOM", "wards_killed", "ADC wards cleared per 10 min"),
  r("UTILITY", "wards_killed", "Support wards cleared per 10 min"),
  r("TOP", "vision_useful", "Top wards that reveal someone"),
  r("MIDDLE", "vision_useful", "Mid wards that reveal someone"),
  r("MIDDLE", "vision_seconds_of_info", "Mid: seconds of info from own wards"),
  r("UTILITY", "vision", "Support vision score per 10 min"),
  r("JUNGLE", "vision", "Jungle vision score per 10 min"),
  s("wards", "wards_on_the_rival_half_of_the_map", "Wards placed on the enemy half of the map", pct),
];

/** Decision traits (not result ones) in the winner-versus-loser comparison. */
const WIN_DECISIONS: { key: string; label: string }[] = [
  { key: "punishments", label: "Punishes enemy facechecks" },
  { key: "punished", label: "Gets punished facechecking" },
  { key: "setups", label: "Prepares objectives" },
  { key: "lane_gold", label: "Lane gold at 14:00" },
  { key: "lane_cs", label: "CS at 14:00" },
  { key: "blind_rival_side", label: "Time on the enemy side of the lane" },
  { key: "backs", label: "Recalls before 14:00" },
  { key: "trades_dies", label: "Dies in trades" },
  { key: "sidelane_turns", label: "Side-lanes alone" },
  { key: "departures_no_wave", label: "Roams without pushing" },
  { key: "jungler_invisible", label: "Time unseen (jungle)" },
];

const WIN_OUTCOMES: { key: string; label: string }[] = [
  { key: "level", label: "Level" },
  { key: "plates", label: "Plates" },
  { key: "gold", label: "Gold" },
  { key: "deaths", label: "Deaths" },
];

const OBJECTIVE_CONTROL: { key: string; label: string }[] = [
  { key: "presence", label: "More presence in the area" },
  { key: "control_wards", label: "More control wards" },
  { key: "punishments", label: "More facechecks punished" },
  { key: "ward_seconds", label: "More seconds of vision" },
  { key: "arrives", label: "Arrived earlier" },
];

export const ALL_METRICS: Metric[] = [
  ...FINDINGS.map((finding) => finding.metric),
  ...MISTAKES,
  ...CLIMBERS,
  ...UNCHANGED,
  ...FARMING,
  ...RECALLS,
  ...PRIO,
  ...LAST_HITS,
  ...TRADES,
  ...Object.values(ROLE_METRICS).flatMap((role) => role.metrics),
  ...ROAMS,
  ...SIDE_LANES,
  ...OBJECTIVES,
  ...VISION,
];
export { WIN_DECISIONS, WIN_OUTCOMES, OBJECTIVE_CONTROL };

// ── Pieces ────────────────────────────────────────────────────────────────────

/**
 * A metric's seven leagues. A single tone (the axis already states the league, and rank colours are
 * hard to tell apart): Gold and Challenger in acid, the two figures compared alongside.
 * The axis doesn't start at 0, so the shape shows; the numbers are always written out.
 */
function TierBars({ metric, height, labels = true }: { metric: Metric; height: number; labels?: boolean }) {
  const values = tierValues(metric);
  const max = Math.max(...values);
  const min = Math.min(...values);
  const floor = Math.max(0, min - (max - min) * 0.6);
  const span = max - floor || 1;
  const description = values.map((value, index) => `${TIER_NAMES[index]} ${formatValue(value, metric)}`).join(", ");
  return (
    <div>
      {/* fixed height and stretched width (preserveAspectRatio none): in a narrow card it doesn't grow in height */}
      <svg role="img" aria-label={`${metric.label}: ${description}`} viewBox="0 0 82 100" preserveAspectRatio="none" className="block w-full" style={{ height }}>
        {values.map((value, index) => {
          const h = Math.max(3, ((value - floor) / span) * 100);
          const edge = index === 0 || index === values.length - 1;
          return (
            <g key={TIER_SHORT[index]}>
              <title>{`${TIER_NAMES[index]}: ${formatValue(value, metric)}`}</title>
              {/* invisible strip over the whole column: the tooltip fires even if the bar is short */}
              <rect x={index * 12} y={0} width={10} height={100} fill="transparent" />
              <rect x={index * 12} y={100 - h} width={10} height={h} fill={edge ? palette.primary : palette.border} />
            </g>
          );
        })}
      </svg>
      {labels && (
        <div aria-hidden="true" className="mt-1 grid grid-cols-7 text-center text-xs font-bold text-subtle">
          {TIER_SHORT.map((tier) => (
            <span key={tier}>{tier}</span>
          ))}
        </div>
      )}
    </div>
  );
}

function TierHead({ tier, name }: { tier: string; name: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <RankEmblem tier={tier} size={18} />
      {name}
    </span>
  );
}

/** Metrics table: Gold, the shape across the seven leagues, Challenger and the change. */
function MetricTable({ metrics, label }: { metrics: Metric[]; label: string }) {
  return (
    <div className="relative overflow-x-auto">
      <table className="w-full text-sm sm:min-w-[34rem]" aria-label={label}>
        <thead>
          <tr className="microtext border-b border-line text-left text-subtle">
            <th scope="col" className="px-3 py-2.5 font-black sm:px-5">Metric</th>
            <th scope="col" className="px-2 py-2.5 text-right font-black"><TierHead tier="GOLD" name="Gold" /></th>
            <th scope="col" className="hidden w-28 px-2 py-2.5 font-black sm:table-cell"><span className="sr-only">All tiers</span></th>
            <th scope="col" className="px-2 py-2.5 text-right font-black"><TierHead tier="CHALLENGER" name="Chall" /></th>
            <th scope="col" className="px-3 py-2.5 text-right font-black sm:px-5">Change</th>
          </tr>
        </thead>
        <tbody>
          {metrics.map((metric) => {
            const values = tierValues(metric);
            const clear = isSignificant(metric);
            return (
              <tr key={metric.label} className="border-b border-line/60 last:border-0">
                <th scope="row" className="px-3 py-2 text-left font-normal text-soft sm:px-5">{metric.label}</th>
                <td className="px-2 py-2 text-right text-text tabular-nums">{formatValue(values[0] ?? 0, metric)}</td>
                <td className="hidden px-2 py-1.5 sm:table-cell"><TierBars metric={metric} height={20} labels={false} /></td>
                <td className="px-2 py-2 text-right text-text tabular-nums">{formatValue(values[6] ?? 0, metric)}</td>
                <td className="px-3 py-2 text-right tabular-nums sm:px-5">
                  {clear ? (
                    <span className="font-bold text-text">{relativeChange(values)}</span>
                  ) : (
                    <span className="text-xs whitespace-nowrap text-subtle">no clear change</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function Prose({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("flex max-w-3xl flex-col gap-3 text-sm leading-relaxed text-muted [&_strong]:text-text", className)}>{children}</div>;
}

function Section({ title, description, children, text }: { title: string; description?: string; children: ReactNode; text?: ReactNode }) {
  return (
    // min-w-0: in a grid, the table would widen the cell (and the page on mobile) instead of scrolling inside
    <Card className="min-w-0">
      <CardHeader title={title} description={description} />
      {text && <Prose className="px-5 pt-4">{text}</Prose>}
      <div className="py-2">{children}</div>
    </Card>
  );
}

function FindingCard({ finding }: { finding: Finding }) {
  const values = tierValues(finding.metric);
  return (
    <Card className="flex flex-col gap-3 p-5">
      <p className="microtext text-subtle">{finding.metric.label}</p>
      <div className="flex items-baseline justify-between gap-3">
        <p className="headline text-xl text-text tabular-nums">{relativeChange(values)}</p>
        <p className="text-xs text-muted tabular-nums">
          {formatValue(values[0] ?? 0, finding.metric)} → {formatValue(values[6] ?? 0, finding.metric)}
        </p>
      </div>
      <TierBars metric={finding.metric} height={64} />
      <h3 className="text-sm font-black tracking-field text-acid uppercase">{finding.title}</h3>
      <p className="text-sm leading-relaxed text-muted">{finding.body}</p>
    </Card>
  );
}

/** Cell of the winner/loser table: the % written out, and a blue tint (has more) or red (has less). */
function WinCell({ role, stat }: { role: Role; stat: string }) {
  const split = winSplit(role, stat);
  if (!split || Math.abs(split.z) < Z) {
    return <td className="px-3 py-2 text-center text-subtle">—</td>;
  }
  const lean = split.all - 0.5;
  const tint = lean > 0 ? "56, 189, 248" : "248, 113, 113";
  return (
    <td
      className="px-3 py-2 text-center font-bold text-text tabular-nums"
      style={{ background: `rgba(${tint}, ${Math.min(0.45, Math.abs(lean) * 1.2)})` }}
      title={`Winner has more in ${formatPercent(split.all * 100, 0)} of games`}
    >
      {formatPercent(split.all * 100, 0)}
    </td>
  );
}

function WinTable({ rows, label }: { rows: { key: string; label: string }[]; label: string }) {
  return (
    <div className="relative overflow-x-auto">
      <table className="w-full min-w-[34rem] text-sm" aria-label={label}>
        <thead>
          <tr className="microtext border-b border-line text-subtle">
            <th scope="col" className="px-5 py-2.5 text-left font-black">The winner…</th>
            {ROLES.map(({ role, name }) => (
              <th key={role} scope="col" className="px-3 py-2.5 text-center font-black">{name}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.key} className="border-b border-line/60 last:border-0">
              <th scope="row" className="px-5 py-2 text-left font-normal text-soft">{row.label}</th>
              {ROLES.map(({ role }) => (
                <WinCell key={role} role={role} stat={row.key} />
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ObjectiveControl() {
  return (
    <ul className="flex flex-col gap-3 p-5">
      {OBJECTIVE_CONTROL.map(({ key, label }) => {
        const all = stats.objectives[key]?.all;
        const share = all && all.n ? all.wins / all.n : 0;
        return (
          <li key={key} className="grid grid-cols-[minmax(0,13rem)_1fr_3.5rem] items-center gap-3 text-sm">
            <span className="text-soft">{label}</span>
            <span className="relative h-2 bg-panel-light" aria-hidden="true">
              <span className="absolute inset-y-0 left-0 bg-acid-dark" style={{ width: `${share * 100}%` }} />
              <span className="absolute inset-y-[-3px] left-1/2 w-px bg-muted/60" />
            </span>
            <span className="text-right font-bold text-text tabular-nums">{formatPercent(share * 100, 0)}</span>
          </li>
        );
      })}
      <li className="text-xs text-subtle">
        Share of contested objectives taken by the team that did more of each. The line marks 50%, a coin flip.
      </li>
    </ul>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

const TABS = [
  { value: "summary", label: "Summary" },
  { value: "laning", label: "Laning" },
  { value: "roles", label: "Roles" },
  { value: "macro", label: "Macro & vision" },
  { value: "winning", label: "What wins games" },
  { value: "method", label: "Method" },
] as const;

/** All the figures, for whoever wants the detail: the "Deep dive" tab of Stats by rank. */
export function DeepDive() {
  const [params, setParams] = useSearchParams();
  const tab = TABS.find((option) => option.value === params.get("tab"))?.value ?? "summary";
  const role = ROLES.find((option) => option.role === params.get("role"))?.role ?? "TOP";
  const jungleKills = winSplit("JUNGLE", "kills");

  const go = (next: Record<string, string>) =>
    setParams({ view: "deep", ...Object.fromEntries(Object.entries(next).filter(([, value]) => value !== "summary")) }, {
      replace: true,
      preventScrollReset: true,
    });

  return (
    <>
      <Tabs value={tab} onValueChange={(value) => go(value === "roles" ? { tab: value, role } : { tab: value })}>
        <TabsList aria-label="Deep dive sections" className="flex-wrap gap-y-3">
          {TABS.map((option) => (
            <TabsTrigger key={option.value} value={option.value}>
              {option.label}
            </TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value="summary" className="mt-6 flex flex-col gap-6 focus:outline-none">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {FINDINGS.map((finding) => (
              <FindingCard key={finding.title} finding={finding} />
            ))}
          </div>

          <div className="grid gap-6 xl:grid-cols-2">
            <Section
              title="Mistakes that fade as you climb"
              description="Lower is better. Each one shrinks steadily, tier after tier."
              text={
                <p>
                  Low-elo games are lost to <strong>leaks, not to bad calls</strong>: minions dropped on every recall,
                  crash and roam, camps left idle, crashed waves nobody uses. None of these needs better mechanics.
                </p>
              }
            >
              <MetricTable metrics={MISTAKES} label="Mistakes that fade as you climb" />
            </Section>
            <Section
              title="What climbers do more"
              description="Higher is more common in high elo."
              text={
                <p>
                  In high elo, <strong>the lane advantage is taken to the rest of the map</strong>. Waves are crashed in
                  order to go somewhere else, supports and mids roam, vision is denied as well as placed, and the
                  jungle–support duo takes over objective setup.
                </p>
              }
            >
              <MetricTable metrics={CLIMBERS} label="What climbers do more" />
            </Section>
          </div>

          <Section
            title="What doesn't change"
            description="The same from Gold to Challenger: none of these moves past the bar."
            text={
              <p>
                The trades themselves, when to recall and what a roam gets you look alike in every tier. They are
                not what separates the ranks, or the concept doesn&apos;t capture the difference.
              </p>
            }
          >
            <MetricTable metrics={UNCHANGED} label="What doesn't change with rank" />
          </Section>
        </TabsContent>

        <TabsContent value="laning" className="mt-6 flex flex-col gap-6 focus:outline-none">
          <Section
            title="Farming"
            description="Minutes 2 to 14 for CS at 14:00, whole game for the per-10-minute rates."
            text={
              <p>
                CS is the metric that ranks the tiers most cleanly: it rises tier after tier, with no jumps. At 14:00 a
                Challenger ADC has 15 more minions than a Gold one.
              </p>
            }
          >
            <MetricTable metrics={FARMING} label="Farming by rank" />
          </Section>

          <Section
            title="Recalls"
            description="Laning phase, to 14:00. The last four rows are the share of recalls by the wave left behind."
            text={
              <p>
                High-elo players recall <strong>more often and more cheaply</strong>, but on the same waves. The split
                between recalling before the cannon wave, after it or on a normal wave is identical in every tier. The
                difference is how well the wave is set up before leaving. They also cancel more recalls, and the rise
                comes mostly with an enemy on screen (within 2,000 units): in high elo a recall started too close gets
                punished, because the opponent knows the tempo it buys. It rarely takes a hit: walking up is enough.
              </p>
            }
          >
            <MetricTable metrics={RECALLS} label="Recalls by rank" />
          </Section>

          <Section
            title="What players do after crashing a wave"
            description="Crashing a wave into the enemy tower pins the opponent and frees a few seconds. What each crash is used for, to 15:00."
            text={
              <p>
                Crashing with no follow-up is halved. <strong>Rotating to another lane almost triples</strong>, and a
                third of Challenger crashes are used for two things at once. Harassing under tower is the one use that
                stays flat.
              </p>
            }
          >
            <MetricTable metrics={PRIO} label="Crash follow-ups by rank" />
          </Section>

          <div className="grid gap-6 xl:grid-cols-2">
            <Section
              title="Last hits & lane position"
              description="Minutes 0 to 14. Time on the enemy side is the share of the laning phase spent alive past the middle of the lane."
              text={
                <p>
                  A missed last hit is a minion from your lane that dies within 700 units of you, alive, without you
                  taking the gold: <strong>they fall by about 40% from Gold to Challenger</strong> in every lane. Where laners
                  stand barely moves: under a third of the laning phase past the middle of the lane, in every tier
                  (a bit more for top and for supports climbing). In the same lane, though, the winner is usually the
                  one standing further up.
                </p>
              }
            >
              <MetricTable metrics={LAST_HITS} label="Last hits and lane position by rank" />
            </Section>
            <Section
              title="Trades"
              text={
                <p>
                  The trade itself barely changes: same damage, length, health left and death rate. High-elo trades
                  pack more abilities, and mids burn fewer summoners in them. What improves is everything around the
                  trade.
                </p>
              }
            >
              <MetricTable metrics={TRADES} label="Trades by rank" />
            </Section>
          </div>
        </TabsContent>

        <TabsContent value="roles" className="mt-6 flex flex-col gap-6 focus:outline-none">
          <div role="group" aria-label="Role" className="flex flex-wrap gap-1.5">
            {ROLES.map((option) => (
              <button
                key={option.role}
                type="button"
                aria-pressed={option.role === role}
                onClick={() => go({ tab: "roles", role: option.role })}
                className={cn(
                  "cursor-pointer border px-3 py-1.5 text-xs font-bold transition-colors",
                  option.role === role ? "border-acid bg-acid/15 text-acid" : "border-line text-muted hover:text-text",
                )}
              >
                {option.name}
              </button>
            ))}
          </div>
          <Section
            title={ROLES.find((option) => option.role === role)?.name ?? role}
            text={<p>{ROLE_METRICS[role].summary}</p>}
          >
            <MetricTable metrics={ROLE_METRICS[role].metrics} label={`${role} by rank`} />
          </Section>
        </TabsContent>

        <TabsContent value="macro" className="mt-6 flex flex-col gap-6 focus:outline-none">
          <Section
            title="Roams"
            description="Every time a laner leaves their lane before 14:00."
            text={
              <p>
                High-elo players roam <strong>74% more, and each roam is just as productive</strong>: about four in five
                get something (a kill, a camp, a burned summoner, a deep ward) in every tier. Roaming more doesn&apos;t
                dilute it, and each roam costs fewer minions.
              </p>
            }
          >
            <MetricTable metrics={ROAMS} label="Roams by rank" />
          </Section>

          <Section
            title="Side lanes & grouping"
            description="From 14:00 to the end of the game."
            text={
              <>
                <p>
                  Side-laners die less per turn <strong>with the same information</strong>: about two enemies are
                  unaccounted for in every tier. The difference is in the exit, not in what they know.
                </p>
                <p>
                  Overgroups (minions dying under your own tower while three or more teammates stand elsewhere) rise
                  with rank, but abandoned side lanes fall. High-elo teams group more often around objectives and
                  accept a few lost minions, then fix the lane before it bleeds wave after wave.
                </p>
              </>
            }
          >
            <MetricTable metrics={SIDE_LANES} label="Side lanes by rank" />
          </Section>

          <div className="grid gap-6 xl:grid-cols-2">
            <Section
              title="Setting up objectives"
              description="The 90 seconds before each dragon, grub, herald and baron, per team."
              text={
                <p>
                  Fewer players do the setup and the jungle–support duo takes almost two thirds of it. Control wards go up 90%.
                  Total vision time around the pit barely moves.
                </p>
              }
            >
              <MetricTable metrics={OBJECTIVES} label="Objective setup by rank" />
            </Section>
            <Section
              title="Who takes the objective"
              description="The same in every tier."
              text={
                <p>
                  Arriving first decides nothing on its own. <strong>Controlling the area does</strong>: denying vision
                  and punishing whoever walks in. Presence is partly circular, since whoever stands there is who takes
                  it.
                </p>
              }
            >
              <ObjectiveControl />
            </Section>
          </div>

          <Section
            title="Vision"
            description="Laning phase for revealing wards, whole game for the rest."
            text={
              <p>
                <strong>Clearing enemy wards is what rises most</strong>, in every role. Laners&apos; wards in high elo
                reveal someone more often, and for longer. Vision score itself only really moves for support and jungle.
              </p>
            }
          >
            <MetricTable metrics={VISION} label="Vision by rank" />
          </Section>
        </TabsContent>

        <TabsContent value="winning" className="mt-6 flex flex-col gap-6 focus:outline-none">
          <Section
            title="What separates winners from losers"
            description="Winner against loser in the same role and the same game. Share of games where the winner has more; 50% means it doesn't separate them."
            text={
              <>
                <p>
                  Every game is compared with itself: same tier, same length, the two players facing each other. Blue
                  means the winner does more of it, red means less. Blank cells don&apos;t pass the bar.
                </p>
                <p>
                  <strong>Punishing facechecks and not getting punished</strong> separates winners in every role, more
                  for ADC and support. Spending the laning phase on the enemy side of the lane separates them in mid,
                  bot lane and support, and recalling more often during laning in every lane. Winning ADCs and supports side-lane alone <em>less</em>: ending up alone in a side lane is
                  a sign of losing.
                </p>
              </>
            }
          >
            <WinTable rows={WIN_DECISIONS} label="Decisions that separate winners" />
          </Section>

          <div className="grid gap-6 xl:grid-cols-2">
            <Section
              title="Outcomes"
              description="These separate winners the most, but mostly because they won."
            >
              <WinTable rows={WIN_OUTCOMES} label="Outcomes of winning" />
            </Section>
            <Card className="p-5">
              <p className="microtext text-subtle">Does it change with rank?</p>
              <p className="mt-2 text-sm leading-relaxed text-soft">
                Almost never. What separates a winner from a loser weighs the same in Gold and in Challenger: everyone
                gets better, but what decides games stays the same.
              </p>
              {jungleKills && (
                <div className="mt-5 border-t border-line pt-4">
                  <p className="text-sm text-muted">The one clear exception: jungle kills.</p>
                  <div className="mt-3 flex items-end gap-6">
                    <div>
                      <p className="headline text-xl text-text tabular-nums">{formatPercent(jungleKills.low * 100, 0)}</p>
                      <p className="microtext mt-1 text-subtle">Gold–Plat</p>
                    </div>
                    <div>
                      <p className="headline text-xl text-acid tabular-nums">{formatPercent(jungleKills.high * 100, 0)}</p>
                      <p className="microtext mt-1 text-subtle">Master+</p>
                    </div>
                  </div>
                  <p className="mt-3 text-sm leading-relaxed text-muted">
                    Share of games where the winning jungler has more kills. In high elo, a jungler who turns ganks
                    into kills wins much more often.
                  </p>
                </div>
              )}
            </Card>
          </div>

          <Card className="p-5">
            <Prose>
              <p>
                <strong>These are associations, not causes.</strong> A player who is ahead crashes more waves because
                they are ahead. Laning-phase metrics (to 14:00) are less tangled up with the result than later ones, but
                not free of it. Telling &ldquo;what wins&rdquo; from &ldquo;what the winning side does&rdquo; is the job
                of the model, using the game state at every moment.
              </p>
            </Prose>
          </Card>
        </TabsContent>

        <TabsContent value="method" className="mt-6 flex flex-col gap-6 focus:outline-none">
          <Section title="Data">
            <Prose className="px-5 pb-3">
              <p>
                Ranked solo games from EUW, from Gold to Challenger. Each game&apos;s tier is that of the player it was
                sampled from (up to three games per player); the rest of the lobby sits at similar MMR.
              </p>
              <p>
                Every game is decoded from its replay file into a table with every champion every second, plus every
                event (casts, damage, deaths, wards, minions, camps). The concepts are measured on top of that: waves
                crashed and what follows, recalls and the wave left behind, roams, side lanes, objective setup, vision
                that reveals someone.
              </p>
            </Prose>
          </Section>
          <Section title="How to read the numbers">
            <Prose className="px-5 pb-3">
              <p>
                <strong>Gold → Challenger</strong> are the tier averages. The bars show all seven tiers, from G to C.
                The axis doesn&apos;t start at zero, so the shape shows up; the numbers are always written out.
              </p>
              <p>
                <strong>Counts are per 10 minutes of the stretch they measure.</strong> Laning-phase stats cover a fixed
                window (minutes 2–14), late-game ones start at 14:00, and official stats cover the whole game.
                Otherwise the tier with longer games would seem to &ldquo;do more of everything&rdquo;.
              </p>
              <p>
                <strong>A pattern must clear |z| ≥ {Z}</strong> on the rank correlation (Spearman, one value per game), or
                p &lt; 0.0001. With hundreds of comparisons, chance doesn&apos;t get a single one through. Rows that miss
                the bar are shown as &ldquo;no clear change&rdquo;.
              </p>
            </Prose>
          </Section>
          <Section title="Limits">
            <Prose className="px-5 pb-3">
              <p>
                One sample, one region: correlations around 0.15 are real, but small. Late-game
                metrics are the most tangled up with who is winning.
              </p>
              <p>
                The metrics are rules, not ground truth: where a rule falls short, the pattern inherits it. For example,
                &ldquo;overextended with the jungler unseen&rdquo; always assumes the worst case. A few impossible
                health and mana readings were dropped, and the games that don&apos;t fully match their own post-game
                stats change none of the results.
              </p>
            </Prose>
          </Section>
        </TabsContent>
      </Tabs>
    </>
  );
}
