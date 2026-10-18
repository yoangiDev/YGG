import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type ExpandedState,
  type SortingState,
} from "@tanstack/react-table";
import { ArrowDown, ArrowUp, ArrowUpDown, ChevronDown } from "lucide-react";
import { Fragment, useState } from "react";

import { ChampionIcon, ItemIcon, RuneIcon, ScoreRing, SpellIcon } from "@/components/player/PlayerBits";
import { cn } from "@/lib/cn";
import { asPercent, formatDateTime, formatDuration, formatNumber, formatPercent, formatSigned, timeAgo } from "@/lib/format";
import { roleLabel } from "@/lib/roles";
import { statTone, toneText } from "@/lib/stats";

import type { Match } from "./queries";
import { WpaTimeline } from "./WpaTimeline";

const column = createColumnHelper<Match>();
const CENTERED = new Set(["kda", "build"]);

const columns = [
  column.accessor("win", {
    id: "result",
    header: "Result",
    cell: ({ row }) => (
      <span className={cn("text-xs font-bold tracking-wide uppercase", row.original.win ? "text-stat-blue" : "text-stat-red")}>
        {row.original.win ? "Win" : "Loss"}
      </span>
    ),
  }),
  column.accessor((match) => match.wpa_grade ?? undefined, {
    id: "grade",
    header: "Grade",
    sortUndefined: "last",
    cell: (info) => {
      const grade = info.getValue();
      if (grade === undefined) return <span className="text-muted">—</span>;
      return (
        <div title="Grade vs. Challenger games in this role (70 = better than 2 in 3 Challenger games)">
          <ScoreRing score={grade} />
        </div>
      );
    },
  }),
  column.accessor("champion", {
    header: "Champion",
    cell: ({ row }) => (
      <div className="flex items-center gap-2.5">
        <ChampionIcon name={row.original.champion} size={32} />
        <div className="min-w-0">
          <p className="max-w-32 truncate font-normal text-text">{row.original.champion}</p>
          <p className="text-xs text-muted">{roleLabel(row.original.player_role)}</p>
        </div>
      </div>
    ),
  }),
  column.accessor("kda", {
    header: "KDA",
    cell: ({ row }) => (
      <div>
        <p className="text-text tabular-nums">
          {row.original.kills}/<span className="text-stat-red">{row.original.deaths}</span>/{row.original.assists}
        </p>
        <p className={cn("text-xs tabular-nums", toneText[statTone("kda", row.original.kda_status)])} title="(Kills + Assists) / Deaths">
          {formatNumber(row.original.kda, 2)} KDA
        </p>
      </div>
    ),
  }),
  column.accessor("cs_per_min", { header: "CS/min", cell: (info) => formatNumber(info.getValue(), 1) }),
  column.accessor((match) => match.gold_diff_14 ?? undefined, {
    id: "gold_diff_14",
    header: "GD@14",
    sortUndefined: "last",
    cell: (info) => {
      const value = info.getValue();
      if (value === undefined) return <span className="text-muted">—</span>;
      return <span className={value >= 0 ? "text-stat-green" : "text-stat-red"}>{formatSigned(value)}</span>;
    },
  }),
  column.accessor((match) => asPercent(match.kill_participation), {
    id: "kill_participation",
    header: "KP",
    cell: (info) => formatPercent(info.getValue(), 0),
  }),
  column.accessor((match) => asPercent(match.damage_share), {
    id: "damage_share",
    header: "Dmg %",
    cell: (info) => formatPercent(info.getValue(), 0),
  }),
  column.accessor("vision_per_min", { header: "Vis/min", cell: (info) => formatNumber(info.getValue(), 2) }),
  column.display({
    id: "build",
    header: "Build",
    cell: ({ row }) => {
      const match = row.original;
      return (
        <div className="flex items-center justify-center gap-2">
          {/* shrink-0: without it the column narrows and the images' max-width: 100% squashes the spells. */}
          <div className="flex shrink-0 flex-col gap-0.5">
            <SpellIcon spellId={match.summoner1_id} size={16} />
            <SpellIcon spellId={match.summoner2_id} size={16} />
          </div>
          <RuneIcon runeId={match.primary_rune} size={22} />
          <div className="flex gap-0.5">
            {[match.item0, match.item1, match.item2, match.item3, match.item4, match.item5, match.item6].map((item, index) => (
              <ItemIcon key={index} itemId={item} size={22} />
            ))}
            <span className="flex" title={match.quest_reward_item ? "Role quest completed" : "Role quest not completed"}>
              <ItemIcon itemId={match.quest_reward_item} size={22} />
            </span>
          </div>
        </div>
      );
    },
  }),
  column.accessor("duration", { header: "Length", cell: (info) => formatDuration(info.getValue()) }),
  column.accessor("creation_time", {
    header: "Played",
    cell: (info) => (
      <time dateTime={info.getValue()} title={formatDateTime(info.getValue())} className="text-muted">
        {timeAgo(info.getValue())}
      </time>
    ),
  }),
  column.display({
    id: "expand",
    header: () => <span className="sr-only">Timeline</span>,
    cell: ({ row }) => (
      <button
        type="button"
        aria-expanded={row.getIsExpanded()}
        aria-label={row.getIsExpanded() ? "Hide win probability timeline" : "Show win probability timeline"}
        onClick={(event) => {
          event.stopPropagation(); // the whole row expands too
          row.toggleExpanded();
        }}
        className="grid size-7 cursor-pointer place-items-center text-subtle transition hover:bg-panel-light hover:text-text"
      >
        <ChevronDown className={cn("size-4 transition-transform", row.getIsExpanded() && "rotate-180")} aria-hidden="true" />
      </button>
    ),
  }),
];

