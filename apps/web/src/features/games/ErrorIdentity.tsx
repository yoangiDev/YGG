import { Hourglass, type LucideIcon, TrendingDown } from "lucide-react";

import { KIND_ICONS } from "@/features/snapshots/MomentExplorer";
import { type Located, TONE_COLOR } from "@/features/snapshots/premiumData";
import { cn } from "@/lib/cn";
import { MINIMAP } from "@/lib/ddragon";

import { consequencesOf, costOf, placeLabel, type Step, type Verdict, verdictOf } from "./errors";

/**
 * The face of a mistake: its verdict (how much it weighed), a small map with the point where it happened, the minute to go to the
 * recording and the chain of what came after. The colour is still the page's: red for mistakes, green for
 * successes; the severity shows in how filled the badge is.
 */

const BADGE: Record<Verdict["key"], string> = {
  blunder: "bg-stat-red text-ink",
  mistake: "border border-stat-red/60 bg-stat-red/15 text-stat-red",
  slip: "border border-line-button text-soft",
  great: "bg-stat-green text-ink",
  good: "border border-stat-green/60 bg-stat-green/15 text-stat-green",
  tradeoff: "border border-stat-gold/60 bg-stat-gold/10 text-stat-gold",
  teamloss: "border border-line-button text-soft",
  teamwin: "border border-stat-green/40 text-stat-green",
};

/** The moment's chess annotation (?? Blunder, ? Mistake, ?! Slip, ! Good play); for team things, «Team loss» or «Team win». */
export function VerdictBadge({ moment, size = "md" }: { moment: Located["moment"]; size?: "sm" | "md" }) {
  const verdict = verdictOf(moment);
  return (
    <span
      role="img"
      aria-label={verdict.name}
      title={verdict.name}
      className={cn("grid shrink-0 place-items-center leading-none font-black", size === "sm" ? "size-6 text-xs" : "size-8 text-sm", BADGE[verdict.key])}
    >
      <span aria-hidden="true">{verdict.glyph}</span>
    </span>
  );
}

/** The match's minimap, small, with a dot where it happened. With no position, the icon of the kind of moment. */
function MapThumb({ located }: { located: Located }) {
  const { moment } = located;
  if (moment.x === null || moment.z === null) {
    const Icon = KIND_ICONS[moment.kind];
    return (
      <span className="grid size-10 shrink-0 place-items-center border border-line sm:size-12" aria-hidden="true">
        <Icon className="size-5 text-muted" />
      </span>
    );
  }
  const left = ((moment.x - MINIMAP.x[0]) / (MINIMAP.x[1] - MINIMAP.x[0])) * 100;
  const top = ((MINIMAP.z[1] - moment.z) / (MINIMAP.z[1] - MINIMAP.z[0])) * 100;
  return (
    <span className="relative size-10 shrink-0 overflow-hidden border border-line bg-ink sm:size-12" aria-hidden="true">
      <img src={MINIMAP.src} alt="" loading="lazy" decoding="async" className="absolute inset-0 size-full brightness-[0.55] saturate-[0.6]" />
      <span
        className="absolute size-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-ink"
        style={{ left: `${left}%`, top: `${top}%`, background: TONE_COLOR[moment.tone] }}
      />
    </span>
  );
}

/** A mistake from a lesson, at a glance: verdict, where, what it was, what it cost and at what minute. One click shows it. */
export function MomentRow({ located, selected, onFocus }: { located: Located; selected: boolean; onFocus: (key: string) => void }) {
  const { moment } = located;
  const cost = costOf(moment);
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={() => onFocus(located.key)}
      className={cn(
        "grid w-full cursor-pointer grid-cols-[auto_auto_minmax(0,1fr)_auto] items-center gap-2.5 border px-2.5 py-2 text-left transition-colors sm:gap-3 sm:px-3",
        selected ? "border-acid/70 bg-acid/[0.06]" : "border-line hover:border-line-button",
      )}
    >
      <VerdictBadge moment={moment} />
      <MapThumb located={located} />
      <span className="min-w-0">
        <span className="line-clamp-2 text-sm font-bold text-text">{moment.title}</span>
        {cost && <span className={cn("block text-xs tabular-nums", moment.tone === "good" ? "text-stat-green" : "text-stat-red")}>{cost}</span>}
      </span>
      <span className="text-right">
        <span className="block text-base font-black text-text tabular-nums">{moment.clock}</span>
        {moment.where && <span className="block max-w-28 truncate text-xs text-muted">{placeLabel(moment.where)}</span>}
      </span>
    </button>
  );
}

const STEP_ICONS: Record<Step["kind"], LucideIcon> = { ...KIND_ICONS, time: Hourglass, wp: TrendingDown };

/**
 * What came after a mistake, link by link: the mistake, the time it took from you, what fell meanwhile and what
 * changed in the match. Vertical because it lives in the stage's narrow column.
 */
export function Chain({ located, all, onFocus }: { located: Located; all: Located[]; onFocus: (key: string) => void }) {
  const steps = consequencesOf(located, all);
  if (steps.length === 0) return null;
  return (
    <div className="mt-3">
      <p className="mb-2 text-xs font-bold text-muted">What followed</p>
      <ol aria-label="What followed this error">
        {steps.map((step, i) => {
          const Icon = STEP_ICONS[step.kind];
          const body = (
            <>
              <span
                className={cn(
                  "grid size-8 shrink-0 place-items-center border",
                  i === 0 ? "border-stat-red bg-stat-red/10 text-stat-red" : step.tone === "good" ? "border-stat-green/50 text-stat-green" : "border-line-button text-soft",
                )}
              >
                <Icon className="size-4" aria-hidden="true" />
              </span>
              <span className="min-w-0 pt-0.5">
                <span className="block text-sm font-bold text-text">{step.label}</span>
                {step.sub && <span className="block text-xs text-muted tabular-nums">{step.sub}</span>}
              </span>
            </>
          );
          return (
            <li key={`${step.kind}-${i}`} className="relative">
              {i < steps.length - 1 && <span aria-hidden="true" className="absolute top-8 bottom-0 left-4 w-px bg-line-button" />}
              {step.key && i > 0 ? (
                <button type="button" onClick={() => onFocus(step.key ?? "")} className="flex w-full cursor-pointer gap-3 pb-3 text-left hover:[&_span.block]:text-acid">
                  {body}
                </button>
              ) : (
                <div className={cn("flex gap-3", i < steps.length - 1 && "pb-3")}>{body}</div>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
