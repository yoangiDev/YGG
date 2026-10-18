import {
  Coins,
  Equal,
  Undo2,
  EyeOff,
  Footprints,
  House,
  Target,
  Trees,
  Trophy,
  type LucideIcon,
} from "lucide-react";
import { useId, useState, type ReactNode } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { ChartTooltipBox } from "@/components/charts/ChartTooltip";
import { RankEmblem, RoleIcon } from "@/components/player/PlayerBits";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/cn";
import { MINIMAP, OBJECTIVE_ICONS } from "@/lib/ddragon";
import { formatNumber, formatPercent } from "@/lib/format";
import { categorical, palette } from "@/lib/palette";
import { rankImage } from "@/lib/rank";

import {
  enemyHalfShare,
  formatValue,
  friendlyChange,
  type Metric,
  objectiveShare,
  type Role,
  ROLES,
  stats,
  TIER_NAMES,
  TIER_SHORT,
  TIERS,
  type Team,
  tierValues,
  type WardGroup,
  winnerShare,
} from "./rankStats";

// ── Metrics ───────────────────────────────────────────────────────────────────
// The view for everyone: few figures, in everyday words. `OVERVIEW_METRICS` gathers them for the test.

const r = (role: Role, key: string, label: string, extra: Partial<Metric> = {}): Metric => ({ ref: { role, key }, label, ...extra });
const s = (table: string, key: string, label: string, extra: Partial<Metric> = {}): Metric => ({ ref: { table, key }, label, ...extra });
const pct = { unit: "%", digits: 0 } as const;
const perMinute = { scale: 0.1, digits: 1 } as const;

// Grey for the starting league and acid for Challenger: the comparison repeated throughout the page.
const GOLD_BAR = palette.subtle;
// Only to tell the cards apart; no data goes in these colours (DESIGN.md: data in stat-*).
const HUES = [palette.gold, palette.blue, palette.red, palette.green, categorical.indigo, palette.primary];

interface Habit {
  icon: LucideIcon;
  title: string;
  metric: Metric;
  body: string;
}

const HABITS: Habit[] = [
  {
    icon: Coins,
    title: "They farm more",
    metric: r("BOTTOM", "cs", "Minions per minute (ADC)", perMinute),
    body: "A Challenger ADC takes about 1.4 more minions every minute. In a 25-minute game, that's around 36 extra minions.",
  },
  {
    icon: House,
    title: "They lose less when recalling",
    metric: s("backs", "cs_lost_per_back", "Minions lost per recall", { digits: 1 }),
    body: "Going back to base always costs some minions. Challenger players lose fewer, because they leave the wave in a better state first.",
  },
  {
    icon: Target,
    title: "They never waste a push",
    metric: s("prio", "crash_with_no_use_at_all", "Pushes followed by nothing", pct),
    body: "Pushing the wave into the enemy tower buys a few free seconds. In Gold, 1 in 11 of those moments is wasted; in Challenger, 1 in 20.",
  },
  {
    icon: Footprints,
    title: "Supports leave the lane",
    metric: r("UTILITY", "departures", "Support roams before 14:00", { digits: 1 }),
    body: "Challenger supports roam twice as often in the early game, helping the jungler and mid instead of staying bot.",
  },
  {
    icon: EyeOff,
    title: "They destroy enemy vision",
    metric: r("MIDDLE", "wards_killed", "Wards destroyed per 10 min (mid)", { digits: 2 }),
    body: "Clearing enemy wards is what grows the most as you climb. Challenger mids destroy almost twice as many as Gold mids.",
  },
  {
    icon: Trees,
    title: "Junglers keep farming",
    metric: r("JUNGLE", "idle_clears_lost", "Camp clears lost before 14:00", { digits: 1 }),
    body: "Leaving camps up is the classic jungle mistake. Gold junglers lose about 5 clears by minute 14; Challenger junglers, about 3.5.",
  },
];

// Missed last hits: a minion of their lane that dies within 700 of the laner, alive, without them collecting its gold.
const LANERS = ROLES.filter(({ role }) => role === "TOP" || role === "MIDDLE" || role === "BOTTOM");
const missed = (role: Role) => r(role, "finishes_missed", "Missed last hits by 14:00", { digits: 1 });
const accuracy = (role: Role) => r(role, "finishes_hit_rate", "Minions taken when in range", pct);

interface ClimbOption {
  label: string;
  caption: string;
  values: number[];
  format: (value: number) => string;
}

const climbMetric = (label: string, caption: string, metric: Metric): ClimbOption => ({
  label,
  caption,
  values: tierValues(metric),
  format: (value) => formatValue(value, metric),
});

const ADC_CS = r("BOTTOM", "cs", "ADC minions per minute", perMinute);
const ROAMS = s("departures", "lane_departures_per_game", "Roams per game before 14:00", { digits: 1 });
const WASTED = s("prio", "crash_with_no_use_at_all", "Wasted pushes", pct);
const ADC_WARDS = r("BOTTOM", "wards_killed", "ADC wards destroyed per 10 min", { digits: 2 });
const CLIMB_METRICS: Metric[] = [ADC_CS, missed("BOTTOM"), ROAMS, WASTED, ADC_WARDS];