// ponytail: not virtualised, all rows on the page (the scroll is the screen's).
// If a snapshot reaches several hundred matches and it shows, useWindowVirtualizer from @tanstack/react-virtual.
/** Sortable match table; each row expands with its WPA timeline. */
export function MatchTable({ matches, snapshotId }: { matches: Match[]; snapshotId: number }) {
  const [sorting, setSorting] = useState<SortingState>([{ id: "creation_time", desc: true }]);
  const [expanded, setExpanded] = useState<ExpandedState>({});

  const table = useReactTable({
    data: matches,
    columns,
    state: { sorting, expanded },
    onSortingChange: setSorting,
    onExpandedChange: setExpanded,
    getRowCanExpand: () => true,
    getRowId: (match) => match.match_id, // on reordering, the same match stays expanded
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });
  const columnCount = table.getVisibleLeafColumns().length;

  return (
    // Horizontal scroll only, and only if the screen is narrow: the vertical one is the page's.
    <div className="relative overflow-x-auto" tabIndex={0} role="region" aria-label="Matches table">
      <table className="w-full min-w-[1040px] border-collapse text-sm">
        <thead>
          {table.getHeaderGroups().map((group) => (
            <tr key={group.id} className="border-b border-line">
              {group.headers.map((header) => {
                const sorted = header.column.getIsSorted();
                const canSort = header.column.getCanSort();
                return (
                  <th
                    key={header.id}
                    scope="col"
                    aria-sort={canSort ? (sorted === "asc" ? "ascending" : sorted === "desc" ? "descending" : "none") : undefined}
                    className={cn(
                      "px-2 py-2.5 text-xs font-bold tracking-wider whitespace-nowrap text-muted uppercase",
                      CENTERED.has(header.column.id) ? "text-center" : "text-left",
                    )}
                  >
                    {canSort ? (
                      <button
                        type="button"
                        onClick={header.column.getToggleSortingHandler()}
                        className="-my-1.5 inline-flex cursor-pointer items-center gap-1 py-1.5 uppercase hover:text-text"
                      >
                        {flexRender(header.column.columnDef.header, header.getContext())}
                        {sorted === "asc" ? (
                          <ArrowUp className="size-3" aria-hidden="true" />
                        ) : sorted === "desc" ? (
                          <ArrowDown className="size-3" aria-hidden="true" />
                        ) : (
                          <ArrowUpDown className="size-3 opacity-40" aria-hidden="true" />
                        )}
                      </button>
                    ) : (
                      flexRender(header.column.columnDef.header, header.getContext())
                    )}
                  </th>
                );
              })}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => (
            <Fragment key={row.id}>
              <tr
                onClick={() => row.toggleExpanded()}
                className={cn(
                  "cursor-pointer border-b border-line/50 transition hover:bg-panel-light/60",
                  row.original.win
                    ? "shadow-[inset_3px_0_0_var(--color-stat-blue)]"
                    : "shadow-[inset_3px_0_0_var(--color-stat-red)]",
                )}
              >
                {row.getVisibleCells().map((cell) => (
                  <td
                    key={cell.id}
                    className={cn("px-2 py-2 whitespace-nowrap text-text/90", CENTERED.has(cell.column.id) && "text-center")}
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
              {row.getIsExpanded() && (
                <tr className="border-b border-line bg-ink-soft/60">
                  <td colSpan={columnCount}>
                    <WpaTimeline snapshotId={snapshotId} matchId={row.original.match_id} />
                  </td>
                </tr>
              )}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}
