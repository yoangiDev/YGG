import { type RefObject, useEffect, useRef, useState } from "react";

import { ChampionIcon } from "@/components/player/PlayerBits";
import { GameSummary, RatingBadge, RatingParts, ScoreTable } from "@/features/snapshots/GameCard";
import {
  GameTimeline,
  MomentDetail,
  MomentFilters,
  MomentList,
  MomentMap,
  MomentStatus,
} from "@/features/snapshots/MomentExplorer";
import { Chip, DecisiveChart, NextGame, PatternCards, ROLE_NAMES, Section, type PremiumData, type Review } from "@/features/snapshots/PremiumResult";
import { type Game, gameMoments, indexMoments, isCoachReview, type Located, type MomentKind, type Tone } from "@/features/snapshots/premiumData";
import { WardMap } from "@/features/snapshots/WardMap";
import { cn } from "@/lib/cn";
import { formatSigned } from "@/lib/format";

import { LessonCards, StrengthCards, TextToggle, useExpanded } from "./CoachCards";
import { Chain, VerdictBadge } from "./ErrorIdentity";
import { verdictOf } from "./errors";
import { createSelection, SelectionProvider, useSelected, useSelection } from "./selection";

/**
 * A match's analysis. The match and its moments come first, then what you already do well and the
 * coach block, and finally your numbers against your tier. The map and the chosen moment are a fixed stage alongside, so
 * that a lesson shows its moment without taking you elsewhere on the page; stacked (mobile), the page scrolls up to it.
 */
