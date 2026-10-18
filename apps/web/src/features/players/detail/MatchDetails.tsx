import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { Swords } from "lucide-react";

import { ChampionIcon, ItemIcon, RuneIcon, SpellIcon } from "@/components/player/PlayerBits";
import { Skeleton } from "@/components/ui/Card";
import { ErrorState } from "@/components/ui/States";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { cn } from "@/lib/cn";
import { OBJECTIVE_ICONS } from "@/lib/ddragon";
import { formatCompact, formatNumber, formatPercent } from "@/lib/format";
import { queryKeys } from "@/lib/queryKeys";
import { lpLabel, rankImage, rankLabel } from "@/lib/rank";
import { roleLabel } from "@/lib/roles";
import { scoreTone, statTone, toneText } from "@/lib/stats";

type Team = Schemas["MatchTeamDetails"];
type Participant = Schemas["MatchParticipantDetails"];
type LobbyRank = Schemas["LobbyRank"];
type PlayerRank = Schemas["PlayerRank"];

// Official minimap icons (OBJECTIVE_ICONS). Kills have none that reads at this size: swords.
const OBJECTIVES = [
  { key: "kills", label: "Kills", icon: null },
  { key: "towers", label: "Towers", icon: "tower" },
  { key: "dragons", label: "Dragons", icon: "dragon" },
  { key: "barons", label: "Barons", icon: "baron" },
  { key: "heralds", label: "Heralds", icon: "riftherald" },
  { key: "grubs", label: "Void grubs", icon: "grub" },
] as const satisfies readonly { key: keyof Team; label: string; icon: string | null }[];

// placement · champion · player · spells and runes · items · KDA · KP · CS · damage · score
const ROW_GRID =
  "grid-cols-[40px_32px_minmax(0,1fr)_64px_32px] sm:grid-cols-[46px_32px_minmax(0,1fr)_72px_48px_58px_minmax(84px,1fr)_36px] " +
  "lg:grid-cols-[46px_32px_minmax(96px,1fr)_40px_92px_72px_48px_58px_minmax(92px,1fr)_36px]";

function ordinal(position: number): string {
  if (position === 1) return "1st";
  if (position === 2) return "2nd";
  if (position === 3) return "3rd";
  return `${position}th`;
}

// MVP and ACE, flat: MVP with the accent and ACE in lilac. No glows.
const BADGES = {
  MVP: { title: "MVP: best player of the winning team", className: "border border-acid/60 text-acid" },
  ACE: { title: "ACE: best player of the losing team", className: "border border-rank-master/60 bg-rank-master/15 text-rank-master-text" },
} as const;

/** MVP, ACE or the position (1st-10th) according to the match grade. */
export function Placement({
  badge,
  placement,
  className,
}: Pick<Participant, "badge" | "placement"> & { className?: string }) {
  const base = "grid h-6 place-items-center text-xs font-black tracking-field tabular-nums";
  if (badge) {
    const { title, className: look } = BADGES[badge];
    return (
      <span title={title} className={cn(base, look, className)}>
        {badge}
      </span>
    );
  }
  return <span className={cn(base, "border border-line font-bold text-subtle", className)}>{ordinal(placement)}</span>;
}

function Metric({ value, label, className }: { value: string; label: string; className?: string }) {
  return (
    <div className={cn("text-right", className)}>
      <p className="text-sm font-black text-text tabular-nums">{value}</p>
      <p className="text-xs text-subtle">{label}</p>
    </div>
  );
}

