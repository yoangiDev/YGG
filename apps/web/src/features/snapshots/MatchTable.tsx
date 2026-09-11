import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type SortingState,
} from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import { useRef, useState } from "react";

import { ChampionIcon, ItemIcon, RuneIcon, SpellIcon } from "@/components/player/PlayerBits";
import { cn } from "@/lib/cn";
import { asPercent, formatDateTime, formatDuration, formatNumber, formatPercent, formatSigned, timeAgo } from "@/lib/format";
import { roleLabel } from "@/lib/roles";
import { kdaTone, toneText } from "@/lib/stats";

import type { Match } from "./queries";

const column = createColumnHelper<Match>();

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
  column.accessor("champion", {
    header: "Champion",
    cell: ({ row }) => (
      <div className="flex items-center gap-2.5">
        <ChampionIcon name={row.original.champion} size={32} />
        <div className="min-w-0">
          <p className="max-w-32 truncate font-medium text-fg">{row.original.champion}</p>
          <p className="text-xs text-muted">{roleLabel(row.original.player_role)}</p>
        </div>
      </div>
    ),
  }),
  column.accessor("kda", {
    header: "KDA",
    cell: ({ row }) => (
      <div>
        <p className="text-fg tabular-nums">
          {row.original.kills}/<span className="text-stat-red">{row.original.deaths}</span>/{row.original.assists}
        </p>
        <p className={cn("text-xs tabular-nums", toneText[kdaTone(row.original.kda)])}>{formatNumber(row.original.kda, 2)}</p>
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
        <div className="flex items-center gap-2">
          <div className="flex flex-col gap-0.5">
            <SpellIcon spellId={match.summoner1_id} size={16} />
            <SpellIcon spellId={match.summoner2_id} size={16} />
          </div>
          <RuneIcon runeId={match.primary_rune} size={22} />
          <div className="flex gap-0.5">
            {[match.item0, match.item1, match.item2, match.item3, match.item4, match.item5, match.item6].map((item, index) => (
              <ItemIcon key={index} itemId={item} size={22} />
            ))}
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
];

const ROW_HEIGHT = 56;

/**
 * Tabla de partidas ordenable y virtualizada: con cientos de partidas solo se
 * montan las filas visibles (más un margen), así el scroll no se resiente.
 */
export function MatchTable({ matches }: { matches: Match[] }) {
  const [sorting, setSorting] = useState<SortingState>([{ id: "creation_time", desc: true }]);
  const scrollRef = useRef<HTMLDivElement>(null);

  const table = useReactTable({
    data: matches,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  const { rows } = table.getRowModel();
  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 10,
    initialRect: { width: 1024, height: 720 },
  });

  const virtualRows = virtualizer.getVirtualItems();
  const paddingTop = virtualRows[0]?.start ?? 0;
  const paddingBottom = virtualizer.getTotalSize() - (virtualRows.at(-1)?.end ?? 0);
  const columnCount = table.getVisibleLeafColumns().length;

  return (
    <div ref={scrollRef} className="max-h-[70vh] overflow-auto" tabIndex={0} role="region" aria-label="Matches table">
      <table className="w-full min-w-[1040px] border-collapse text-sm" aria-rowcount={rows.length + 1}>
        <thead className="sticky top-0 z-10 bg-surface">
          {table.getHeaderGroups().map((group) => (
            <tr key={group.id} className="border-b border-border">
              {group.headers.map((header) => {
                const sorted = header.column.getIsSorted();
                const canSort = header.column.getCanSort();
                return (
                  <th
                    key={header.id}
                    scope="col"
                    aria-sort={canSort ? (sorted === "asc" ? "ascending" : sorted === "desc" ? "descending" : "none") : undefined}
                    className="px-3 py-2.5 text-left text-[11px] font-semibold tracking-wider whitespace-nowrap text-muted uppercase"
                  >
                    {canSort ? (
                      <button
                        type="button"
                        onClick={header.column.getToggleSortingHandler()}
                        className="inline-flex cursor-pointer items-center gap-1 uppercase hover:text-fg"
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
          {paddingTop > 0 && (
            <tr aria-hidden="true">
              <td colSpan={columnCount} style={{ height: paddingTop }} />
            </tr>
          )}
          {virtualRows.map((virtualRow) => {
            const row = rows[virtualRow.index];
            if (!row) return null;
            return (
              <tr
                key={row.id}
                data-index={virtualRow.index}
                aria-rowindex={virtualRow.index + 2}
                ref={virtualizer.measureElement}
                className={cn(
                  "border-b border-border/50 transition hover:bg-surface-2/60",
                  row.original.win
                    ? "shadow-[inset_3px_0_0_var(--color-stat-blue)]"
                    : "shadow-[inset_3px_0_0_var(--color-stat-red)]",
                )}
              >
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} className="px-3 py-2 whitespace-nowrap text-fg/90">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            );
          })}
          {paddingBottom > 0 && (
            <tr aria-hidden="true">
              <td colSpan={columnCount} style={{ height: paddingBottom }} />
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