const PUSH_USES: Metric[] = [
  s("prio", "crash_goes_back_to_base", "Go back to base", pct),
  s("prio", "crash_rotates_to_another_lane", "Go help another lane", pct),
  s("prio", "crash_vision", "Place a ward", pct),
  s("prio", "crash_goes_into_the_fog", "Hide in the fog", pct),
  s("prio", "crash_harass_under_tower", "Poke the enemy under tower", pct),
  s("prio", "crash_with_no_use_at_all", "Nothing at all", pct),
];

const WINNING: { key: string; less?: boolean; text: string }[] = [
  { key: "punishments", text: "catches more enemies walking in alone" },
  { key: "blind_rival_side", text: "spends more of the laning phase on the enemy side of the lane" },
  { key: "lane_gold", text: "has more gold from the lane at 14 minutes" },
  { key: "setups", text: "does more to prepare dragons and barons" },
  { key: "trades_dies", less: true, text: "dies less when trading in lane" },
];

const OBJECTIVES: { key: string; text: string }[] = [
  { key: "presence", text: "had more players around it" },
  { key: "control_wards", text: "placed more control wards" },
  { key: "punishments", text: "caught more enemies walking in" },
  { key: "arrives", text: "simply got there first" },
];

const DUO_SHARE = s("setups", "share_of_the_jungler_support_duo_s_work", "Setup done by jungle + support", pct);

const MYTHS: { title: string; metric?: Metric; body: string; icon?: LucideIcon }[] = [
  {
    title: "Playing further up",
    metric: r("BOTTOM", "blind_rival_side", "of the laning phase on the enemy side (ADC)", pct),
    body: "Laners spend under a third of the laning phase past the middle of their lane, in every tier. What it does tell you is who wins the lane: usually the one standing there.",
  },
  {
    title: "You can recall anywhere",
    icon: Undo2,
    metric: s("recalls", "cancelled_with_a_rival_on_screen_per_player_and_game", "recalls cancelled with an enemy on screen, per player", { digits: 1 }),
    body: "Not in high elo. A recall started too close gets punished: good players walk up and force the cancel, because they know the tempo it buys. Challenger players cancel 28% more of them.",
  },
  {
    title: "Trading harder",
    metric: s("trades", "damage_per_champion_and_trade", "damage per trade", { digits: 0 }),
    body: "A trade deals the same damage in Gold and in Challenger. What changes is everything around it: the wave, the recall, the roam.",
  },
  {
    title: "Getting there first",
    body: "Arriving first at an objective wins it only half the time. Controlling the area around it is what matters.",
  },
];

interface Tip {
  title: string;
  metric: Metric;
  body: string;
}

const ROLE_TIPS: Record<Role, { intro: string; tips: Tip[] }> = {
  TOP: {
    intro: "High-elo top laners farm more, waste less and fight for vision.",
    tips: [
      { title: "Farm more", metric: r("TOP", "cs", "Minions per minute", perMinute), body: "About one more minion every minute than a Gold top laner." },
      { title: "Waste fewer minions", metric: r("TOP", "prio_cs_lost", "Minions lost around your pushes", { digits: 1 }), body: "A third fewer minions lost when pushing and leaving the lane." },
      { title: "Destroy more wards", metric: r("TOP", "wards_killed", "Wards destroyed per 10 min", { digits: 2 }), body: "Almost twice as many. Less enemy vision means safer pushes." },
    ],
  },
  JUNGLE: {
    intro: "High-elo junglers show up more often without falling behind on farm.",
    tips: [
      { title: "Keep your camps cycling", metric: r("JUNGLE", "idle_clears_lost", "Camp clears lost before 14:00", { digits: 1 }), body: "Leaving small camps up adds up: Gold junglers lose about 5 clears by minute 14." },
      { title: "Show up in lanes more", metric: r("JUNGLE", "jungler_shows_up", "Times seen in lanes before 14:00", { digits: 1 }), body: "Challenger junglers appear more often, and less often with their camps sitting idle." },
      { title: "Die less", metric: r("JUNGLE", "deaths", "Deaths per 10 min", { digits: 2 }), body: "They walk into fewer traps and go back to spend their gold sooner." },
    ],
  },
  MIDDLE: {
    intro: "High-elo mids manage the wave better and get more out of their vision.",
    tips: [
      { title: "Waste about half as many minions", metric: r("MIDDLE", "prio_cs_lost", "Minions lost around your pushes", { digits: 1 }), body: "The biggest wave-management improvement of any role." },
      { title: "Miss fewer last hits", metric: missed("MIDDLE"), body: "About 9 fewer minions left to die within reach by minute 14 than a Gold mid." },
      { title: "Get more from your wards", metric: r("MIDDLE", "vision_seconds_of_info", "Seconds of info per ward", { digits: 1 }), body: "Their wards spot enemies more often and for longer: placed where people walk." },
    ],
  },
  BOTTOM: {
    intro: "High-elo ADCs farm more and stop wandering alone in side lanes.",
    tips: [
      { title: "Farm more", metric: r("BOTTOM", "cs", "Minions per minute", perMinute), body: "The biggest farming gap of any role: about 1.4 minions more every minute." },
      { title: "Stop side-laning alone", metric: r("BOTTOM", "sidelane_turns", "Side-lane turns per 10 min after 14:00", { digits: 2 }), body: "Challenger ADCs side-lane about a third less often, and die there about a third less often." },
      { title: "Destroy more wards", metric: r("BOTTOM", "wards_killed", "Wards destroyed per 10 min", { digits: 2 }), body: "Twice as many as a Gold ADC." },
    ],
  },
  UTILITY: {
    intro: "Support is the role that changes most: from a second carry to a map player.",
    tips: [
      { title: "Roam twice as much", metric: r("UTILITY", "departures", "Roams before 14:00", { digits: 1 }), body: "Helping mid and the jungler instead of staying in bot lane." },
      { title: "Ward more", metric: r("UTILITY", "wards", "Wards placed per 10 min", { digits: 1 }), body: "Almost 50% more wards, and more of them spot the enemy jungler." },
      { title: "Stop playing for damage", metric: r("UTILITY", "damage", "Damage per 10 min", { digits: 0 }), body: "Challenger supports deal less damage: their time goes into vision and roams." },
    ],
  },
};

