import { ChevronDown } from "lucide-react";

import { ChampionIcon } from "@/components/player/PlayerBits";
import { cn } from "@/lib/cn";
import { formatNumber, formatSigned } from "@/lib/format";
import { palette } from "@/lib/palette";

import { KIND_ICONS, MomentExplorer } from "./MomentExplorer";
import {
  type Game,
  KINDS,
  type Located,
  playedAt,
  type Rating,
  type Review,
  type Scoreboard,
  type ScoreboardPlayer,
  type TeamTotals,
} from "./premiumData";

const ROLE_SHORT: Record<string, string> = { TOP: "Top", JUNGLE: "Jgl", MIDDLE: "Mid", BOTTOM: "Bot", UTILITY: "Sup" };

/** The colour of a 1-to-100 grade: the same scale as the rest of the dashboard. */
export const ratingColor = (score: number) =>
  score >= 75 ? palette.green : score >= 60 ? palette.primary : score >= 45 ? palette.gold : palette.red;

export const clock = (seconds: number) => `${Math.floor(seconds / 60)}:${String(Math.round(seconds % 60)).padStart(2, "0")}`;

/** A match card's id, so it can be jumped to from a pattern or a lesson. */
export const gameCardId = (matchId: string) => `game-${matchId}`;

interface Props {
  game: Game;
  gameIndex: number;
  moments: Located[];
  review: Review | null;
  open: boolean;
  onToggle: () => void;
  selected: string | null;
  onSelect: (key: string) => void;
}

/** A whole match: the post-game scoreboard, the grade for what they did and all their moments. */
export function GameCard({ game, gameIndex, moments, review, open, onToggle, selected, onSelect }: Props) {
  const board = game.scoreboard;
  return (
    <article id={gameCardId(game.match_id)} className={cn("scroll-mt-4 border bg-panel-light/40", open ? "border-line-button" : "border-line")}>
      <button
        type="button"
        aria-expanded={open}
        onClick={onToggle}
        className="flex w-full cursor-pointer flex-wrap items-center gap-x-3 gap-y-2 px-4 py-3 text-left"
      >
        <RatingBadge rating={game.rating} />
        <ChampionIcon name={game.champion} size={34} />
        <GameSummary game={game} momentCount={moments.length} title={`Game ${gameIndex + 1} · ${game.champion}`} />
        <ChevronDown className={cn("ml-auto size-5 shrink-0 text-muted transition-transform", open && "rotate-180")} aria-hidden="true" />
      </button>

      {open && (
        <div className="flex flex-col gap-4 border-t border-line px-4 py-4">
          {board && <ScoreTable board={board} />}
          {game.rating && <RatingParts rating={game.rating} />}
          <MomentExplorer game={game} gameIndex={gameIndex} moments={moments} review={review} selected={selected} onSelect={onSelect} />
        </div>
      )}
    </article>
  );
}

/** Who played, against whom, how it ended and the match's numbers, on two lines. */
export function GameSummary({ game, momentCount, title }: { game: Game; momentCount: number; title: string }) {
  const board = game.scoreboard;
  const you = board?.players.find((p) => p.you);
  const score = board?.teams;
  return (
    <span className="min-w-0">
      <span className="flex flex-wrap items-baseline gap-x-2">
        <span className="text-sm font-black text-text">{title}</span>
        {game.opponent && <span className="text-xs text-muted">vs {game.opponent}</span>}
        <span className={cn("text-xs font-black uppercase", game.win ? "text-stat-green" : "text-stat-red")}>
          {game.win ? "Win" : "Loss"}
        </span>
      </span>
      <span className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-muted">
        {score && (
          <span className="font-bold tabular-nums">
            <span className="text-stat-green">{score.ally.kills}</span> – <span className="text-stat-red">{score.enemy.kills}</span>
          </span>
        )}
        {you && (
          <span className="tabular-nums">
            you {you.kills}/{you.deaths}/{you.assists} · {formatNumber(you.cs, 0)} CS
          </span>
        )}
        <span className="tabular-nums">{clock(game.duration)}</span>
        {playedAt(game) && <span>{playedAt(game)}</span>}
        <span>{momentCount} moments</span>
      </span>
    </span>
  );
}

export function RatingBadge({ rating }: { rating?: Rating }) {
  if (rating?.score === undefined)
    return (
      <span className="grid size-11 shrink-0 place-items-center border border-line text-xs text-subtle" title="No rating for this game">
        —
      </span>
    );
  return (
    <span
      className="flex size-11 shrink-0 flex-col items-center justify-center border-2"
      style={{ borderColor: ratingColor(rating.score), color: ratingColor(rating.score) }}
      title={`Rating ${rating.score}/100 for this game: ${formatSigned(rating.total, 1)} points from your own moments, per 30 minutes, against the players of your tier and role`}
    >
      <span className="text-lg leading-none font-black tabular-nums">{rating.score}</span>
      <span className="microtext text-xs opacity-70">rating</span>
    </span>
  );
}

