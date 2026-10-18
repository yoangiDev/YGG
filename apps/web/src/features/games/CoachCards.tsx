import { ChevronDown, Lightbulb } from "lucide-react";
import { useState } from "react";

import { MomentChips, Section } from "@/features/snapshots/PremiumResult";
import { type Located, type Review } from "@/features/snapshots/premiumData";
import { cn } from "@/lib/cn";
import { formatSigned } from "@/lib/format";

import { MomentRow } from "./ErrorIdentity";
import { KILL_GOLD, killsLabel } from "./kills";
import { useSelected } from "./selection";

/**
 * The coach cards of a match's page: what is seen at a glance (how much each lesson cost or gave,
 * with each mistake at a glance (verdict, place, cost and minute)) and the full text behind a button, per card or per section.
 */

/** Which cards have their full text in view. */
export function useExpanded() {
  const [open, setOpen] = useState<ReadonlySet<string>>(new Set());
  return {
    isOpen: (id: string) => open.has(id),
    toggle: (id: string) =>
      setOpen((current) => {
        const next = new Set(current);
        if (next.has(id)) next.delete(id);
        else next.add(id);
        return next;
      }),
    allOpen: (ids: string[]) => ids.length > 0 && ids.every((id) => open.has(id)),
    setAll: (ids: string[], value: boolean) =>
      setOpen((current) => {
        const next = new Set(current);
        for (const id of ids) {
          if (value) next.add(id);
          else next.delete(id);
        }
        return next;
      }),
  };
}
export type Expanded = ReturnType<typeof useExpanded>;

/** A section's button: all its text in view, or trimmed again. */
export function TextToggle({ expanded, ids, scope }: { expanded: Expanded; ids: string[]; scope: string }) {
  const all = expanded.allOpen(ids);
  if (ids.length === 0) return null;
  const label = all ? "Show less" : "Show all text";
  return (
    <button
      type="button"
      aria-label={`${label}: ${scope}`}
      aria-pressed={all}
      onClick={() => expanded.setAll(ids, !all)}
      className="-my-1.5 inline-flex shrink-0 cursor-pointer items-center gap-1.5 py-1.5 text-xs font-bold text-acid hover:underline"
    >
      {label}
      <ChevronDown className={cn("size-3.5 transition-transform", all && "rotate-180")} aria-hidden="true" />
    </button>
  );
}

/** What the card's moments added up to, in gold and in the kills they are worth. With no gold in between, there is no total. */
function Total({ moments }: { moments: Located[] }) {
  const gold = moments.reduce((sum, m) => sum + (m.moment.gold ?? 0), 0);
  if (!gold) return null;
  const kills = killsLabel(gold);
  return (
    <p className={cn("shrink-0 text-right leading-tight tabular-nums", gold < 0 ? "text-stat-red" : "text-stat-green")}>
      <span className="block text-base font-black">{formatSigned(gold, 0)} gold</span>
      {kills && (
        <span className="block text-xs text-muted" title={`A champion kill gives ${KILL_GOLD} gold`}>
          ≈ {kills}
        </span>
      )}
    </p>
  );
}

const ROWS = 3;

/** The card's moments, each with its face; those that don't fit stay in «Why it happened». */
function Rows({ moments, selected, onFocus }: { moments: Located[]; selected: string | null; onFocus: (key: string) => void }) {
  return (
    <ul className="flex flex-col gap-2">
      {moments.slice(0, ROWS).map((m) => (
        <li key={m.key}>
          <MomentRow located={m} selected={m.key === selected} onFocus={onFocus} />
        </li>
      ))}
      {moments.length > ROWS && <li className="text-xs text-muted">+{moments.length - ROWS} more {moments.length - ROWS === 1 ? "moment" : "moments"} in the details</li>}
    </ul>
  );
}

const inOrder = (keys: string[], index: Map<string, Located>) =>
  keys.map((k) => index.get(k)).filter((m): m is Located => m !== undefined).sort((a, b) => a.moment.t - b.moment.t);