export function GameAnalysis({ result, review: rawReview }: { result: PremiumData; review: Review | null }) {
  const { summary, games } = result;
  const game = games[0];
  const review = isCoachReview(rawReview) ? rawReview : null;
  const index = indexMoments(games);
  const moments = game ? gameMoments(index, game.match_id) : [];
  const patterns = summary.patterns ?? [];

  const first =
    review?.lessons.flatMap((l) => l.moments).find((k) => index.has(k)) ??
    patterns.find((p) => p.tone === "bad")?.moments.find((k) => index.has(k)) ??
    null;
  const [selection] = useState(() => createSelection(first));
  const [tone, setTone] = useState<Tone | "all">("all");
  const [kind, setKind] = useState<MomentKind | null>(null);
  const expanded = useExpanded();
  const stage = useRef<HTMLDivElement>(null);

  if (!game || index.size === 0) {
    return (
      <p className="text-sm text-muted">
        This analysis was made before the coach dashboard existed. Run it again to see every moment of your game on the map.
      </p>
    );
  }

  const shown = moments
    .filter((m) => !kind || m.moment.kind === kind)
    .filter((m) => tone === "all" || m.moment.tone === tone);
  const kinds = [...new Set(moments.map((m) => m.moment.kind))];
  const hasMetrics = Object.values(summary.metrics).some((m) => m.winners !== null && m.losers !== null);

  /** Show a moment. With the stage alongside there is nothing to move; stacked, the page scrolls up to it. */
  function focus(key: string) {
    if (!index.has(key)) return;
    selection.set(key);
    if (window.matchMedia("(min-width: 1024px)").matches) return;
    const calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    stage.current?.scrollIntoView({ behavior: calm ? "auto" : "smooth", block: "start" });
  }

  const paragraphs = review?.coach_summary.split(/\n\s*\n/) ?? [];
  const summaryOpen = expanded.isOpen("summary");
  const cardProps = { index, onFocus: focus, expanded };
  const patternIds = patterns.map((p) => `pattern:${p.kind}`);

  return (
    <SelectionProvider value={selection}>
      <div className="grid gap-x-8 gap-y-6 lg:grid-cols-[minmax(0,1fr)_25rem]">
        <div className="flex min-w-0 flex-col gap-4 lg:col-start-1 lg:row-start-1">
          <GameHeader game={game} moments={moments.length} role={summary.role} tier={summary.tier} />
          {game.rating && <RatingParts rating={game.rating} />}
        </div>

        <Stage stageRef={stage} moments={moments} shown={shown} review={review} onFocus={focus} />

        <div className="flex min-w-0 flex-col gap-6 lg:col-start-1 lg:row-start-2">
          <Section
            as="h2"
            title="Your game, moment by moment"
            description="Every moment of the game, with the exact in-game minute to rewatch it. Pick one to see it on the map."
          >
            <Timeline game={game} note={review?.game_notes.find((n) => n.match_id === game.match_id)?.note} onFocus={focus} />
            <MomentFilters tone={tone} onTone={setTone} kind={kind} onKind={setKind} kinds={kinds} />
            <Moments moments={shown} />
          </Section>

          {game.scoreboard && (
            <Section as="h2" title="Scoreboard">
              <ScoreTable board={game.scoreboard} columns="md:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2" />
            </Section>
          )}

          {review ? (
            <>
              <StrengthCards review={review} {...cardProps} />
              <section aria-labelledby="coach-headline" className="acid-tab flex flex-col gap-6 border-t border-line pt-5">
                <div className="flex flex-col gap-3">
                  <h2 id="coach-headline" className="max-w-prose text-lg leading-snug font-black text-text">
                    {review.headline}
                  </h2>
                  <div className="flex max-w-prose flex-col gap-2.5 text-sm leading-relaxed text-soft">
                    {(summaryOpen ? paragraphs : paragraphs.slice(0, 1)).map((p, i) => (
                      <p key={i} className={cn(!summaryOpen && "line-clamp-3")}>
                        {p}
                      </p>
                    ))}
                  </div>
                  {(paragraphs.length > 1 || (paragraphs[0]?.length ?? 0) > 200) && (
                    <button
                      type="button"
                      aria-expanded={summaryOpen}
                      onClick={() => expanded.toggle("summary")}
                      className="-my-1.5 cursor-pointer self-start py-1.5 text-xs font-bold text-acid hover:underline"
                    >
                      {summaryOpen ? "Show less" : "Read the full review"}
                    </button>
                  )}
                </div>
                <LessonCards review={review} {...cardProps} />
                <NextGame review={review} />
              </section>
            </>
          ) : (
            <p className="border-t border-line pt-5 text-sm text-muted">
              The written coach review appears here when the analysis runs with Claude enabled; every moment above already explains itself.
            </p>
          )}

          {game.wards?.length ? (
            <Section
              as="h2"
              title="Your vision, ward by ward"
              description="Every ward you placed as support: what it showed, the window you placed it in and what you risked to place it."
            >
              <WardMap games={games} />
            </Section>
          ) : null}

          {(patterns.length > 0 || hasMetrics) && (
            <Section
              as="h2"
              title="Your numbers against your tier"
              description="How this game compares with the players of your tier and role who win and who lose. Each card links to its moments on the map."
              action={<TextToggle expanded={expanded} ids={[...patternIds, ...(hasMetrics ? ["metrics"] : [])]} scope="Your numbers against your tier" />}
            >
              {patterns.length > 0 && (
                <PatternCards
                  patterns={patterns}
                  index={index}
                  onFocus={focus}
                  titleAs="h3"
                  columns="md:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2"
                  isOpen={(kind) => expanded.isOpen(`pattern:${kind}`)}
                  onToggle={(kind) => expanded.toggle(`pattern:${kind}`)}
                />
              )}
              {hasMetrics && (
                <div className="flex flex-col gap-3">
                  <div>
                    <h3 className="text-sm font-black text-text">Where winners and losers differ most</h3>
                    <p className="mt-0.5 text-xs text-muted">The concepts that separate them in your tier and role, and where you stand (higher is better).</p>
                  </div>
                  <DecisiveChart metrics={summary.metrics} columns="md:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2" detail={expanded.isOpen("metrics")} />
                </div>
              )}
            </Section>
          )}
        </div>
      </div>
    </SelectionProvider>
  );
}