export const OVERVIEW_METRICS: Metric[] = [
  ...HABITS.map((habit) => habit.metric),
  ...CLIMB_METRICS,
  ...LANERS.flatMap(({ role }) => [missed(role), accuracy(role)]),
  ...PUSH_USES,
  DUO_SHARE,
  ...MYTHS.flatMap((myth) => (myth.metric ? [myth.metric] : [])),
  ...Object.values(ROLE_TIPS).flatMap((role) => role.tips.map((tip) => tip.metric)),
];
export const WINNING_KEYS = WINNING.map((row) => row.key);
export const OBJECTIVE_KEYS = OBJECTIVES.map((row) => row.key);

// ── Pieces ────────────────────────────────────────────────────────────────────

function SectionTitle({ eyebrow, title, children }: { eyebrow: string; title: string; children?: ReactNode }) {
  return (
    <div className="mb-5 max-w-3xl">
      <p className="eyebrow mb-2">{eyebrow}</p>
      <h2 className="headline text-xl text-text sm:text-xl">{title}</h2>
      {children && <p className="mt-2 text-sm leading-relaxed text-muted">{children}</p>}
    </div>
  );
}

/** Gold against Challenger in two bars from zero, with the emblem and the figure written alongside. */
function Versus({ metric }: { metric: Metric }) {
  const values = tierValues(metric);
  const gold = values[0] ?? 0;
  const challenger = values[values.length - 1] ?? 0;
  const max = Math.max(gold, challenger) || 1;
  const rows = [
    { tier: "GOLD", name: "Gold", value: gold, color: GOLD_BAR },
    { tier: "CHALLENGER", name: "Challenger", value: challenger, color: palette.primary },
  ];
  return (
    <div role="img" aria-label={`${metric.label}: Gold ${formatValue(gold, metric)}, Challenger ${formatValue(challenger, metric)}`}>
      <p className="mb-2 text-xs text-subtle">{metric.label}</p>
      <div className="flex flex-col gap-2" aria-hidden="true">
        {rows.map((row) => (
          <div key={row.tier} className="grid grid-cols-[22px_1fr_3.5rem] items-center gap-2.5">
            <RankEmblem tier={row.tier} size={22} />
            <span className="h-3 bg-white/[0.05]">
              <span className="block h-full" style={{ width: `${(row.value / max) * 100}%`, background: row.color }} />
            </span>
            <span className="text-right text-sm font-bold text-text tabular-nums">{formatValue(row.value, metric)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function ChangeBadge({ metric }: { metric: Metric }) {
  return (
    <span className="border border-acid/30 bg-acid/10 px-2 py-1 text-sm font-black text-acid tabular-nums">
      {friendlyChange(tierValues(metric))}
    </span>
  );
}

function HabitCard({ habit, hue }: { habit: Habit; hue: string }) {
  const Icon = habit.icon;
  return (
    <Card className="flex flex-col gap-4 p-5">
      <div className="flex items-center justify-between">
        <span className="grid size-11 place-items-center rounded-full" style={{ background: `${hue}22`, color: hue }}>
          <Icon className="size-5" aria-hidden="true" />
        </span>
        <ChangeBadge metric={habit.metric} />
      </div>
      <h3 className="text-lg font-black text-text">{habit.title}</h3>
      <Versus metric={habit.metric} />
      <p className="text-sm leading-relaxed text-muted">{habit.body}</p>
    </Card>
  );
}

/** Axis with round values (6.5, 7, 7.5… or 26, 27, 28…): with recharts' own they came out 6.8, 7.2, 7.7. */
export function niceScale(values: number[]): { domain: [number, number]; ticks: number[] } {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const base = 10 ** Math.floor(Math.log10(max - min || 1)) / 2;
  const low = Math.floor(min / base) * base;
  const high = Math.ceil(max / base) * base;
  const step = base * Math.ceil((high - low) / base / 5);
  const ticks = Array.from({ length: Math.floor((high - low) / step + 1e-9) + 1 }, (_, i) => +(low + i * step).toFixed(6));
  return { domain: [low, Math.max(high, ticks[ticks.length - 1] ?? high)], ticks };
}

/** League axis with its emblem: understood without reading. */
function TierTick({ x = 0, y = 0, payload }: { x?: number | string; y?: number | string; payload?: { value?: unknown } }) {
  const tier = typeof payload?.value === "string" ? payload.value : "";
  const index = TIERS.indexOf(tier as (typeof TIERS)[number]);
  return (
    <g transform={`translate(${Number(x)},${Number(y)})`}>
      <image href={rankImage(tier)} x={-12} y={4} width={24} height={24} />
      <text x={0} y={42} textAnchor="middle" fill={palette.muted} fontSize={10}>
        {TIER_SHORT[index] ?? ""}
      </text>
    </g>
  );
}

function ClimbChart() {
  const first = climbMetric("Minions per minute", "How many minions an ADC takes every minute.", ADC_CS);
  const options: ClimbOption[] = [
    first,
    {
      label: "Game length",
      caption: "How long a game lasts, in minutes. Higher tiers close games faster.",
      values: stats.duration.means,
      format: (value) => `${formatNumber(value, 1)} min`,
    },
    climbMetric(
      "Missed last hits",
      "Minions from the ADC's lane that die within their reach by minute 14 without them taking the gold.",
      missed("BOTTOM"),
    ),
    climbMetric("Roams", "Times players leave their lane to help elsewhere before minute 14, per game.", ROAMS),
    climbMetric("Wasted pushes", "Share of pushed waves followed by nothing useful.", WASTED),
    climbMetric("Wards destroyed", "Enemy wards an ADC destroys every 10 minutes.", ADC_WARDS),
  ];
  const [selected, setSelected] = useState(0);
  const option = options[selected] ?? first;
  const rows = TIERS.map((tier, index) => ({ tier, value: option.values[index] ?? 0 }));
  const summary = rows.map((row, index) => `${TIER_NAMES[index]} ${option.format(row.value)}`).join(", ");
  const scale = niceScale(option.values);

  return (
    <Card className="p-5">
      <div role="group" aria-label="Metric" className="mb-3 flex flex-wrap gap-1.5">
        {options.map((item, index) => (
          <button
            key={item.label}
            type="button"
            aria-pressed={index === selected}
            onClick={() => setSelected(index)}
            className={cn(
              "cursor-pointer border px-3 py-1.5 text-xs font-bold transition-colors",
              index === selected ? "border-acid bg-acid/15 text-acid" : "border-line text-muted hover:text-text",
            )}
          >
            {item.label}
          </button>
        ))}
      </div>
      <p className="mb-4 text-sm text-muted">{option.caption}</p>
      <div role="img" aria-label={`${option.label}: ${summary}`} className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 12, right: 20, bottom: 4, left: 0 }}>
            <CartesianGrid stroke={palette.grid} vertical={false} />
            <XAxis dataKey="tier" interval={0} height={50} tickLine={false} axisLine={{ stroke: palette.border }} tick={(props) => <TierTick {...props} />} />
            <YAxis
              width={52}
              tickLine={false}
              axisLine={false}
              tick={{ fill: palette.muted, fontSize: 11 }}
              tickFormatter={(value: number) => option.format(value)}
              domain={scale.domain}
              ticks={scale.ticks}
            />
            <Tooltip
              cursor={{ stroke: palette.border }}
              content={(props) => {
                const row = props.active ? (props.payload[0]?.payload as { tier: string; value: number } | undefined) : undefined;
                if (!row) return null;
                return (
                  <ChartTooltipBox title={TIER_NAMES[TIERS.indexOf(row.tier as (typeof TIERS)[number])]}>
                    <span className="tabular-nums">{option.format(row.value)}</span>
                  </ChartTooltipBox>
                );
              }}
            />
            <Line
              type="monotone"
              dataKey="value"
              stroke={palette.primary}
              strokeWidth={3}
              dot={{ r: 5, fill: palette.primary, stroke: palette.surface, strokeWidth: 2 }}
              activeDot={{ r: 7 }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}

function Legend() {
  return (
    <p className="flex flex-wrap items-center gap-x-5 gap-y-1 text-xs text-muted">
      <span className="flex items-center gap-1.5">
        <span className="size-2.5" style={{ background: GOLD_BAR }} aria-hidden="true" />
        <RankEmblem tier="GOLD" size={16} /> Gold
      </span>
      <span className="flex items-center gap-1.5">
        <span className="size-2.5 bg-acid" aria-hidden="true" />
        <RankEmblem tier="CHALLENGER" size={16} /> Challenger
      </span>
    </p>
  );
}

/** Grouped bars: what they do with their free seconds, in Gold and in Challenger. */
function PushChart() {
  const rows = PUSH_USES.map((metric) => {
    const values = tierValues(metric);
    return { metric, gold: values[0] ?? 0, challenger: values[values.length - 1] ?? 0 };
  });
  const max = Math.max(...rows.flatMap((row) => [row.gold, row.challenger]));
  return (
    <Card className="p-5">
      <ul className="flex flex-col gap-4">
        {rows.map(({ metric, gold, challenger }) => (
          <li key={metric.label} className="grid gap-1.5 sm:grid-cols-[13rem_1fr] sm:items-center sm:gap-4">
            <span className="text-sm font-bold text-soft">{metric.label}</span>
            <div
              className="flex flex-col gap-1"
              role="img"
              aria-label={`${metric.label}: Gold ${formatValue(gold, metric)}, Challenger ${formatValue(challenger, metric)}`}
            >
              {[
                { value: gold, color: GOLD_BAR, text: "text-muted" },
                { value: challenger, color: palette.primary, text: "text-text" },
              ].map((bar, index) => (
                <span key={index} className="flex items-center gap-2" aria-hidden="true">
                  <span className="h-3" style={{ width: `${(bar.value / max) * 85}%`, background: bar.color }} />
                  <span className={cn("text-xs font-bold tabular-nums", bar.text)}>{formatValue(bar.value, metric)}</span>
                </span>
              ))}
            </div>
          </li>
        ))}
      </ul>
      <div className="mt-5 border-t border-line pt-3">
        <Legend />
      </div>
    </Card>
  );
}

/** Ten icons, lit up as many as the matches out of ten: read without knowing statistics. */
function IconArray({ share, icon, label }: { share: number; icon: (lit: boolean, index: number) => ReactNode; label: string }) {
  const lit = Math.round(share * 10);
  return (
    <div role="img" aria-label={`${label}: ${lit} in 10`} className="flex flex-wrap items-center gap-x-3 gap-y-1">
      <span className="flex gap-1" aria-hidden="true">
        {Array.from({ length: 10 }, (_, index) => icon(index < lit, index))}
      </span>
      <span className="shrink-0 text-sm font-black text-text tabular-nums">{lit} in 10</span>
    </div>
  );
}

function WinningSection() {
  return (
    <Card className="flex flex-col gap-5 p-5">
      <p className="text-sm text-muted">Comparing the two players in the same role, in the same game. In how many games the winner…</p>
      {WINNING.map((row) => (
        <div key={row.key} className="flex flex-col gap-2">
          <p className="text-sm font-bold text-soft">…{row.text}</p>
          <IconArray
            share={winnerShare(row.key, row.less)}
            label={`The winner ${row.text}`}
            icon={(lit, index) => (
              <Trophy key={index} className={cn("size-5", lit ? "text-stat-gold" : "text-white/15")} />
            )}
          />
        </div>
      ))}
    </Card>
  );
}

/** One-part donut (0-100): the jungle/support duo's share in setting up objectives. */
function Donut({ value, tier, name }: { value: number; tier: string; name: string }) {
  const radius = 34;
  const circumference = 2 * Math.PI * radius;
  const color = tier === "CHALLENGER" ? palette.primary : GOLD_BAR;
  return (
    <figure className="flex flex-col items-center gap-2">
      <svg viewBox="0 0 88 88" className="size-28" role="img" aria-label={`${name}: ${formatPercent(value, 0)}`}>
        <circle cx="44" cy="44" r={radius} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="10" />
        <circle
          cx="44"
          cy="44"
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeDasharray={`${(value / 100) * circumference} ${circumference}`}
          transform="rotate(-90 44 44)"
        />
        <text x="44" y="49" textAnchor="middle" fill={palette.fg} fontSize="16" fontWeight="900">
          {formatPercent(value, 0)}
        </text>
      </svg>
      <figcaption className="flex items-center gap-1.5 text-xs text-muted">
        <RankEmblem tier={tier} size={16} /> {name}
      </figcaption>
    </figure>
  );
}

function ObjectiveSection() {
  const duo = tierValues(DUO_SHARE);
  return (
    <Card className="flex flex-col gap-5 p-5">
      <p className="text-sm text-muted">Out of 10 objectives (dragons, grubs, heralds and barons), the team that took it was the one that…</p>
      {OBJECTIVES.map((row) => (
        <div key={row.key} className="flex flex-col gap-2">
          <p className="text-sm font-bold text-soft">…{row.text}</p>
          <IconArray
            share={objectiveShare(row.key)}
            label={`The team that ${row.text}`}
            icon={(lit, index) => (
              <img
                key={index}
                src={`${OBJECTIVE_ICONS}/dragon.png`}
                alt=""
                loading="lazy"
                decoding="async"
                width={20}
                height={20}
                className={cn("size-5", !lit && "opacity-20 grayscale")}
              />
            )}
          />
        </div>
      ))}
      <div className="mt-2 border-t border-line pt-5">
        <p className="mb-4 text-sm font-bold text-soft">Who does the preparation? Share done by the jungler and the support.</p>
        <div className="flex justify-around">
          <Donut value={duo[0] ?? 0} tier="GOLD" name="Gold" />
          <Donut value={duo[duo.length - 1] ?? 0} tier="CHALLENGER" name="Challenger" />
        </div>
      </div>
    </Card>
  );
}

/** Top, mid and ADC: missed last hits (Gold against Challenger) and the hit rate. */
function LastHitSection() {
  return (
    <Card className="grid gap-8 p-5 md:grid-cols-3 md:gap-6">
      {LANERS.map(({ role, name }) => {
        const hit = tierValues(accuracy(role));
        return (
          <div key={role} className="flex flex-col gap-3">
            <p className="flex items-center gap-2 text-sm font-black text-text">
              <RoleIcon role={role} size={18} />
              {name}
            </p>
            <Versus metric={missed(role)} />
            <p className="text-xs text-muted">
              Minions taken when in range:{" "}
              <span className="font-bold text-text tabular-nums">
                {formatValue(hit[0] ?? 0, accuracy(role))} → {formatValue(hit[hit.length - 1] ?? 0, accuracy(role))}
              </span>
            </p>
          </div>
        );
      })}
    </Card>
  );
}

// difference: where the rest has more. Violet and not blue or red, which are the teams (ΔE 37.6 with the acid in deuteranopia)
const MORE_BELOW = categorical.indigo;

/**
 * A heatmap over the minimap, cell by cell. With negative values (the difference between two groups) it paints
 * those cells in `MORE_BELOW`. `scale` is the value that is seen at full intensity.
 */
function HeatMap({ values, scale, label, tip }: { values: number[]; scale: number; label: string; tip: (value: number) => string }) {
  const blur = useId();
  const { side, cells } = stats.map_wards;
  const size = side / cells;
  const [x0, x1] = MINIMAP.x;
  const [z0, z1] = MINIMAP.z;
  return (
    <div className="relative aspect-square overflow-hidden border border-line bg-ink">
      <img src={MINIMAP.src} alt="" loading="lazy" decoding="async" className="absolute inset-0 size-full brightness-[0.25] grayscale" />
      {/* and upward: the game's z grows toward the red base, which on the minimap is at the top */}
      <svg
        viewBox={`${x0} ${-z1} ${x1 - x0} ${z1 - z0}`}
        preserveAspectRatio="none"
        className="absolute inset-0 size-full"
        role="img"
        aria-label={label}
      >
        <filter id={blur} x="-5%" y="-5%" width="110%" height="110%">
          <feGaussianBlur stdDeviation={size * 0.5} />
        </filter>
        <g filter={`url(#${blur})`}>
          {values.map((value, index) =>
            value !== 0 ? (
              <rect
                key={index}
                x={(index % cells) * size}
                y={-(Math.floor(index / cells) + 1) * size}
                width={size}
                height={size}
                fill={value > 0 ? palette.primary : MORE_BELOW}
                fillOpacity={Math.min(1, Math.abs(value) / scale)}
              >
                <title>{tip(value)}</title>
              </rect>
            ) : null,
          )}
        </g>
      </svg>
      <span className="pointer-events-none absolute bottom-[14%] left-[5%] text-xs font-black tracking-caps text-stat-blue uppercase">
        Blue side
      </span>
      <span className="pointer-events-none absolute top-[14%] right-[5%] text-xs font-black tracking-caps text-stat-red uppercase">
        Red side
      </span>
    </div>
  );
}

/** The value below which the `q` of the cells with something falls: the hottest saturates and the rest can be told apart. */
function quantile(values: number[], q: number): number {
  const sorted = values.map(Math.abs).filter((value) => value > 0).sort((a, b) => a - b);
  return sorted[Math.floor(q * (sorted.length - 1))] ?? 1;
}

function MapTitle({ tiers, name }: { tiers: string[]; name: string }) {
  return (
    <figcaption className="flex min-h-[26px] items-center gap-2 text-sm font-black text-text">
      <span className="flex -space-x-1.5" aria-hidden="true">
        {tiers.map((tier) => (
          <RankEmblem key={tier} tier={tier} size={22} />
        ))}
      </span>
      {name}
    </figcaption>
  );
}

const LOW_TIERS = ["GOLD", "PLATINUM", "EMERALD", "DIAMOND", "MASTER"];
const HIGH_TIERS = ["GRANDMASTER", "CHALLENGER"];

const TEAMS: { team: Team; name: string; enemy: string }[] = [
  { team: "100", name: "Blue team", enemy: "red" },
  { team: "200", name: "Red team", enemy: "blue" },
];

function WardSection() {
  const [team, setTeam] = useState<Team>("100");
  const enemy = TEAMS.find((option) => option.team === team)?.enemy ?? "red";
  const high = stats.map_wards.high[team];
  const rest = stats.map_wards.rest[team];
  const groups: { group: WardGroup; tiers: string[]; name: string }[] = [
    { group: rest, tiers: LOW_TIERS, name: "Gold to Master" },
    { group: high, tiers: HIGH_TIERS, name: "Grandmaster & Challenger" },
  ];
  // the same scale in both: what is compared is where, not how much
  const scale = quantile([...high.squares, ...rest.squares], 0.97);
  const difference = high.squares.map((value, index) => value - (rest.squares[index] ?? 0));
  const percent = (value: number) => formatPercent(Math.abs(value) / 100, 1);
  return (
    <Card className="flex flex-col gap-6 p-5">
      <div role="group" aria-label="Team" className="flex flex-wrap gap-1.5">
        {TEAMS.map((option) => (
          <button
            key={option.team}
            type="button"
            aria-pressed={option.team === team}
            onClick={() => setTeam(option.team)}
            className={cn(
              "cursor-pointer border px-3 py-1.5 text-xs font-bold transition-colors",
              option.team === team ? "border-acid bg-acid/15 text-acid" : "border-line text-muted hover:text-text",
            )}
          >
            {option.name}
          </button>
        ))}
      </div>
      <div className="grid gap-6 md:grid-cols-3">
        {groups.map(({ group, tiers, name }) => (
          <figure key={name} className="flex flex-col gap-3">
            <MapTitle tiers={tiers} name={name} />
            <HeatMap
              values={group.squares}
              scale={scale}
              label={`${name}: ${formatPercent(enemyHalfShare(group, team) * 100, 0)} of wards on the ${enemy} side of the map`}
              tip={(value) => `${percent(value)} of their wards`}
            />
            <p className="text-sm text-muted">
              <span className="font-black text-text tabular-nums">{formatPercent(enemyHalfShare(group, team) * 100, 0)}</span>{" "}
              of their wards on the {enemy} side.
            </p>
          </figure>
        ))}
        <figure className="flex flex-col gap-3">
          <figcaption className="flex min-h-[26px] items-center text-sm font-black text-text">What changes</figcaption>
          <HeatMap
            values={difference}
            scale={quantile(difference, 0.95)}
            label="Where Grandmaster and Challenger players ward more, and where the tiers below ward more"
            tip={(value) => `${percent(value)} of the wards more in ${value > 0 ? "Grandmaster & Challenger" : "Gold to Master"}`}
          />
          <p className="flex flex-col gap-1 text-sm text-muted">
            <span className="flex items-center gap-2">
              <span className="size-2.5 shrink-0 bg-acid" aria-hidden="true" /> More wards in Grandmaster & Challenger
            </span>
            <span className="flex items-center gap-2">
              <span className="size-2.5 shrink-0" style={{ background: MORE_BELOW }} aria-hidden="true" /> More wards
              from Gold to Master
            </span>
          </p>
        </figure>
      </div>
      <p className="border-t border-line pt-4 text-xs text-muted">
        Every ward of the whole game placed by the chosen team, where it really is: the blue base is bottom-left, the
        red base top-right. The first two maps share one scale: the brighter the spot, the bigger the share of wards
        placed there.
      </p>
    </Card>
  );
}

function MythCard({ myth }: { myth: (typeof MYTHS)[number] }) {
  const values = myth.metric ? tierValues(myth.metric) : null;
  const Icon = myth.icon ?? Equal;
  return (
    <Card className="flex flex-col gap-3 p-5">
      <span className="grid size-10 place-items-center rounded-full bg-white/[0.06] text-soft">
        <Icon className="size-5" aria-hidden="true" />
      </span>
      <h3 className="text-lg font-black text-text">{myth.title}</h3>
      {myth.metric && values ? (
        <p className="flex items-center gap-4 text-sm text-muted">
          <span className="flex items-center gap-1.5">
            <RankEmblem tier="GOLD" size={18} />
            <span className="font-bold text-text tabular-nums">{formatValue(values[0] ?? 0, myth.metric)}</span>
          </span>
          <span className="flex items-center gap-1.5">
            <RankEmblem tier="CHALLENGER" size={18} />
            <span className="font-bold text-text tabular-nums">{formatValue(values[values.length - 1] ?? 0, myth.metric)}</span>
          </span>
          <span className="text-xs">{myth.metric.label}</span>
        </p>
      ) : (
        <p className="text-sm font-bold text-text">{formatPercent(objectiveShare("arrives") * 100, 0)} won by the team that arrived first</p>
      )}
      <p className="text-sm leading-relaxed text-muted">{myth.body}</p>
    </Card>
  );
}

// ── Views ────────────────────────────────────────────────────────────────────

export function Overview({ onDeepDive }: { onDeepDive: () => void }) {
  return (
    <div className="flex flex-col gap-14">
      <section>
        <SectionTitle eyebrow="The short version" title="6 habits of Challenger players">
          Compared with Gold players in the same role. None of them needs faster hands.
        </SectionTitle>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {HABITS.map((habit, index) => (
            <HabitCard key={habit.title} habit={habit} hue={HUES[index % HUES.length] ?? palette.primary} />
          ))}
        </div>
      </section>

      <section>
        <SectionTitle eyebrow="Last hits" title="40% fewer missed last hits">
          A missed last hit is a minion from your lane that dies within 700 units of you (about attack range) and
          you don&apos;t get the gold: you were right there. Minions lost while dead, in base or somewhere else
          don&apos;t count. It improves in every tier, and it&apos;s a skill that climbs rather than one that wins a
          single game: in the same lane, winner and loser miss about as many.
        </SectionTitle>
        <LastHitSection />
      </section>

      <section>
        <SectionTitle eyebrow="Tier by tier" title="The climb, step by step">
          Most habits improve a little with every tier. Pick one to see how it changes from Gold to Challenger.
        </SectionTitle>
        <ClimbChart />
      </section>

      <section>
        <SectionTitle eyebrow="Wave control" title="After pushing a wave, what do they do?">
          Pushing your wave into the enemy tower gives you a few free seconds. Challenger players spend them somewhere
          else on the map.
        </SectionTitle>
        <PushChart />
      </section>

      <section className="grid gap-10 xl:grid-cols-2 xl:gap-6">
        <div>
          <SectionTitle eyebrow="Winning" title="What the winner does more" />
          <WinningSection />
        </div>
        <div>
          <SectionTitle eyebrow="Objectives" title="Who takes the dragon?" />
          <ObjectiveSection />
        </div>
      </section>

      <section>
        <SectionTitle eyebrow="Vision" title="Where the wards go">
          Below Grandmaster, vision piles up on the dragon side of the map: the bot river and bot lane. Grandmaster and
          Challenger players spread it towards the middle. Pick a team to see its wards where they really are; the
          third map shows only the difference.
        </SectionTitle>
        <WardSection />
      </section>

      <section>
        <SectionTitle eyebrow="Myths" title="Common beliefs, checked">
          Things people blame for losing. From Gold to Challenger, the data says otherwise.
        </SectionTitle>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {MYTHS.map((myth) => (
            <MythCard key={myth.title} myth={myth} />
          ))}
        </div>
      </section>

      <Card className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between">
        <p className="max-w-3xl text-sm leading-relaxed text-muted">
          <strong className="text-text">How we measured it.</strong> Ranked games from EUW, from Gold to Challenger,
          decoded second by second from their replay files. Every number is an average for that tier. These
          are patterns, not rules: players who are already ahead also push and roam more.
        </p>
        <button
          type="button"
          onClick={onDeepDive}
          className="shrink-0 cursor-pointer border border-line-button px-4 py-2 text-xs font-black tracking-[0.1em] text-text uppercase hover:border-acid hover:text-acid"
        >
          Every number
        </button>
      </Card>
    </div>
  );
}

export function ByRole({ role, onRole }: { role: Role; onRole: (role: Role) => void }) {
  const { intro, tips } = ROLE_TIPS[role];
  const name = ROLES.find((option) => option.role === role)?.name ?? role;
  return (
    <div className="flex flex-col gap-6">
      <div role="group" aria-label="Role" className="flex flex-wrap gap-2">
        {ROLES.map((option) => (
          <button
            key={option.role}
            type="button"
            aria-pressed={option.role === role}
            onClick={() => onRole(option.role)}
            className={cn(
              "flex cursor-pointer items-center gap-2 border px-3.5 py-2 text-sm font-bold transition-colors",
              option.role === role ? "border-acid bg-acid/15 text-acid" : "border-line text-muted hover:text-text",
            )}
          >
            <RoleIcon role={option.role} size={18} />
            {option.name}
          </button>
        ))}
      </div>
      <SectionTitle eyebrow={name} title={`How Challenger ${name.toLowerCase()} players play`}>
        {intro}
      </SectionTitle>
      <div className="grid gap-4 md:grid-cols-3">
        {tips.map((tip, index) => (
          <Card key={tip.title} className="flex flex-col gap-4 p-5">
            <div className="flex items-center justify-between">
              <span
                className="grid size-9 place-items-center rounded-full text-sm font-black"
                style={{ background: `${HUES[index] ?? palette.primary}22`, color: HUES[index] ?? palette.primary }}
              >
                {index + 1}
              </span>
              <ChangeBadge metric={tip.metric} />
            </div>
            <h3 className="text-lg font-black text-text">{tip.title}</h3>
            <Versus metric={tip.metric} />
            <p className="text-sm leading-relaxed text-muted">{tip.body}</p>
          </Card>
        ))}
      </div>
    </div>
  );
}