/** Where the grade comes from: what each kind of moment adds and subtracts. */
export function RatingParts({ rating }: { rating: Rating }) {
  const parts = rating.parts.filter((p) => Math.abs(p.points) >= 0.05);
  const most = Math.max(1, ...parts.map((p) => Math.abs(p.points)));
  if (parts.length === 0) return null;
  return (
    <section aria-label="What the rating is made of" className="border border-line p-3">
      <p className="text-sm font-bold text-text">
        {rating.score !== undefined ? (
          <>
            <span className="tabular-nums" style={{ color: ratingColor(rating.score) }}>
              {rating.score}/100{" "}
            </span>
            <span className="text-muted">
              for this game: {formatSigned(rating.total, 1)} points from your own moments
              {rating.median !== undefined && `, where an ordinary game of your tier and role is ${formatSigned(rating.median, 1)}`}.
            </span>
          </>
        ) : (
          <span className="text-muted">
            What you did in this game: {formatSigned(rating.total, 1)} points from your own moments, per 30 minutes.
          </span>
        )}
      </p>
      <ul className="mt-2 grid gap-1.5 sm:grid-cols-2">
        {parts.map((part) => {
          const Icon = KIND_ICONS[part.kind];
          const good = part.points > 0;
          return (
            <li key={part.kind} className="grid grid-cols-[1rem_minmax(0,7rem)_1fr_3rem] items-center gap-2 text-xs">
              <Icon className="size-3.5 text-muted" aria-hidden="true" />
              <span className="truncate text-soft">{KINDS[part.kind]}</span>
              <span className="relative h-1.5 rounded-full bg-white/10" aria-hidden="true">
                <span className="absolute inset-y-0 left-1/2 w-px bg-line-button" />
                <span
                  className="absolute inset-y-0 rounded-full"
                  style={{
                    background: good ? palette.green : palette.red,
                    left: good ? "50%" : `${50 - (50 * Math.abs(part.points)) / most}%`,
                    width: `${(50 * Math.abs(part.points)) / most}%`,
                  }}
                />
              </span>
              <span className={cn("text-right tabular-nums", good ? "text-stat-green" : "text-stat-red")}>
                {formatSigned(part.points, 1)}
              </span>
            </li>
          );
        })}
      </ul>
      <p className="mt-2 text-xs text-muted">
        Only what you decide counts: fights, objectives and the game&apos;s swings are your team&apos;s, so they don&apos;t move your rating.
      </p>
    </section>
  );
}

/** The post-game scoreboard: the five of each team with their KDA, gold and damage. */
export function ScoreTable({ board, columns = "lg:grid-cols-2" }: { board: Scoreboard; columns?: string }) {
  const most = Math.max(1, ...board.players.map((p) => p.damage));
  return (
    <div className={cn("grid gap-3", columns)}>
      {(["ally", "enemy"] as const).map((side) => (
        <div key={side} className="border border-line">
          <TeamHeader side={side} totals={board.teams[side]} />
          <table className="w-full text-xs">
            <caption className="sr-only">{side === "ally" ? "Your team" : "Their team"}</caption>
            <thead>
              <tr className="text-xs text-subtle uppercase">
                <th scope="col" className="py-1 pl-2 text-left font-bold">Champion</th>
                <th scope="col" className="py-1 text-right font-bold">KDA</th>
                <th scope="col" className="py-1 text-right font-bold">CS</th>
                <th scope="col" className="py-1 text-right font-bold">Gold</th>
                <th scope="col" className="py-1 pr-2 text-right font-bold">Damage</th>
              </tr>
            </thead>
            <tbody>
              {board.players
                .filter((p) => p.side === side)
                .map((p) => (
                  <Row key={p.champion} player={p} most={most} />
                ))}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
}

function TeamHeader({ side, totals }: { side: "ally" | "enemy"; totals: TeamTotals }) {
  const objectives = [
    totals.dragons && `${totals.dragons} dragon${totals.dragons > 1 ? "s" : ""}`,
    totals.barons && `${totals.barons} Baron${totals.barons > 1 ? "s" : ""}`,
    totals.heralds && `${totals.heralds} Herald${totals.heralds > 1 ? "s" : ""}`,
    totals.grubs && `${totals.grubs} grubs`,
    totals.towers && `${totals.towers} tower${totals.towers > 1 ? "s" : ""}`,
  ].filter((x): x is string => Boolean(x));
  return (
    <p className="flex flex-wrap items-baseline gap-x-2 border-b border-line px-2 py-1.5">
      <span className={cn("text-xs font-black", side === "ally" ? "text-stat-green" : "text-stat-red")}>
        {side === "ally" ? "Your team" : "Their team"}
      </span>
      <span className="text-xs font-bold text-text tabular-nums">{totals.kills} kills</span>
      <span className="text-xs text-muted tabular-nums">{formatNumber(totals.gold, 0)} gold</span>
      {objectives.length > 0 && <span className="text-xs text-muted">{objectives.join(" · ")}</span>}
    </p>
  );
}

function Row({ player, most }: { player: ScoreboardPlayer; most: number }) {
  return (
    <tr className={cn("border-t border-line/50", player.you && "bg-acid/[0.07]")}>
      <th scope="row" className="py-1 pl-2 text-left font-normal">
        <span className="flex min-w-0 items-center gap-1.5">
          <ChampionIcon name={player.champion} size={18} className="shrink-0" />
          <span className={cn("truncate", player.you ? "font-bold text-text" : "text-soft")}>{player.champion}</span>
          <span className="shrink-0 text-xs text-subtle uppercase">{ROLE_SHORT[player.role] ?? ""}</span>
        </span>
      </th>
      <td className="py-1 text-right text-soft tabular-nums">
        {player.kills}/<span className="text-stat-red">{player.deaths}</span>/{player.assists}
      </td>
      <td className="py-1 text-right text-soft tabular-nums">{player.cs}</td>
      <td className="py-1 text-right text-soft tabular-nums">{formatNumber(player.gold / 1000, 1)}k</td>
      <td className="py-1 pr-2 text-right tabular-nums">
        <span className="flex items-center justify-end gap-1.5">
          <span className="h-1 w-8 rounded-full bg-white/10" aria-hidden="true">
            <span className="block h-full rounded-full bg-stat-gold/70" style={{ width: `${(100 * player.damage) / most}%` }} />
          </span>
          <span className="text-soft">{formatNumber(player.damage / 1000, 1)}k</span>
        </span>
      </td>
    </tr>
  );
}