/**
 * The stage: the map and the chosen moment, always the same size on a wide screen. It is the only thing that is repainted,
 * together with the list and the cards, when the selection changes.
 */
function Stage({
  stageRef,
  moments,
  shown,
  review,
  onFocus,
}: {
  stageRef: RefObject<HTMLDivElement | null>;
  moments: Located[];
  shown: Located[];
  review: Review | null;
  onFocus: (key: string) => void;
}) {
  const selected = useSelected();
  const selection = useSelection();
  const detail = useRef<HTMLDivElement>(null);
  const current = moments.find((m) => m.key === selected);

  // a new moment is read from the top, not from where the detail's scroll was left
  useEffect(() => {
    if (detail.current) detail.current.scrollTop = 0;
  }, [selected]);

  return (
    <div ref={stageRef} className="scroll-mt-[calc(var(--header-h)+1.5rem)] lg:col-start-2 lg:row-span-2 lg:row-start-1">
      <MomentStatus text={current ? `${verdictOf(current.moment).name}. ${current.moment.clock}, ${current.moment.title}` : ""} />
      {/* the stage is always the same size: the map on top and the detail below, which is the one that scrolls */}
      <div className="flex flex-col gap-3 lg:sticky lg:top-[calc(var(--header-h)+1rem)] lg:h-[min(calc(100svh_-_var(--header-h)_-_2rem),52rem)]">
        {/* the map is square: on short screens it shrinks to leave room for the detail */}
        <div className="mx-auto w-full lg:w-[min(100%,max(14rem,45svh))] lg:shrink-0">
          <MomentMap moments={shown} current={current} onSelect={selection.set} />
        </div>
        <div ref={detail} className="flex flex-col lg:-m-1.5 lg:min-h-0 lg:flex-1 lg:overflow-y-auto lg:p-1.5">
          {current ? (
            <MomentDetail
              className="flex-1"
              located={current}
              note={review?.moment_notes.find((n) => n.moment === current.key)?.note}
              single
              verdict={<VerdictBadge moment={current.moment} />}
              extra={<Chain located={current} all={moments} onFocus={onFocus} />}
            />
          ) : (
            <p className="flex-1 border border-dashed border-line p-4 text-sm text-muted">
              Pick a moment on the map, in the list or in a lesson to see what happened, what it cost and the exact minute to rewatch.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function Timeline({ game, note, onFocus }: { game: Game; note?: string; onFocus: (key: string) => void }) {
  const selected = useSelected();
  return <GameTimeline game={game} gameIndex={0} note={note} selected={selected} onSelect={onFocus} single />;
}

function Moments({ moments }: { moments: Located[] }) {
  const selection = useSelection();
  const selected = useSelected();
  return (
    <MomentList
      moments={moments}
      selected={selected}
      onSelect={selection.set}
      renderBadge={(m) => <VerdictBadge moment={m.moment} size="sm" />}
    />
  );
}

function GameHeader({ game, moments, role, tier }: { game: Game; moments: number; role: string; tier: string }) {
  const gold14 = game.numbers?.gold_diff_14;
  return (
    <header className="flex flex-wrap items-center gap-x-3 gap-y-3">
      <RatingBadge rating={game.rating} />
      <ChampionIcon name={game.champion} size={44} />
      <GameSummary game={game} momentCount={moments} title={game.champion} />
      <div className="flex flex-wrap items-center gap-2 text-xs sm:ml-auto">
        <Chip>{ROLE_NAMES[role] ?? role}</Chip>
        <Chip>Compared with {tier.charAt(0) + tier.slice(1).toLowerCase()}</Chip>
        {gold14 !== null && gold14 !== undefined && <Chip>{formatSigned(gold14, 0)} gold at 14:00</Chip>}
      </div>
    </header>
  );
}
