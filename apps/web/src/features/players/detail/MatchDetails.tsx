import { useQuery } from "@tanstack/react-query";
import { Bug, Castle, Crown, Eye, Flame, Swords, type LucideIcon } from "lucide-react";

import { ChampionIcon, ItemIcon, RuneIcon, SpellIcon } from "@/components/player/PlayerBits";
import { Skeleton } from "@/components/ui/Card";
import { ErrorState } from "@/components/ui/States";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { cn } from "@/lib/cn";
import { formatCompact, formatNumber, formatPercent } from "@/lib/format";
import { queryKeys } from "@/lib/queryKeys";
import { roleLabel } from "@/lib/roles";
import { kdaTone, scoreTone, toneText } from "@/lib/stats";

type Team = Schemas["MatchTeamDetails"];
type Participant = Schemas["MatchParticipantDetails"];

const OBJECTIVES = [
  { key: "kills", label: "Kills", icon: Swords },
  { key: "towers", label: "Towers", icon: Castle },
  { key: "dragons", label: "Dragons", icon: Flame },
  { key: "barons", label: "Barons", icon: Crown },
  { key: "heralds", label: "Heralds", icon: Eye },
  { key: "grubs", label: "Void grubs", icon: Bug },
] as const satisfies readonly { key: keyof Team; label: string; icon: LucideIcon }[];

// placement · campeón · jugador · hechizos y runas · objetos · KDA · KP · CS · daño · puntuación
const ROW_GRID =
  "grid-cols-[40px_32px_minmax(0,1fr)_64px_32px] sm:grid-cols-[46px_32px_minmax(0,1fr)_72px_48px_58px_minmax(84px,1fr)_36px] " +
  "lg:grid-cols-[46px_32px_minmax(96px,1fr)_40px_92px_72px_48px_58px_minmax(92px,1fr)_36px]";

function ordinal(position: number): string {
  if (position === 1) return "1st";
  if (position === 2) return "2nd";
  if (position === 3) return "3rd";
  return `${position}th`;
}

function Placement({ participant }: { participant: Participant }) {
  const base = "grid h-6 place-items-center text-[10px] font-black tracking-[0.06em] tabular-nums";
  if (participant.badge === "MVP") return <span className={cn(base, "bg-acid text-on-acid")}>MVP</span>;
  if (participant.badge === "ACE") return <span className={cn(base, "border border-acid/60 text-acid")}>ACE</span>;
  return <span className={cn(base, "border border-line font-bold text-subtle")}>{ordinal(participant.placement)}</span>;
}

function Metric({ value, label, className }: { value: string; label: string; className?: string }) {
  return (
    <div className={cn("text-right", className)}>
      <p className="text-[13px] font-extrabold text-text tabular-nums">{value}</p>
      <p className="text-[10px] text-subtle">{label}</p>
    </div>
  );
}

function ParticipantRow({ participant, maxDamage, tracked }: { participant: Participant; maxDamage: number; tracked: boolean }) {
  const support = participant.role === "SUPPORT";
  const [spell1 = 0, spell2 = 0] = participant.spells;
  const [item0 = 0, item1 = 0, item2 = 0, item3 = 0, item4 = 0, item5 = 0] = participant.items;

  return (
    <li className={cn("relative grid items-center gap-x-3 px-4 py-2 sm:px-5", ROW_GRID, tracked && "bg-acid/[0.06]")}>
      {tracked && <span aria-hidden="true" className="absolute inset-y-0 left-0 w-[3px] bg-acid" />}
      <Placement participant={participant} />

      <div className="relative w-fit">
        <ChampionIcon name={participant.champion} size={32} />
        <span className="absolute -right-1.5 -bottom-1 min-w-4 bg-ink px-0.5 text-center text-[9px] font-black text-soft tabular-nums">
          {participant.champion_level}
        </span>
      </div>

      <div className="min-w-0">
        <p className={cn("truncate text-[13px] font-extrabold", tracked ? "text-acid" : "text-text")}>
          {participant.game_name || "Unknown"}
          <span className="font-medium text-subtle">#{participant.tag_line}</span>
        </p>
        <p className="truncate text-[11px] text-subtle">
          {participant.champion} · {roleLabel(participant.role)}
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
        <p className="text-[13px] font-extrabold text-text tabular-nums">
          {participant.kills}/<span className="text-stat-red">{participant.deaths}</span>/{participant.assists}
        </p>
        <p className={cn("text-[10px] tabular-nums", toneText[kdaTone(participant.kda)])}>{formatNumber(participant.kda, 2)} KDA</p>
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
        <p className="mt-1 truncate text-[11px] text-subtle tabular-nums">
          <span className="font-bold text-soft">{formatCompact(participant.damage)}</span> ({formatNumber(participant.damage_per_min, 0)}/m)
        </p>
      </div>

      <p
        className={cn("text-right text-[15px] font-black tabular-nums", toneText[scoreTone(participant.score)])}
        title="Performance score in this match (best player = 100)"
      >
        {participant.score}
      </p>
    </li>
  );
}

function TeamBlock({ team, maxDamage, trackedPuuid }: { team: Team; maxDamage: number; trackedPuuid: string | undefined }) {
  const side = team.team_id === 100 ? "Blue" : "Red";
  const result = team.win ? "Victory" : "Defeat";
  return (
    <section aria-label={`${result}, ${side} side`} className="border-b border-line last:border-b-0">
      <header className="flex flex-wrap items-center gap-x-6 gap-y-2 border-b border-line bg-white/[0.02] px-4 py-2.5 sm:px-5">
        <h4 className={cn("text-sm font-black", team.win ? "text-stat-blue" : "text-stat-red")}>
          {result}
          <span className="ml-2 text-[11px] font-bold text-subtle">{side} side</span>
        </h4>
        <ul className="flex flex-wrap items-center gap-x-4 gap-y-1">
          {OBJECTIVES.map(({ key, label, icon: Icon }) => (
            <li key={key} title={label} className="flex items-center gap-1.5">
              <Icon className="size-3.5 text-subtle" aria-hidden="true" />
              <span className="text-[13px] font-extrabold text-text tabular-nums">{team[key]}</span>
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
          />
        ))}
      </ul>
    </section>
  );
}

/** Los 10 participantes de una partida, con el equipo ganador primero. */
export function MatchDetails({ matchId, trackedPuuid }: { matchId: string; trackedPuuid: string | undefined }) {
  const details = useQuery({
    queryKey: queryKeys.matchDetails(matchId),
    queryFn: () => unwrap(api.GET("/matches/{match_id}/details", { params: { path: { match_id: matchId } } })),
    // Una partida terminada no cambia.
    staleTime: Number.POSITIVE_INFINITY,
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

  return (
    <div className="animate-rise border-t border-line bg-ink-soft/70">
      {teams.map((team) => (
        <TeamBlock key={team.team_id} team={team} maxDamage={maxDamage} trackedPuuid={trackedPuuid} />
      ))}
    </div>
  );
}