/** A card's footer: opens or closes what is trimmed. */
function More({ id, open, label, onToggle }: { id: string; open: boolean; label: string; onToggle: () => void }) {
  return (
    <button
      type="button"
      aria-expanded={open}
      aria-controls={id}
      onClick={onToggle}
      className="flex w-full cursor-pointer items-center justify-between border-t border-line px-4 py-2 text-left text-xs font-bold text-muted transition-colors hover:text-text"
    >
      {open ? "Show less" : label}
      <ChevronDown className={cn("size-4 transition-transform", open && "rotate-180")} aria-hidden="true" />
    </button>
  );
}

interface CardsProps {
  review: Review;
  index: Map<string, Located>;
  onFocus: (key: string) => void;
  expanded: Expanded;
}

/** Each lesson: its title, what to do and what it cost; the full why stays behind «Why it happened». */
export function LessonCards({ review, index, onFocus, expanded }: CardsProps) {
  const selected = useSelected();
  const ids = review.lessons.map((_, i) => `lesson:${i}`);
  return (
    <Section
      title="What to work on"
      description="From the coach, most important first. Each lesson says what it cost you; click a moment to see it on the map."
      action={<TextToggle expanded={expanded} ids={ids} scope="What to work on" />}
    >
      <ol className="flex flex-col gap-3">
        {review.lessons.map((lesson, i) => {
          const id = ids[i] ?? "";
          const open = expanded.isOpen(id);
          const moments = inOrder(lesson.moments, index);
          return (
            <li key={lesson.title} className="border border-line bg-panel-light/60">
              <div className="flex flex-col gap-3 p-4">
                <div className="flex items-start gap-3">
                  <span className="grid size-8 shrink-0 place-items-center bg-stat-gold/15 text-sm font-black text-stat-gold">{i + 1}</span>
                  <div className="min-w-0 flex-1">
                    <h4 className="text-base font-black text-text">{lesson.title}</h4>
                    <p className="mt-1 flex gap-2 text-sm text-text">
                      <Lightbulb className="mt-0.5 size-4 shrink-0 text-acid" aria-hidden="true" />
                      <span className={cn(!open && "line-clamp-2")}>{lesson.fix}</span>
                    </p>
                  </div>
                  <Total moments={moments} />
                </div>
                {moments.length > 0 && <Rows moments={moments} selected={selected} onFocus={onFocus} />}
              </div>
              <More id={id} open={open} label="Why it happened" onToggle={() => expanded.toggle(id)} />
              {open && (
                <div id={id} className="flex flex-col gap-3 border-t border-line p-4">
                  <p className="max-w-prose text-sm leading-relaxed text-soft">{lesson.why}</p>
                  <MomentChips keys={lesson.moments} index={index} onFocus={onFocus} single />
                </div>
              )}
            </li>
          );
        })}
      </ol>
    </Section>
  );
}

/** What you already do well, with the same glance as the lessons: what it gave, with each success at a glance. */
export function StrengthCards({ review, index, onFocus, expanded }: CardsProps) {
  const selected = useSelected();
  const ids = review.strengths.map((_, i) => `strength:${i}`);
  return (
    <Section as="h2" title="What you already do well" action={<TextToggle expanded={expanded} ids={ids} scope="What you already do well" />}>
      <ul className="grid gap-3 md:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
        {review.strengths.map((strength, i) => {
          const id = ids[i] ?? "";
          const open = expanded.isOpen(id);
          const moments = inOrder(strength.moments, index);
          return (
            <li key={strength.title} className="flex flex-col border border-stat-green/25 bg-stat-green/[0.04]">
              <div className="flex flex-1 flex-col gap-3 p-4">
                <div className="flex items-start justify-between gap-3">
                  <h3 className="text-sm font-black text-text">{strength.title}</h3>
                  <Total moments={moments} />
                </div>
                {moments.length > 0 && <Rows moments={moments} selected={selected} onFocus={onFocus} />}
                <p className={cn("text-sm text-soft", !open && "line-clamp-2")}>{strength.detail}</p>
              </div>
              <More id={id} open={open} label="Details" onToggle={() => expanded.toggle(id)} />
              {open && (
                <div id={id} className="border-t border-line p-4">
                  <MomentChips keys={strength.moments} index={index} onFocus={onFocus} single />
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </Section>
  );
}
