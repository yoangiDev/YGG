import { useState } from "react";

import { ChampionIcon } from "@/components/player/PlayerBits";
import { cn } from "@/lib/cn";
import { MINIMAP } from "@/lib/ddragon";
import { formatNumber } from "@/lib/format";
import { palette } from "@/lib/palette";

import { FilterChip } from "./MomentExplorer";
import { type Game, MAP_VIEWBOX, mapPoint, type Ward, WARD_RISKS, WARD_WINDOWS, type WardGroup, wardGroups } from "./premiumData";

const WINDOW_LABELS: Record<string, string> = {
  objective: "Setting up an objective",
  priority: "With your wave pushed",
  reset: "On the way out of base",
  none: "None of those",
};
const RISK_LABELS: Record<string, string> = { low: "Low", medium: "Medium", high: "High" };
const RISK_COLORS: Record<string, string> = { low: palette.green, medium: palette.gold, high: palette.red };
const TYPE_LABELS: Record<Ward["type"], string> = { totem: "Trinket ward", control: "Control ward", support: "Support item ward" };
const MODES = [
  { key: "info", label: "What it saw" },
  { key: "risk", label: "What it risked" },
] as const;
type Mode = (typeof MODES)[number]["key"];

const infoColor = (ward: Ward) => (ward.jungler ? palette.blue : ward.seconds > 0 ? palette.green : palette.gray);
const share = (part: number, whole: number) => (whole ? `${Math.round((part / whole) * 100)}%` : "—");

/** The support's wards on the map, one by one: what each showed or what it risked when placed, and the tallies
 * by the window they were placed in and by their risk. */