function ParticipantRow({
  participant,
  maxDamage,
  tracked,
  rank,
}: {
  participant: Participant;
  maxDamage: number;
  tracked: boolean;
  rank: PlayerRank | undefined;
}) {
  const support = participant.role === "SUPPORT";
  const [spell1 = 0, spell2 = 0] = participant.spells;
  const [item0 = 0, item1 = 0, item2 = 0, item3 = 0, item4 = 0, item5 = 0] = participant.items;

  return (
    <li className={cn("relative grid items-center gap-x-3 px-4 py-2 sm:px-5", ROW_GRID, tracked && "bg-acid/[0.06]")}>
      {tracked && <span aria-hidden="true" className="absolute inset-y-0 left-0 w-[3px] bg-acid" />}
      <Placement badge={participant.badge} placement={participant.placement} />

      <div className="relative w-fit">
        <ChampionIcon name={participant.champion} size={32} />
        <span className="absolute -right-1.5 -bottom-1 min-w-4 bg-ink px-0.5 text-center text-xs font-black text-soft tabular-nums">
          {participant.champion_level}
        </span>
      </div>

      <div className="min-w-0">
        <p className={cn("truncate text-sm font-black", tracked ? "text-acid" : "text-text")}>
          {participant.game_name || "Unknown"}
          <span className="font-normal text-subtle">#{participant.tag_line}</span>
        </p>
        <p className="flex min-w-0 items-center gap-1 text-xs text-subtle">
          <span className="truncate">
            {participant.champion} · {roleLabel(participant.role)}
          </span>
          {rank && (
            <span className="flex shrink-0 items-center gap-0.5 font-bold text-soft">
              <span aria-hidden="true">·</span>
              {/* the emblem already states the rank: beside it, only the division and LP (the name, for screen readers) */}
              {rank.tier && <img src={rankImage(rank.tier)} alt="" className="size-4" />}
              <span className="sr-only">{rankLabel(rank.tier, rank.division, rank.lp)}</span>
              <span aria-hidden="true" title={rankLabel(rank.tier, rank.division, rank.lp)}>
                {lpLabel(rank.tier, rank.division, rank.lp)}
              </span>
            </span>
          )}
        </p>
      </div>

      <div className="hidden grid-cols-2 gap-0.5 lg:grid">
        <SpellIcon spellId={spell1} size={18} />
        <RuneIcon runeId={participant.keystone} size={18} />
        <SpellIcon spellId={spell2} size={18} />
        <RuneIcon runeId={participant.secondary_tree} size={18} />
      </div>

      <div role="group" aria-label="Items" className="hidden grid-cols-4 gap-0.5 lg:grid">
        <ItemIcon itemId={item0} size={21} />
        <ItemIcon itemId={item1} size={21} />
        <ItemIcon itemId={item2} size={21} />
        <ItemIcon itemId={participant.trinket} size={21} />
        <ItemIcon itemId={item3} size={21} />
        <ItemIcon itemId={item4} size={21} />
        <ItemIcon itemId={item5} size={21} />
      </div>

      <div className="text-right">
        <p className="text-sm font-black text-text tabular-nums">
          {participant.kills}/<span className="text-stat-red">{participant.deaths}</span>/{participant.assists}
        </p>
        <p className={cn("text-xs tabular-nums", toneText[statTone("kda", participant.kda_status)])}>{formatNumber(participant.kda, 2)} KDA</p>
      </div>

      <Metric className="hidden sm:block" value={formatPercent(participant.kill_participation, 0)} label="KP" />
      <Metric
        className="hidden sm:block"
        value={formatNumber(support ? participant.vision_per_min : participant.cs_per_min, 1)}
        label={support ? "Vision/min" : "CS/min"}
      />

      <div className="hidden min-w-0 sm:block">
        <div className="h-1.5 bg-white/[0.08]" aria-hidden="true">
          <div
            className={cn("h-full", tracked ? "bg-acid" : "bg-muted/60")}
            style={{ width: `${(participant.damage / maxDamage) * 100}%` }}
          />
        </div>
        <p className="mt-1 truncate text-xs text-subtle tabular-nums">
          <span className="font-bold text-soft">{formatCompact(participant.damage)}</span> ({formatNumber(participant.damage_per_min, 0)}/m)
        </p>
      </div>

      <p
        className={cn("text-right text-sm font-black tabular-nums", toneText[scoreTone(participant.score)])}
        title="Score vs. Challenger games in this role (70 = better than 2 in 3 Challenger games)"
      >
        {participant.score}
      </p>
    </li>
  );
}

