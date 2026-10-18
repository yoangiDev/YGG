import {
  Binoculars,
  Castle,
  Layers,
  Compass,
  Eye,
  Flag,
  Flame,
  Footprints,
  House,
  MapPin,
  Scale,
  ShieldAlert,
  Skull,
  Swords,
  Target,
  Timer,
  Repeat,
  Trees,
  TrendingDown,
  Unlink,
  Video,
  Zap,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import {
  Area,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { ChartTooltipBox } from "@/components/charts/ChartTooltip";
import { ChampionIcon } from "@/components/player/PlayerBits";
import { cn } from "@/lib/cn";
import { MINIMAP } from "@/lib/ddragon";
import { formatNumber, formatSigned } from "@/lib/format";
import { palette } from "@/lib/palette";

import {
  type Game,
  isSupportOpening,
  KINDS,
  type Located,
  MAP_VIEWBOX,
  mapPoint,
  type MapSide,
  type MomentKind,
  momentKey,
  type OpeningState,
  type Play,
  playedAt,
  type Review,
  type SupportOpening,
  TONE_COLOR,
  type Tone,
  wpAt,
} from "./premiumData";

export const KIND_ICONS: Record<MomentKind, LucideIcon> = {
  death: Skull,
  camps: Trees,
  fog: Eye,
  gank: Target,
  fight: Swords,
  objective: Flag,
  swing: TrendingDown,
  flash: Zap,
  back: House,
  roam: Footprints,
  opening: Compass,
  play: Scale,
  pair: Unlink,
  ward: Binoculars,
  setup: Timer,
  trade: Repeat,
  damage: Flame,
  dive: ShieldAlert,
  tower: Castle,
  plate: Layers,
};

const TONES: { key: Tone | "all"; label: string }[] = [
  { key: "bad", label: "Mistakes" },
  { key: "good", label: "Good plays" },
  { key: "all", label: "Everything" },
];
const RADIUS = [0, 200, 250, 320]; // by severity, in map units (the minimap measures ~15,000)
const HIT_RADIUS = 520; // each point's click zone: ~28 px on a 400 map, which is more than a 10 px point

interface ExplorerProps {
  game: Game;
  gameIndex: number;
  /** The moments of that match, in order (premiumData.gameMoments). */
  moments: Located[];
  review: Review | null;
  selected: string | null;
  onSelect: (key: string) => void;
}

/** The map of a match's moments: where each mistake happened, at what minute and what it cost. */
export function MomentExplorer({ game, gameIndex, moments, review, selected, onSelect }: ExplorerProps) {
  const [tone, setTone] = useState<Tone | "all">("all");
  const [kind, setKind] = useState<MomentKind | null>(null);
  // the one chosen from outside (a pattern, a lesson) takes precedence over this match's filters
  const current = moments.find((m) => m.key === selected);

  const filtered = moments
    .filter((m) => !kind || m.moment.kind === kind)
    .filter((m) => tone === "all" || m.moment.tone === tone);
  const kindsHere = [...new Set(moments.map((m) => m.moment.kind))];

  return (
    <div className="flex flex-col gap-4">
      <MomentStatus text={current ? `${current.moment.clock}, ${current.moment.title}` : ""} />
      <MomentFilters tone={tone} onTone={setTone} kind={kind} onKind={setKind} kinds={kindsHere} />

      <div className="grid gap-4 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
        <MomentMap moments={filtered} current={current} onSelect={onSelect} />
        <div className="flex min-w-0 flex-col gap-3">
          {current ? (
            <MomentDetail located={current} note={review?.moment_notes.find((n) => n.moment === current.key)?.note} />
          ) : (
            <p className="border border-dashed border-line p-4 text-sm text-muted">
              Pick a moment on the map or in the list to see what happened, what it cost and the exact minute to rewatch.
            </p>
          )}
          <MomentList moments={filtered} selected={selected} onSelect={onSelect} />
        </div>
      </div>

      <GameTimeline
        game={game}
        gameIndex={gameIndex}
        note={review?.game_notes.find((n) => n.match_id === game.match_id)?.note}
        selected={selected}
        onSelect={onSelect}
      />
    </div>
  );
}

/** The moment filters: by tone (mistakes, successes) and by kind. */
export function MomentFilters({
  tone,
  onTone,
  kind,
  onKind,
  kinds,
}: {
  tone: Tone | "all";
  onTone: (tone: Tone | "all") => void;
  kind: MomentKind | null;
  onKind: (kind: MomentKind | null) => void;
  kinds: MomentKind[];
}) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <div role="group" aria-label="Show" className="mr-2 flex overflow-hidden rounded-full border border-line">
        {TONES.map((t) => (
          <button
            key={t.key}
            type="button"
            aria-pressed={tone === t.key}
            onClick={() => onTone(t.key)}
            className={cn(
              "cursor-pointer px-3 py-1.5 text-xs font-bold transition",
              tone === t.key ? "bg-acid text-on-acid" : "text-muted hover:text-text",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>
      <FilterChip active={kind === null} onClick={() => onKind(null)}>
        All kinds
      </FilterChip>
      {kinds.map((k) => {
        const Icon = KIND_ICONS[k];
        return (
          <FilterChip key={k} active={kind === k} onClick={() => onKind(kind === k ? null : k)}>
            <Icon className="size-3.5" aria-hidden="true" />
            {KINDS[k]}
          </FilterChip>
        );
      })}
    </div>
  );
}

export function FilterChip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        "inline-flex cursor-pointer items-center gap-1.5 rounded-full border px-2.5 py-1.5 text-xs font-bold transition",
        active ? "border-acid/70 bg-acid/10 text-text" : "border-line text-muted hover:border-line-button hover:text-text",
      )}
    >
      {children}
    </button>
  );
}

export function MomentMap({ moments, current, onSelect }: { moments: Located[]; current?: Located; onSelect: (key: string) => void }) {
  const located = (m: Located) => m.moment.x !== null && m.moment.z !== null;
  // the chosen one is drawn even if the filters leave it out: removing it from the map when filtering is losing sight of where it happened
  const placed = moments.filter(located);
  if (current && located(current) && !placed.includes(current)) placed.push(current);
  const selected = current?.key ?? null;
  const bad = placed.filter((m) => m.moment.tone === "bad").length;
  return (
    <figure className="flex flex-col gap-2">
      <div className="relative aspect-square overflow-hidden border border-line bg-ink">
        <img src={MINIMAP.src} alt="" className="absolute inset-0 size-full brightness-[0.55] saturate-[0.6]" />
        <svg
          viewBox={MAP_VIEWBOX}
          preserveAspectRatio="none"
          className="absolute inset-0 size-full"
          role="img"
          aria-label={`Map of ${placed.length} moments, ${bad} of them mistakes. Pick one from the list.`}
        >
          {placed.map((m) => {
            const { cx, cy } = mapPoint(m.moment.x ?? 0, m.moment.z ?? 0);
            return (
              <g key={m.key} className="cursor-pointer" onClick={() => onSelect(m.key)}>
                <circle cx={cx} cy={cy} r={HIT_RADIUS} fill="transparent" />
                <circle
                  cx={cx}
                  cy={cy}
                  r={RADIUS[m.moment.severity]}
                  fill={TONE_COLOR[m.moment.tone]}
                  fillOpacity={m.key === selected ? 1 : 0.72}
                  stroke={palette.bg}
                  strokeWidth={50}
                  pointerEvents="none"
                />
                <title>{`${m.moment.clock} · ${m.moment.title}`}</title>
              </g>
            );
          })}
          {current && located(current) && (
            <g pointerEvents="none">
              {current.moment.camp_spots?.map(([x, z], i) => {
                const spot = mapPoint(x, z);
                return <circle key={i} cx={spot.cx} cy={spot.cy} r={260} fill="none" stroke={palette.gold} strokeWidth={70} strokeDasharray="120 90" />;
              })}
              {current.moment.objective_spot && (
                <circle
                  cx={mapPoint(...current.moment.objective_spot).cx}
                  cy={mapPoint(...current.moment.objective_spot).cy}
                  r={900}
                  fill="none"
                  stroke={palette.blue}
                  strokeWidth={70}
                  strokeDasharray="160 110"
                />
              )}
              <circle
                cx={mapPoint(current.moment.x ?? 0, current.moment.z ?? 0).cx}
                cy={mapPoint(current.moment.x ?? 0, current.moment.z ?? 0).cy}
                r={620}
                fill="none"
                stroke={palette.primary}
                strokeWidth={90}
                className="animate-pulse"
              />
            </g>
          )}
        </svg>
        {current && (
          <span className="pointer-events-none absolute top-2 left-2 bg-ink/85 px-2 py-1 text-xs font-bold text-acid tabular-nums">
            {current.moment.clock} · {current.moment.where}
          </span>
        )}
      </div>
      <figcaption className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
        {(["bad", "good", "neutral"] as const).map((t) => (
          <span key={t} className="inline-flex items-center gap-1.5">
            <span aria-hidden="true" className="size-2.5 rounded-full" style={{ background: TONE_COLOR[t] }} />
            {t === "bad" ? "Mistake" : t === "good" ? "Good play" : "Trade-off"}
          </span>
        ))}
        <span>Bigger dot = costlier</span>
      </figcaption>
    </figure>
  );
}

function Cost({ gold, value }: { gold?: number; value?: number }) {
  if (gold) {
    return (
      <span className={cn("tabular-nums", gold < 0 ? "text-stat-red" : "text-stat-green")}>{formatSigned(gold, 0)} g</span>
    );
  }
  if (value) {
    return <span className={cn("tabular-nums", value < 0 ? "text-stat-red" : "text-stat-green")}>{formatSigned(value, 1)} WP</span>;
  }
  return null;
}

export function MomentList({
  moments,
  selected,
  onSelect,
  renderBadge,
}: {
  moments: Located[];
  selected: string | null;
  onSelect: (key: string) => void;
  /** What goes in the first column instead of the kind's icon (a single match's page puts the verdict). */
  renderBadge?: (located: Located) => React.ReactNode;
}) {
  const refs = useRef(new Map<string, HTMLButtonElement>());
  const list = useRef<HTMLOListElement>(null);
  const fromList = useRef(false);
  // the chosen one, in view within the list; scrollIntoView would also move the page, and on opening the analysis it
  // would take it here on its own. If the click was in the list itself nothing moves: the list would slide from under the
  // cursor and the next click would land on a different moment
  useEffect(() => {
    const box = list.current;
    const item = selected ? refs.current.get(selected) : undefined;
    if (fromList.current) {
      fromList.current = false;
      return;
    }
    if (!box || !item) return;
    const top = item.offsetTop;
    if (top < box.scrollTop || top + item.offsetHeight > box.scrollTop + box.clientHeight) {
      box.scrollTop = Math.max(0, top - box.clientHeight / 3);
    }
  }, [selected]);

  if (moments.length === 0) return <p className="text-sm text-muted">Nothing of this kind in this game.</p>;
  return (
    <ol ref={list} aria-label="Moments" className="relative max-h-[22rem] overflow-y-auto border border-line">
      {moments.map((m) => {
        const Icon = KIND_ICONS[m.moment.kind];
        const active = m.key === selected;
        return (
          <li key={m.key} className="border-b border-line/60 last:border-0">
            <button
              ref={(el) => {
                if (el) refs.current.set(m.key, el);
                else refs.current.delete(m.key);
              }}
              type="button"
              aria-current={active}
              onClick={() => {
                fromList.current = true;
                onSelect(m.key);
              }}
              className={cn(
                "grid w-full cursor-pointer items-center gap-2.5 border-l-2 px-3 text-left transition-colors",
                renderBadge ? "grid-cols-[1.5rem_2.75rem_minmax(0,1fr)_auto] py-2.5" : "grid-cols-[1.25rem_2.75rem_minmax(0,1fr)_auto] py-2",
                active ? "border-l-acid bg-acid/[0.07]" : "border-l-transparent hover:bg-white/[0.03]",
              )}
            >
              {renderBadge ? renderBadge(m) : <Icon className="size-4" style={{ color: TONE_COLOR[m.moment.tone] }} aria-hidden="true" />}
              <span className="text-xs font-bold text-soft tabular-nums">{m.moment.clock}</span>
              <span className="flex min-w-0 items-center gap-2">
                <span className="truncate text-sm text-text">{m.moment.title}</span>
              </span>
              <span className="flex items-center gap-2 text-xs">
                <Cost gold={m.moment.gold} value={m.moment.value} />
                <Severity level={m.moment.severity} />
              </span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}

function Severity({ level }: { level: number }) {
  return (
    <span className="flex gap-0.5" aria-label={`Impact ${level} of 3`}>
      {[1, 2, 3].map((i) => (
        <span key={i} aria-hidden="true" className={cn("h-2.5 w-1", i <= level ? "bg-stat-gold" : "bg-white/10")} />
      ))}
    </span>
  );
}

/** Which moment has been chosen, for screen readers: a sentence in a region that already exists when it changes. */
export function MomentStatus({ text }: { text: string }) {
  return (
    <p role="status" className="sr-only">
      {text}
    </p>
  );
}

/** `single`: a single match's page, where there is no «match 1» to name. */
export function MomentDetail({
  located,
  note,
  single = false,
  verdict,
  extra,
  className,
}: {
  className?: string;
  located: Located;
  note?: string;
  single?: boolean;
  /** The moment's verdict, which replaces the icon of its kind next to the title. */
  verdict?: React.ReactNode;
  /** Something specific to whoever renders it (the chain of consequences), after the moment's labels. */
  extra?: React.ReactNode;
}) {
  const { moment } = located;
  const Icon = KIND_ICONS[moment.kind];

  return (
    <article className={cn("border border-line bg-panel-light/70 p-4", className)}>
      <div className="flex items-start gap-4">
        <div className="flex flex-col items-center">
          <span className="text-xl leading-none font-black text-text tabular-nums">{moment.clock}</span>
          <span className="microtext mt-1 text-xs text-subtle">in-game</span>
        </div>
        <div className="min-w-0 flex-1">
          <p className="flex items-center gap-2 text-base font-black text-text">
            {verdict ?? <Icon className="size-4 shrink-0" style={{ color: TONE_COLOR[moment.tone] }} aria-hidden="true" />}
            {moment.title}
          </p>
          {moment.where && (
            <p className="mt-1 flex items-center gap-1.5 text-xs text-soft">
              <MapPin className="size-3.5 text-acid" aria-hidden="true" />
              {moment.where}
            </p>
          )}
        </div>
      </div>

      <p className="mt-3 text-sm leading-relaxed text-soft">{moment.text}</p>

      <div className="mt-3 flex flex-wrap gap-2 text-xs">
        {moment.gold ? (
          <Badge tone={moment.gold < 0 ? "bad" : "good"}>
            {moment.gold < 0 ? "Cost" : "Gained"} {formatNumber(Math.abs(moment.gold), 0)} gold
          </Badge>
        ) : null}
        {moment.wp_before !== undefined && moment.wp_after !== undefined && moment.wp_before !== moment.wp_after && (
          <Badge tone={moment.wp_after < moment.wp_before ? "bad" : "good"}>
            Win chance {moment.wp_before}% → {moment.wp_after}%
          </Badge>
        )}
        {moment.dead_for ? <Badge tone="neutral">Dead {moment.dead_for} s</Badge> : null}
        {moment.tags?.map((tag) => (
          <Badge key={tag} tone="neutral">
            {tag}
          </Badge>
        ))}
      </div>

      {extra}

      {moment.opening &&
        (isSupportOpening(moment.opening) ? <SupportOpeningCard state={moment.opening} /> : <OpeningCard state={moment.opening} />)}
      {moment.play && <PlayCard play={moment.play} />}

      {note && (
        <div className="mt-3 border border-acid/40 bg-acid/[0.06] p-3">
          <p className="microtext text-xs text-acid">Coach</p>
          <p className="mt-1 text-sm leading-relaxed text-text">{note}</p>
        </div>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-3 border-t border-line pt-3">
        <p className="flex min-w-0 flex-1 items-center gap-1.5 text-xs text-muted">
          <Video className="size-3.5 shrink-0" aria-hidden="true" />
          Rewatch it: open {single ? "your recording" : "your recording of this game"} at {moment.clock} of game time
          {moment.end ? ` (it lasts until ${Math.floor(moment.end / 60)}:${String(Math.floor(moment.end % 60)).padStart(2, "0")})` : ""}.
        </p>
      </div>
    </article>
  );
}

function Badge({ tone, children }: { tone: Tone; children: React.ReactNode }) {
  return (
    <span
      className={cn(
        "rounded-full border px-2.5 py-0.5 font-bold",
        tone === "bad" && "border-stat-red/40 bg-stat-red/10 text-stat-red",
        tone === "good" && "border-stat-green/40 bg-stat-green/10 text-stat-green",
        tone === "neutral" && "border-line bg-white/[0.03] text-soft",
      )}
    >
      {children}
    </span>
  );
}

interface TimelinePoint {
  minute: number;
  wp: number | null;
  gold: number | null;
}

/** A match from start to finish: their team's WP and its gold lead, with each moment where it happened. */
export function GameTimeline({
  game,
  gameIndex,
  note,
  selected,
  onSelect,
  single = false,
}: {
  game: Game;
  gameIndex: number;
  note?: string;
  selected: string | null;
  onSelect: (key: string) => void;
  /** A single match's page: its header already states champion and result, and there is no «match 1». */
  single?: boolean;
}) {
  const series = game.series;
  const points: TimelinePoint[] = series
    ? series.t.map((t, i) => ({ minute: t / 60, wp: wpAt(game, t), gold: series.team_gold[i] ?? null }))
    : (game.wp ?? []).map(([t, wp]) => ({ minute: t / 60, wp: Math.round(wp * 100), gold: null }));
  const dots = (game.moments ?? []).map((m) => ({
    minute: m.t / 60,
    wp: wpAt(game, m.t) ?? 50,
    key: momentKey(game.match_id, m.id),
    tone: m.tone,
    title: `${m.clock} · ${m.title}`,
  }));
  const current = dots.find((d) => d.key === selected);
  const gold14 = game.numbers?.gold_diff_14;

  return (
    <section aria-label={single ? "Game timeline" : `Game ${gameIndex + 1} timeline`} className="border border-line p-4">
      {!single && (
        <header className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <ChampionIcon name={game.champion} size={28} />
          <h3 className="text-sm font-black text-text">
            Game {gameIndex + 1}: {game.champion}
            {game.opponent ? ` vs ${game.opponent}` : ""}
          </h3>
          <span className={cn("text-sm font-bold", game.win ? "text-stat-green" : "text-stat-red")}>{game.win ? "Win" : "Loss"}</span>
          <span className="text-xs text-muted tabular-nums">
            {formatNumber(game.stats.kills ?? 0, 0)}/{formatNumber(game.stats.deaths ?? 0, 0)}/{formatNumber(game.stats.assists ?? 0, 0)}
            {gold14 !== null && gold14 !== undefined ? ` · ${formatSigned(gold14, 0)} gold vs opponent at 14:00` : ""}
            {playedAt(game) ? ` · ${playedAt(game)}` : ""}
          </span>
        </header>
      )}
      {note && <p className={cn("text-sm text-soft", !single && "mt-2")}>{note}</p>}
      <div
        className="mt-3 h-56"
        role="img"
        aria-label={`Your team's win chance and gold lead in ${single ? "this game" : `game ${gameIndex + 1}`}, with ${dots.length} moments marked.`}
      >
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={points} margin={{ top: 8, right: 4, bottom: 0, left: -18 }}>
            <XAxis
              dataKey="minute"
              type="number"
              domain={[0, "dataMax"]}
              tickFormatter={(m: number) => `${Math.round(m)}'`}
              stroke={palette.muted}
              fontSize={11}
            />
            <YAxis yAxisId="wp" domain={[0, 100]} ticks={[0, 50, 100]} tickFormatter={(v: number) => `${v}%`} stroke={palette.muted} fontSize={11} />
            <YAxis
              yAxisId="gold"
              orientation="right"
              tickFormatter={(v: number) => `${v >= 0 ? "+" : ""}${Math.round(v / 1000)}k`}
              stroke={palette.muted}
              fontSize={11}
              width={36}
            />
            <ReferenceLine yAxisId="wp" y={50} stroke="rgba(255,255,255,0.15)" strokeDasharray="4 4" />
            <Area
              yAxisId="gold"
              dataKey="gold"
              type="monotone"
              stroke={palette.primary}
              strokeOpacity={0.6}
              fill={palette.primary}
              fillOpacity={0.1}
              isAnimationActive={false}
              connectNulls
            />
            <Line yAxisId="wp" dataKey="wp" type="monotone" stroke={palette.fg} strokeWidth={2} dot={false} isAnimationActive={false} connectNulls />
            <Scatter
              yAxisId="wp"
              data={dots}
              dataKey="wp"
              isAnimationActive={false}
              shape={(props: { cx?: number; cy?: number; payload?: (typeof dots)[number] }) => (
                <g className="cursor-pointer" onClick={() => props.payload && onSelect(props.payload.key)}>
                  <circle cx={props.cx} cy={props.cy} r={14} fill="transparent" />
                  <circle
                    cx={props.cx}
                    cy={props.cy}
                    r={props.payload?.key === selected ? 7 : 5}
                    fill={props.payload ? TONE_COLOR[props.payload.tone] : palette.gray}
                    stroke={props.payload?.key === selected ? palette.primary : palette.bg}
                    strokeWidth={2}
                    pointerEvents="none"
                  />
                </g>
              )}
            />
            {current && <ReferenceLine yAxisId="wp" x={current.minute} stroke={palette.primary} strokeDasharray="3 3" />}
            <Tooltip
              content={(props) => {
                if (!props.active) return null;
                const row = props.payload[0]?.payload as (TimelinePoint & { title?: string }) | undefined;
                if (!row) return null;
                return (
                  <ChartTooltipBox title={row.title ?? `${Math.floor(row.minute)}:${String(Math.round((row.minute % 1) * 60)).padStart(2, "0")}`}>
                    {row.wp !== null && <span>{row.wp}% to win</span>}
                    {typeof row.gold === "number" && <span>{formatSigned(row.gold, 0)} team gold</span>}
                  </ChartTooltipBox>
                );
              }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-1 text-xs text-muted">
        White: your team&apos;s chance to win. Green area: your team&apos;s gold lead. Dots: the moments of this game; click one.
      </p>
    </section>
  );
}

const OBJECTIVE_NAMES: Record<string, string> = { Dragon: "Dragon", Voidgrub: "Voidgrubs", Herald: "Herald", Baron: "Baron" };

/** The map when the jungler left base: where the people above would open, and each half with what was in it. */
function OpeningCard({ state }: { state: OpeningState }) {
  const top = state.prob_top;
  const rival = state.rival;
  return (
    <section aria-label="Map when you left base" className="mt-3 border border-line bg-ink/40 p-3">
      <p className="microtext text-xs text-subtle">Map when you left base</p>
      {top !== null && (
        <div className="mt-2">
          <div className="flex justify-between text-xs font-bold">
            <span className="text-soft">High elo opens top {Math.round(top * 100)}%</span>
            <span className="text-soft">bot {Math.round((1 - top) * 100)}%</span>
          </div>
          <div className="relative mt-1 flex h-2 overflow-hidden rounded-full bg-white/10" aria-hidden="true">
            <span className="h-full bg-stat-blue/70" style={{ width: `${top * 100}%` }} />
            <span className="h-full flex-1 bg-stat-gold/60" />
          </div>
          <p className="mt-1 text-xs text-muted">
            You opened <span className="font-bold text-text">{state.opens}</span>
            {state.clear ? (
              (top >= 0.5) === (state.opens === "top") ? (
                <span className="text-stat-green"> · the same read</span>
              ) : (
                <span className="text-stat-red"> · against a clear read</span>
              )
            ) : (
              <span> · no clear best side</span>
            )}
          </p>
        </div>
      )}
      <div className="mt-2 grid gap-2 sm:grid-cols-2">
        {(["top", "bot"] as const).map((side) => (
          <SideColumn
            key={side}
            side={side}
            data={state[side]}
            chosen={state.opens === side}
            preferred={top !== null && state.clear && (top >= 0.5) === (side === "top")}
          />
        ))}
      </div>
      <p className="mt-2 text-xs text-muted">
        Their jungler:{" "}
        {rival.ago >= 600
          ? "not seen for a long time"
          : rival.ago < 2
            ? `in sight, ${rival.seen} side`
            : `last seen ${rival.seen} side ${Math.round(rival.ago)} s before`}
        {rival.cleared !== "nothing" && rival.cleared ? ` · last cleared ${rival.cleared} side` : ""}
      </p>
    </section>
  );
}

function SideColumn({ side, data, chosen, preferred }: { side: "top" | "bot"; data: MapSide; chosen: boolean; preferred: boolean }) {
  const objectiveIn = data.objective ?? 600;
  const objectiveName = OBJECTIVE_NAMES[data.objective_which ?? ""] ?? (side === "bot" ? "Dragon" : "Voidgrubs/Herald");
  return (
    <div className={cn("border p-2 text-xs", chosen ? "border-acid/60 bg-acid/[0.04]" : "border-line")}>
      <p className="flex items-center justify-between font-bold text-text">
        <span className="uppercase">{side} side</span>
        <span className="flex gap-1">
          {chosen && <span className="bg-acid/20 px-1.5 text-xs text-acid">YOU</span>}
          {preferred && <span className="bg-stat-blue/20 px-1.5 text-xs text-stat-blue">HIGH ELO</span>}
        </span>
      </p>
      <dl className="mt-1.5 grid grid-cols-[auto_1fr] gap-x-2 gap-y-1 text-muted">
        <dt>Your camps</dt>
        <dd className="text-right text-soft tabular-nums">
          {data.gold_now ?? 0} g up · {data.gold_30 ?? 0} g in 30 s
        </dd>
        <dt>Their camps</dt>
        <dd className="text-right text-soft tabular-nums">{data.gold_rival ?? 0} g up</dd>
        <dt>{objectiveName}</dt>
        <dd className={cn("text-right tabular-nums", objectiveIn <= 0 ? "font-bold text-stat-gold" : "text-soft")}>
          {objectiveIn <= 0 ? "up" : objectiveIn <= 120 ? `in ${Math.round(objectiveIn)} s` : "later"}
        </dd>
        <dt>Scuttle</dt>
        <dd className="text-right text-soft">{data.crab ? "up" : "—"}</dd>
      </dl>
      <div className="mt-2 flex flex-col gap-1">
        <HealthRow label="Your lane" value={data.allies_alive ? data.health_ally : null} color={palette.green} />
        <HealthRow label="Their lane" value={data.rivals_alive ? data.health_rival : null} color={palette.red} />
        {data.no_flash_rival > 0 && <p className="text-stat-gold">{data.no_flash_rival} of them without Flash</p>}
        <WaveRow value={data.wave} />
      </div>
    </div>
  );
}

function HealthRow({ label, value, color }: { label: string; value: number | null; color: string }) {
  return (
    <div className="grid grid-cols-[4.5rem_1fr_2.5rem] items-center gap-2">
      <span className="text-muted">{label}</span>
      <span className="h-1.5 overflow-hidden rounded-full bg-white/10" aria-hidden="true">
        <span className="block h-full" style={{ width: `${(value ?? 0) * 100}%`, background: color }} />
      </span>
      <span className="text-right text-soft tabular-nums">{value === null ? "dead" : `${Math.round(value * 100)}%`}</span>
    </div>
  );
}

/** The wave between the two turrets: theirs on the left, the enemy's on the right. */
function WaveRow({ value }: { value: number }) {
  return (
    <div className="grid grid-cols-[4.5rem_1fr_auto] items-center gap-2">
      <span className="text-muted">Wave</span>
      <span className="relative h-1.5 rounded-full bg-gradient-to-r from-stat-blue/40 via-white/10 to-stat-red/40" aria-hidden="true">
        <span className="absolute top-1/2 size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-text" style={{ left: `${value * 100}%` }} />
      </span>
      <span className="text-right whitespace-nowrap text-soft">{value > 0.55 ? "pushing" : value < 0.45 ? "at yours" : "mid"}</span>
    </div>
  );
}

const LANE_STATES: Record<string, { label: string; tone: Tone }> = {
  crash: { label: "Wave just crashed into their tower", tone: "good" },
  pushed: { label: "Wave pushed to their side", tone: "good" },
  neutral: { label: "Wave in the middle", tone: "neutral" },
  "at their tower": { label: "Wave at your tower", tone: "neutral" },
  "slowpush rival": { label: "Their wave stacking against your ADC", tone: "bad" },
  "freeze rival": { label: "They hold the wave on their side", tone: "bad" },
  "without marksman": { label: "ADC not in lane", tone: "neutral" },
};

/** The marksman's lane when the support left base: where the people above would open, what the wave was like
 * and what came out. */
function SupportOpeningCard({ state }: { state: SupportOpening }) {
  const mid = state.prob_mid;
  const lane = LANE_STATES[state.lane.state] ?? { label: state.lane.state, tone: "neutral" as Tone };
  const recalled = state.recalled_on ? LANE_STATES[state.recalled_on] : undefined;
  const after = state.after;
  const came = [
    after.wards > 0 && `${after.wards} ward${after.wards > 1 ? "s" : ""} placed`,
    after.mid_backed && "their mid backed off",
    after.kills > 0 && `${after.kills} kill${after.kills > 1 ? "s" : ""} you took part in`,
    after.reaches_bot !== null && `with your ADC after ${Math.round(after.reaches_bot)} s`,
  ].filter((x): x is string => Boolean(x));
  return (
    <section aria-label="Bot lane when you left base" className="mt-3 border border-line bg-ink/40 p-3">
      <p className="microtext text-xs text-subtle">Bot lane when you left base</p>
      {mid !== null && (
        <div className="mt-2">
          <div className="flex justify-between text-xs font-bold">
            <span className="text-soft">High elo opens through mid {Math.round(mid * 100)}%</span>
            <span className="text-soft">straight to bot {Math.round((1 - mid) * 100)}%</span>
          </div>
          <div className="relative mt-1 flex h-2 overflow-hidden rounded-full bg-white/10" aria-hidden="true">
            <span className="h-full bg-stat-blue/70" style={{ width: `${mid * 100}%` }} />
            <span className="h-full flex-1 bg-stat-gold/60" />
          </div>
          <p className="mt-1 text-xs text-muted">
            You <span className="font-bold text-text">{state.opens === "mid" ? "opened through mid" : "went straight to bot"}</span>
            {state.clear ? (
              (mid >= 0.5) === (state.opens === "mid") ? (
                <span className="text-stat-green"> · the same read</span>
              ) : (
                <span className="text-stat-red"> · against a clear read</span>
              )
            ) : (
              <span> · no clear read here</span>
            )}
          </p>
        </div>
      )}
      <div className="mt-2 grid gap-2 sm:grid-cols-2">
        <div className="flex flex-col gap-1.5 border border-line p-2 text-xs">
          <p className="font-bold text-text uppercase">Your ADC&apos;s lane</p>
          <p
            className={cn(
              "font-bold",
              lane.tone === "bad" && "text-stat-red",
              lane.tone === "good" && "text-stat-green",
              lane.tone === "neutral" && "text-soft",
            )}
          >
            {lane.label}
          </p>
          <WaveRow value={state.lane.wave} />
          {recalled && (
            <p className="text-muted">
              When you recalled: <span className="text-soft">{recalled.label.toLowerCase()}</span>
            </p>
          )}
          <p className="text-muted">
            Minions: <span className="text-soft tabular-nums">{formatSigned(state.lane.minions, 0)}</span> for your side ·{" "}
            {state.lane.enemies} of their bot laners in lane
          </p>
          <HealthRow
            label={state.lane.adc_in_base ? "ADC (base)" : "Your ADC"}
            value={state.lane.adc_alive ? state.lane.adc_hp : null}
            color={palette.green}
          />
        </div>
        <div className="flex flex-col gap-1.5 border border-line p-2 text-xs">
          <p className="font-bold text-text uppercase">The next 90 seconds</p>
          {came.length > 0 ? (
            <ul className="flex flex-col gap-0.5 text-soft">
              {came.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          ) : (
            <p className="text-muted">Nothing on the map.</p>
          )}
          {after.adc_died && (
            <p className={after.adc_exposed ? "text-stat-gold" : "text-stat-red"}>
              {after.adc_exposed ? "ADC died past the middle of the lane: theirs to respect" : "ADC died"}
            </p>
          )}
        </div>
      </div>
    </section>
  );
}

/** The tally of a play with live camps: what each participant stopped farming and what they got out of it. */
function PlayCard({ play }: { play: Play }) {
  const sides = [
    { key: "ally", title: "Your side" },
    { key: "enemy", title: "Their side" },
  ] as const;
  return (
    <section aria-label="What the play cost and gave" className="mt-3 border border-line bg-ink/40 p-3">
      <p className="microtext text-xs text-subtle">What the play cost and gave</p>
      <dl className="mt-2 grid grid-cols-3 gap-2 text-center">
        <Figure label="Camps left up" value={`${formatNumber(play.camp_gold, 0)} g`} note={play.camps.join(", ")} />
        <Figure label="Clears pushed back" value={`${formatSigned(-play.cost_gold, 0)} g`} note={`${formatSigned(-play.cost_xp, 0)} XP`} tone="bad" />
        <Figure
          label="Net for your side"
          value={`${formatSigned(play.value, 0)} g`}
          note={`${formatSigned(play.net_gold, 0)} g · ${formatSigned(play.net_xp, 0)} XP`}
          tone={play.value >= 0 ? "good" : "bad"}
        />
      </dl>
      <div className="mt-2 grid gap-2 sm:grid-cols-2">
        {sides.map((side) => {
          const rows = play.ledger.filter((l) => l.side === side.key);
          return (
            <div key={side.key} className="border border-line p-2 text-xs">
              <p className="font-bold text-text uppercase">{side.title}</p>
              {rows.length === 0 ? (
                <p className="mt-1 text-muted">Nobody involved.</p>
              ) : (
                <ul className="mt-1 flex flex-col gap-1">
                  {rows.map((row) => (
                    <li key={row.champion} className="grid grid-cols-[1.125rem_minmax(0,1fr)_auto_3.5rem] items-center gap-2">
                      <ChampionIcon name={row.champion} size={18} />
                      <span className="truncate text-soft">
                        {row.champion}
                        {row.died ? <span className="text-stat-red"> · died</span> : null}
                      </span>
                      <span className={cn("font-bold tabular-nums", row.gold >= 0 ? "text-stat-green" : "text-stat-red")}>
                        {formatSigned(row.gold, 0)} g
                      </span>
                      <span className="text-right text-muted tabular-nums">{formatSigned(row.xp, 0)} XP</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          );
        })}
      </div>
      <p className="mt-2 text-xs text-muted">
        Each laner against what they usually farm in that time; each jungler, what the play gave minus the clears it delayed.
      </p>
    </section>
  );
}

function Figure({ label, value, note, tone }: { label: string; value: string; note?: string; tone?: Tone }) {
  return (
    <div className="border border-line px-2 py-1.5">
      <dt className="text-xs text-muted">{label}</dt>
      <dd
        className={cn(
          "text-sm font-black tabular-nums",
          tone === "bad" ? "text-stat-red" : tone === "good" ? "text-stat-green" : "text-text",
        )}
      >
        {value}
      </dd>
      {note && <dd className="truncate text-xs text-subtle">{note}</dd>}
    </div>
  );
}