export function WardMap({ games }: { games: Game[] }) {
  const [gameFilter, setGameFilter] = useState("all");
  const [mode, setMode] = useState<Mode>("info");
  const [picked, setPicked] = useState<string | null>(null);

  const withWards = games.map((game, gameIndex) => ({ game, gameIndex })).filter(({ game }) => game.wards?.length);
  const all = withWards.flatMap(({ game, gameIndex }) =>
    (game.wards ?? []).map((ward, i) => ({ key: `${game.match_id}:${i}`, game, gameIndex, ward })),
  );
  const shown = all.filter((w) => gameFilter === "all" || w.game.match_id === gameFilter);
  const wards = shown.map((w) => w.ward);
  const current = shown.find((w) => w.key === picked);
  const useful = wards.filter((w) => w.seconds > 0).length;
  const seconds = wards.reduce((sum, w) => sum + w.seconds, 0);
  const legend =
    mode === "info"
      ? [
          { color: palette.blue, label: "Found their jungler" },
          { color: palette.green, label: "Showed someone" },
          { color: palette.gray, label: "Saw nobody" },
        ]
      : WARD_RISKS.map((risk) => ({ color: RISK_COLORS[risk] ?? palette.gray, label: `${RISK_LABELS[risk]} risk` }));

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-1.5">
        <div role="group" aria-label="Colour the wards by" className="mr-2 flex overflow-hidden rounded-full border border-line">
          {MODES.map((m) => (
            <button
              key={m.key}
              type="button"
              aria-pressed={mode === m.key}
              onClick={() => setMode(m.key)}
              className={cn(
                "cursor-pointer px-3 py-1 text-xs font-bold transition",
                mode === m.key ? "bg-acid text-on-acid" : "text-muted hover:text-text",
              )}
            >
              {m.label}
            </button>
          ))}
        </div>
        <FilterChip active={gameFilter === "all"} onClick={() => setGameFilter("all")}>
          All {withWards.length} games
        </FilterChip>
        {withWards.map(({ game, gameIndex }) => (
          <FilterChip key={game.match_id} active={gameFilter === game.match_id} onClick={() => setGameFilter(game.match_id)}>
            <ChampionIcon name={game.champion} size={16} />
            <span className="tabular-nums">G{gameIndex + 1}</span>
            <span className={game.win ? "text-stat-green" : "text-stat-red"}>{game.win ? "W" : "L"}</span>
          </FilterChip>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
        <figure className="flex flex-col gap-2">
          <div className="relative aspect-square overflow-hidden border border-line bg-ink">
            <img src={MINIMAP.src} alt="" className="absolute inset-0 size-full brightness-[0.55] saturate-[0.6]" />
            <svg
              viewBox={MAP_VIEWBOX}
              preserveAspectRatio="none"
              className="absolute inset-0 size-full"
              role="img"
              aria-label={`Map of ${wards.length} wards, ${useful} of which showed an enemy.`}
            >
              {shown.map(({ key, ward }) => {
                const { cx, cy } = mapPoint(ward.x, ward.z);
                const dot = {
                  fill: mode === "info" ? infoColor(ward) : (RISK_COLORS[ward.risk] ?? palette.gray),
                  fillOpacity: key === picked ? 1 : 0.8,
                  stroke: ward.died ? palette.fg : palette.bg,
                  strokeWidth: ward.died ? 80 : 40,
                  className: "cursor-pointer",
                  onClick: () => setPicked(key),
                };
                const title = <title>{`${ward.clock} · ${TYPE_LABELS[ward.type]}`}</title>;
                return ward.type === "control" ? (
                  <rect key={key} x={cx - 170} y={cy - 170} width={340} height={340} {...dot}>
                    {title}
                  </rect>
                ) : (
                  <circle key={key} cx={cx} cy={cy} r={190} {...dot}>
                    {title}
                  </circle>
                );
              })}
              {current && (
                <circle
                  cx={mapPoint(current.ward.x, current.ward.z).cx}
                  cy={mapPoint(current.ward.x, current.ward.z).cy}
                  r={520}
                  fill="none"
                  stroke={palette.primary}
                  strokeWidth={80}
                  pointerEvents="none"
                />
              )}
            </svg>
          </div>
          <figcaption className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
            {legend.map((item) => (
              <span key={item.label} className="inline-flex items-center gap-1.5">
                <span aria-hidden="true" className="size-2.5 rounded-full" style={{ background: item.color }} />
                {item.label}
              </span>
            ))}
            <span>Square = control ward</span>
            <span>White ring = died within 15 s</span>
          </figcaption>
        </figure>

        <div className="flex min-w-0 flex-col gap-3">
          <p className="text-sm text-soft">
            <span className="font-bold text-text tabular-nums">{wards.length}</span> wards ·{" "}
            <span className="font-bold text-text tabular-nums">{share(useful, wards.length)}</span> showed an enemy your team wasn&apos;t seeing ·{" "}
            <span className="font-bold text-text tabular-nums">{wards.length ? formatNumber(seconds / wards.length, 1) : "—"} s</span> of that per ward ·{" "}
            <span className="font-bold text-text tabular-nums">{wards.filter((w) => w.swept).length}</span> swept
          </p>
          <GroupTable
            caption="When you placed them"
            note="Objective: within reach of a pit from 90 s before it spawns until it is taken. Wave pushed: your lane's wave on their side. Out of base: in the 75 s after leaving it. Wards with no window tend to show more, because they go where nobody of yours is — but they are also the ones that thin out as you climb: 6.8% of a Gold support's wards, 4.6% of a Challenger's."
            groups={wardGroups(wards, "when", WARD_WINDOWS)}
            labels={WINDOW_LABELS}
            total={wards.length}
          />
          <GroupTable
            caption="What you risked placing them"
            note="How many of them could already see you when you placed it, and whether anyone of yours was next to you. High: three or more in sight within 1500 units, or two with nobody of yours within 2000. Across 5,143 games supports die within 15 s of 2.4% of their low-risk wards, 7% of the medium ones and 16% of the high ones — with two enemies watching, having a teammate next to you takes it from 14.4% to 9.2%."
            groups={wardGroups(wards, "risk", WARD_RISKS)}
            labels={RISK_LABELS}
            colors={RISK_COLORS}
            total={wards.length}
          />
          {current ? (
            <p aria-live="polite" className="border border-line bg-panel-light/70 p-3 text-sm leading-relaxed text-soft">
              <span className="font-bold text-text tabular-nums">
                G{current.gameIndex + 1} · {current.ward.clock}
              </span>{" "}
              · {TYPE_LABELS[current.ward.type]} · {(WINDOW_LABELS[current.ward.when] ?? "").toLowerCase()} ·{" "}
              {(RISK_LABELS[current.ward.risk] ?? "").toLowerCase()} risk ·{" "}
              {current.ward.seconds > 0
                ? `showed enemies for ${current.ward.seconds} s${current.ward.jungler ? ", their jungler among them" : ""}`
                : "saw nobody"}{" "}
              · on the map {current.ward.lived} s{current.ward.swept ? ", until they cleared it" : ""}
              {current.ward.died ? " · you died right after placing it" : ""}
            </p>
          ) : (
            <p className="border border-dashed border-line p-3 text-sm text-muted">Pick a ward on the map to see when you placed it and what it saw.</p>
          )}
        </div>
      </div>
    </div>
  );
}

function GroupTable({
  caption,
  note,
  groups,
  labels,
  colors,
  total,
}: {
  caption: string;
  note: string;
  groups: WardGroup[];
  labels: Record<string, string>;
  colors?: Record<string, string>;
  total: number;
}) {
  return (
    <div className="border border-line p-3">
      <table className="w-full text-xs">
        <caption className="pb-1.5 text-left text-sm font-bold text-text">{caption}</caption>
        <thead>
          <tr className="text-xs text-muted uppercase">
            <th scope="col" className="pb-1 text-left font-bold">
              <span className="sr-only">{caption}</span>
            </th>
            <th scope="col" className="pb-1 text-right font-bold">Wards</th>
            <th scope="col" className="pb-1 text-right font-bold">Showed someone</th>
            <th scope="col" className="pb-1 text-right font-bold">Info per ward</th>
            <th scope="col" className="pb-1 text-right font-bold">Died in 15 s</th>
          </tr>
        </thead>
        <tbody>
          {groups.map((group) => (
            <tr key={group.key} className="border-t border-line/60">
              <th scope="row" className="py-1.5 text-left font-bold text-soft">
                {colors && <span aria-hidden="true" className="mr-1.5 inline-block size-2 rounded-full" style={{ background: colors[group.key] }} />}
                {labels[group.key] ?? group.key}
              </th>
              <td className="py-1.5 text-right text-text tabular-nums">
                {group.wards} <span className="text-muted">({share(group.wards, total)})</span>
              </td>
              <td className="py-1.5 text-right text-text tabular-nums">{share(group.useful, group.wards)}</td>
              <td className="py-1.5 text-right text-text tabular-nums">{group.wards ? `${formatNumber(group.seconds / group.wards, 1)} s` : "—"}</td>
              <td className={cn("py-1.5 text-right tabular-nums", group.died ? "font-bold text-stat-red" : "text-muted")}>{group.died}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-2 text-xs text-muted">{note}</p>
    </div>
  );
}