function TeamBlock({
  team,
  maxDamage,
  trackedPuuid,
  ranks,
}: {
  team: Team;
  maxDamage: number;
  trackedPuuid: string | undefined;
  ranks: Map<string, PlayerRank>;
}) {
  const side = team.team_id === 100 ? "Blue" : "Red";
  const result = team.win ? "Victory" : "Defeat";
  return (
    <section aria-label={`${result}, ${side} side`} className="border-b border-line last:border-b-0">
      <header className="flex flex-wrap items-center gap-x-6 gap-y-2 border-b border-line bg-white/[0.02] px-4 py-2.5 sm:px-5">
        <h4 className={cn("text-sm font-black", team.win ? "text-stat-blue" : "text-stat-red")}>
          {result}
          <span className="ml-2 text-xs font-bold text-subtle">{side} side</span>
        </h4>
        <ul className="flex flex-wrap items-center gap-x-4 gap-y-1">
          {OBJECTIVES.map(({ key, label, icon }) => (
            <li key={key} title={label} className="flex items-center gap-1.5">
              {icon ? (
                <img src={`${OBJECTIVE_ICONS}/${icon}.png`} alt="" width={20} height={20} loading="lazy" className="size-5" />
              ) : (
                <Swords className="size-3.5 text-subtle" aria-hidden="true" />
              )}
              <span className="text-sm font-black text-text tabular-nums">{team[key]}</span>
              <span className="sr-only">{label}</span>
            </li>
          ))}
        </ul>
      </header>
      <ul>
        {team.participants.map((participant) => (
          <ParticipantRow
            key={`${participant.puuid}-${participant.champion}`}
            participant={participant}
            maxDamage={maxDamage}
            tracked={participant.puuid === trackedPuuid}
            rank={ranks.get(participant.puuid)}
          />
        ))}
      </ul>
    </section>
  );
}

/** The lobby's average elo, taken the first time the match was opened. */
function LobbyRankBar({ lobby }: { lobby: UseQueryResult<LobbyRank> }) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-line px-4 py-2.5 sm:px-5">
      <span className="microtext text-subtle">Lobby avg</span>
      {lobby.isPending ? (
        <Skeleton className="h-5 w-40" />
      ) : lobby.isError || !lobby.data.tier ? (
        <span className="text-sm text-subtle">Unavailable</span>
      ) : (
        <span className="flex items-center gap-1.5">
          <img src={rankImage(lobby.data.tier)} alt="" className="size-6" />
          <span className="sr-only">{rankLabel(lobby.data.tier, lobby.data.division, lobby.data.lp)}</span>
          <span
            aria-hidden="true"
            title={rankLabel(lobby.data.tier, lobby.data.division, lobby.data.lp)}
            className="text-sm font-black text-text tabular-nums"
          >
            {lpLabel(lobby.data.tier, lobby.data.division, lobby.data.lp)}
          </span>
        </span>
      )}
    </div>
  );
}

/** The 10 participants of a match, with the winning team first. */
export function MatchDetails({ matchId, trackedPuuid }: { matchId: string; trackedPuuid: string | undefined }) {
  const details = useQuery({
    queryKey: queryKeys.matchDetails(matchId),
    queryFn: () => unwrap(api.GET("/matches/{match_id}/details", { params: { path: { match_id: matchId } } })),
    // A finished match doesn't change.
    staleTime: Number.POSITIVE_INFINITY,
  });
  // Requested only on expanding, along with the details; the API stores it the first time and it doesn't change.
  const lobby = useQuery({
    queryKey: queryKeys.matchLobbyRank(matchId),
    queryFn: () => unwrap(api.GET("/matches/{match_id}/lobby-rank", { params: { path: { match_id: matchId } } })),
    staleTime: Number.POSITIVE_INFINITY,
    retry: false,
  });

  if (details.isPending) {
    return (
      <div aria-busy="true" aria-label="Loading match details" className="flex flex-col gap-1.5 border-t border-line px-5 py-4">
        {Array.from({ length: 10 }, (_, index) => (
          <Skeleton key={index} className="h-9" />
        ))}
      </div>
    );
  }
  if (details.isError) {
    return (
      <div className="border-t border-line">
        <ErrorState className="py-8" error={details.error} onRetry={() => void details.refetch()} />
      </div>
    );
  }

  const teams = [...details.data.teams].sort((a, b) => Number(b.win) - Number(a.win));
  const maxDamage = Math.max(1, ...teams.flatMap((team) => team.participants.map((participant) => participant.damage)));
  const ranks = new Map((lobby.data?.players ?? []).map((rank) => [rank.puuid, rank]));

  return (
    <div className="animate-rise border-t border-line bg-ink-soft/70">
      <LobbyRankBar lobby={lobby} />
      {teams.map((team) => (
        <TeamBlock key={team.team_id} team={team} maxDamage={maxDamage} trackedPuuid={trackedPuuid} ranks={ranks} />
      ))}
    </div>
  );
}
