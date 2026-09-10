import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, GitCompareArrows, RefreshCw, Sparkles, Trash } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router";

import { NotFound } from "@/app/RouteError";
import { ChampionIcon, ProfileIcon, RankBadge, RoleIcon, WinRate } from "@/components/player/PlayerBits";
import { Button, buttonClasses } from "@/components/ui/Button";
import { Card, CardHeader, Skeleton } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Select, Textarea } from "@/components/ui/Field";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { CreateSnapshotDialog } from "@/features/snapshots/CreateSnapshotDialog";
import { api, isApiError, unwrap, type Schemas } from "@/lib/api/client";
import { cn } from "@/lib/cn";
import { formatDate, formatDuration, formatNumber, formatPercent, formatSigned, timeAgo } from "@/lib/format";
import { palette } from "@/lib/palette";
import { parseId } from "@/lib/params";
import { queryKeys } from "@/lib/queryKeys";
import { normalizeTier, RANK_COLORS } from "@/lib/rank";
import { PLAYABLE_ROLES, regionLabel, roleLabel, type Role } from "@/lib/roles";
import { kdaTone, toneText, winRateTone } from "@/lib/stats";

import { playerUpdate, updateCachedPlayer } from "./cache";

type Player = Schemas["PlayerResponse"];
type Snapshot = Schemas["SnapshotResponse"];

export function PlayerDetailPage() {
  const playerId = parseId(useParams().playerId);
  if (playerId === null) return <NotFound />;
  return <PlayerDetail key={playerId} playerId={playerId} />;
}

function PlayerDetail({ playerId }: { playerId: number }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const navigate = useNavigate();
  const [analysisOpen, setAnalysisOpen] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const player = useQuery({
    queryKey: queryKeys.player(playerId),
    queryFn: () => unwrap(api.GET("/players/{player_id}", { params: { path: { player_id: playerId } } })),
  });

  const refresh = useMutation({
    mutationFn: () => unwrap(api.POST("/players/{player_id}/refresh", { params: { path: { player_id: playerId } } })),
    onSuccess: (updated) => {
      updateCachedPlayer(queryClient, updated);
      toast.success("Rank and icon updated");
    },
    onError: (error) => toast.error(error.message),
  });

  const remove = useMutation({
    mutationFn: () => unwrap(api.DELETE("/players/{player_id}", { params: { path: { player_id: playerId } } })),
    onSuccess: () => {
      toast.success("Player deleted");
      void navigate("/players", { replace: true });
      void queryClient.invalidateQueries({ queryKey: queryKeys.playerList() });
    },
    onError: (error) => toast.error(error.message),
  });

  if (player.isPending) return <PlayerSkeleton />;
  if (player.isError) {
    if (isApiError(player.error, 404)) return <NotFound />;
    return (
      <Card>
        <ErrorState error={player.error} onRetry={() => void player.refetch()} />
      </Card>
    );
  }

  return (
    <>
      <Link to="/players" className="mb-3 inline-flex items-center gap-1 text-xs text-muted hover:text-fg">
        <ArrowLeft className="size-3.5" aria-hidden="true" />
        All players
      </Link>

      <PlayerHeader
        player={player.data}
        refreshing={refresh.isPending}
        onRefresh={() => refresh.mutate()}
        onAnalyse={() => setAnalysisOpen(true)}
        onDelete={() => setConfirmDelete(true)}
      />

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <div className="flex min-w-0 flex-col gap-6 lg:col-span-2">
          <SnapshotsPanel playerId={playerId} onAnalyse={() => setAnalysisOpen(true)} />
          <RecentMatchesPanel playerId={playerId} />
        </div>
        <div className="flex min-w-0 flex-col gap-6">
          <RoleSummaryPanel playerId={playerId} />
          <MostPlayedPanel playerId={playerId} />
          <NotesPanel key={player.data.notes ?? ""} player={player.data} />
        </div>
      </div>

      <CreateSnapshotDialog playerId={playerId} open={analysisOpen} onOpenChange={setAnalysisOpen} />
      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title={`Delete ${player.data.game_name}#${player.data.tag_line}?`}
        description="Its snapshots are deleted too. Stored matches are kept for other players."
        loading={remove.isPending}
        onConfirm={() => remove.mutate()}
      />
    </>
  );
}

function PlayerSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading player" className="flex flex-col gap-6">
      <Skeleton className="h-40 w-full rounded-xl" />
      <div className="grid gap-6 lg:grid-cols-3">
        <Skeleton className="h-72 rounded-xl lg:col-span-2" />
        <Skeleton className="h-72 rounded-xl" />
      </div>
    </div>
  );
}

// ── Cabecera ──────────────────────────────────────────────────────────────────

function PlayerHeader({
  player,
  refreshing,
  onRefresh,
  onAnalyse,
  onDelete,
}: {
  player: Player;
  refreshing: boolean;
  onRefresh: () => void;
  onAnalyse: () => void;
  onDelete: () => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const tier = normalizeTier(player.tier);
  const region = player.region.toUpperCase();

  // Para la barra de progreso de Master y Grandmaster hacen falta los cortes de LP de la región.
  const cutoffs = useQuery({
    queryKey: queryKeys.cutoffs(region),
    queryFn: () => unwrap(api.GET("/league/cutoffs", { params: { query: { region } } })),
    enabled: tier === "MASTER" || tier === "GRANDMASTER",
    staleTime: 10 * 60_000,
  });

  const updateRole = useMutation({
    mutationFn: (role: Role) =>
      unwrap(
        api.PUT("/players/{player_id}", {
          params: { path: { player_id: player.id } },
          body: playerUpdate(player, { role }),
        }),
      ),
    onSuccess: (updated) => {
      updateCachedPlayer(queryClient, updated);
      toast.success(`Main role set to ${roleLabel(updated.role)}`);
    },
    onError: (error) => toast.error(error.message),
  });

  const glow = tier ? RANK_COLORS[tier] : palette.primary;

  return (
    <Card className="relative overflow-hidden p-5 sm:p-6">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-28 -right-20 size-80 rounded-full opacity-20 blur-3xl"
        style={{ background: glow }}
      />
      <div className="relative flex flex-col gap-5 md:flex-row md:items-center">
        <ProfileIcon iconId={player.profile_icon_id} name={player.game_name} size={80} className="ring-2 ring-primary/40" />
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-2xl font-bold text-fg">
            {player.game_name}
            <span className="font-medium text-muted">#{player.tag_line}</span>
          </h1>
          <p className="mt-1 flex flex-wrap items-center gap-2 text-sm text-muted">
            <span className="rounded bg-surface-2 px-1.5 py-0.5 text-xs font-semibold text-fg">{regionLabel(player.region)}</span>
            {player.nickname && <span>{player.nickname}</span>}
          </p>
          <div className="mt-4 flex flex-wrap items-center gap-x-8 gap-y-4">
            <RankBadge
              tier={player.tier}
              division={player.rank}
              lp={player.lp}
              size={52}
              showProgress
              cutoffs={
                cutoffs.data
                  ? { grandmaster: cutoffs.data.grandmaster_cutoff_lp, challenger: cutoffs.data.challenger_cutoff_lp }
                  : undefined
              }
            />
            <WinRate wins={player.wins ?? 0} losses={player.losses ?? 0} />
            <label className="flex items-center gap-2 text-xs text-muted">
              <RoleIcon role={player.role} size={18} />
              <span className="sr-only">Main role</span>
              <Select
                className="h-8 w-32 text-xs"
                value={player.role}
                disabled={updateRole.isPending}
                onChange={(event) => updateRole.mutate(event.target.value as Role)}
              >
                {[...PLAYABLE_ROLES, "ALL" as const].map((role) => (
                  <option key={role} value={role}>
                    {roleLabel(role)}
                  </option>
                ))}
              </Select>
            </label>
          </div>
        </div>
        <div className="flex flex-wrap gap-2 md:flex-col md:items-stretch">
          <Button onClick={onAnalyse}>
            <Sparkles className="size-4" aria-hidden="true" />
            New analysis
          </Button>
          <Button variant="outline" loading={refreshing} onClick={onRefresh}>
            {!refreshing && <RefreshCw className="size-4" aria-hidden="true" />}
            Update rank
          </Button>
          <Button variant="danger" onClick={onDelete}>
            <Trash className="size-4" aria-hidden="true" />
            Delete
          </Button>
        </div>
      </div>
    </Card>
  );
}

// ── Snapshots ─────────────────────────────────────────────────────────────────

function SnapshotsPanel({ playerId, onAnalyse }: { playerId: number; onAnalyse: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [selected, setSelected] = useState<number[]>([]);
  const [toDelete, setToDelete] = useState<Snapshot | null>(null);

  const snapshots = useQuery({
    queryKey: queryKeys.snapshots(playerId),
    queryFn: () =>
      unwrap(api.GET("/snapshots/player/{player_id}", { params: { path: { player_id: playerId }, query: { limit: 100 } } })),
  });

  const remove = useMutation({
    mutationFn: (snapshotId: number) =>
      unwrap(api.DELETE("/snapshots/{snapshot_id}", { params: { path: { snapshot_id: snapshotId } } })),
    onSuccess: async (_, snapshotId) => {
      setToDelete(null);
      setSelected((current) => current.filter((id) => id !== snapshotId));
      toast.success("Snapshot deleted");
      await queryClient.invalidateQueries({ queryKey: queryKeys.snapshots(playerId) });
    },
    onError: (error) => toast.error(error.message),
  });

  // Como mucho dos seleccionados: al marcar un tercero se descarta el más antiguo.
  const toggle = (snapshotId: number) =>
    setSelected((current) =>
      current.includes(snapshotId) ? current.filter((id) => id !== snapshotId) : [...current.slice(-1), snapshotId],
    );

  const items = snapshots.data?.items ?? [];
  const [first, second] = selected
    .map((id) => items.find((snapshot) => snapshot.id === id))
    .filter((snapshot): snapshot is Snapshot => snapshot !== undefined)
    .sort((a, b) => a.date_from.localeCompare(b.date_from));

  return (
    <Card>
      <CardHeader
        title="Snapshots"
        description="Each analysis freezes a period of ranked games."
        action={
          first && second ? (
            <Link
              to={`/players/${playerId}/snapshots/compare?a=${first.id}&b=${second.id}`}
              className={buttonClasses({ variant: "outline", size: "sm" })}
            >
              <GitCompareArrows className="size-3.5" aria-hidden="true" />
              Compare
            </Link>
          ) : items.length > 1 ? (
            <span className="text-xs text-muted">Select two to compare</span>
          ) : undefined
        }
      />
      {snapshots.isPending ? (
        <div className="flex flex-col gap-3 p-5">
          <Skeleton className="h-12" />
          <Skeleton className="h-12" />
        </div>
      ) : snapshots.isError ? (
        <ErrorState error={snapshots.error} onRetry={() => void snapshots.refetch()} />
      ) : items.length === 0 ? (
        <EmptyState
          icon={<Sparkles className="size-9" />}
          title="No analyses yet"
          description="Pick a date range and YGG will download and analyse those games."
          action={
            <Button size="sm" onClick={onAnalyse}>
              Run the first analysis
            </Button>
          }
        />
      ) : (
        <ul className="divide-y divide-border/50">
          {items.map((snapshot) => {
            const range = `${formatDate(snapshot.date_from)} – ${formatDate(snapshot.date_to)}`;
            return (
              <li key={snapshot.id} className="flex items-center gap-3 px-5 py-3 transition hover:bg-surface-2/40">
                <input
                  type="checkbox"
                  className="size-4 cursor-pointer accent-[#9e5ae2]"
                  checked={selected.includes(snapshot.id)}
                  onChange={() => toggle(snapshot.id)}
                  aria-label={`Select ${range} for comparison`}
                />
                <Link to={`/players/${playerId}/snapshots/${snapshot.id}`} className="group min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-fg group-hover:text-primary-light">{range}</p>
                  <p className="truncate text-xs text-muted">
                    {snapshot.match_count} games
                    {snapshot.description ? ` · ${snapshot.description}` : ""}
                  </p>
                </Link>
                <Button variant="ghost" size="icon" aria-label={`Delete snapshot ${range}`} onClick={() => setToDelete(snapshot)}>
                  <Trash className="size-4" aria-hidden="true" />
                </Button>
              </li>
            );
          })}
        </ul>
      )}
      <ConfirmDialog
        open={toDelete !== null}
        onOpenChange={(open) => {
          if (!open) setToDelete(null);
        }}
        title="Delete this snapshot?"
        description="The analysis is removed. Its matches stay stored and are reused by future analyses."
        loading={remove.isPending}
        onConfirm={() => {
          if (toDelete) remove.mutate(toDelete.id);
        }}
      />
    </Card>
  );
}

// ── Partidas recientes ────────────────────────────────────────────────────────

function RecentMatchesPanel({ playerId }: { playerId: number }) {
  const queryClient = useQueryClient();
  const toast = useToast();

  const matches = useQuery({
    queryKey: queryKeys.playerMatches(playerId),
    queryFn: () =>
      unwrap(api.GET("/matches/player/{player_id}", { params: { path: { player_id: playerId }, query: { limit: 10 } } })),
  });

  const sync = useMutation({
    mutationFn: () =>
      unwrap(
        api.GET("/matches/player/{player_id}", {
          params: { path: { player_id: playerId }, query: { limit: 10, sync: true } },
        }),
      ),
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.playerMatches(playerId), data);
      void queryClient.invalidateQueries({ queryKey: queryKeys.playerSummary(playerId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.mostPlayed(playerId) });
      toast.success("Match history synced");
    },
    onError: (error) => toast.error(error.message),
  });

  return (
    <Card>
      <CardHeader
        title="Recent matches"
        description="Latest ranked games stored for this player."
        action={
          <Button variant="ghost" size="sm" loading={sync.isPending} onClick={() => sync.mutate()}>
            {!sync.isPending && <RefreshCw className="size-3.5" aria-hidden="true" />}
            Sync
          </Button>
        }
      />
      {matches.isPending ? (
        <div className="flex flex-col gap-3 p-5">
          {Array.from({ length: 4 }, (_, index) => (
            <Skeleton key={index} className="h-12" />
          ))}
        </div>
      ) : matches.isError ? (
        <ErrorState error={matches.error} onRetry={() => void matches.refetch()} />
      ) : matches.data.length === 0 ? (
        <EmptyState title="No matches stored" description="Sync to download the latest ranked games from Riot." />
      ) : (
        <ul className="divide-y divide-border/50">
          {matches.data.map((match) => (
            <li key={match.match_id} className="flex items-center gap-3 py-2.5 pr-5 pl-3">
              <span
                className={cn("w-1 self-stretch rounded-full", match.win ? "bg-stat-blue" : "bg-stat-red")}
                aria-hidden="true"
              />
              <ChampionIcon name={match.champion} size={36} />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-fg">
                  {match.champion}
                  <span className={cn("ml-2 text-xs font-bold", match.win ? "text-stat-blue" : "text-stat-red")}>
                    {match.win ? "Victory" : "Defeat"}
                  </span>
                </p>
                <p className="truncate text-xs text-muted">
                  {roleLabel(match.player_role)} · {formatDuration(match.duration)} ·{" "}
                  <time dateTime={match.creation_time}>{timeAgo(match.creation_time)}</time>
                </p>
              </div>
              <div className="text-right">
                <p className="text-sm text-fg tabular-nums">
                  {match.kills}/<span className="text-stat-red">{match.deaths}</span>/{match.assists}
                </p>
                <p className={cn("text-xs tabular-nums", toneText[kdaTone(match.kda)])}>{formatNumber(match.kda, 2)} KDA</p>
              </div>
              <div className="hidden w-16 text-right sm:block">
                <p className="text-sm text-fg tabular-nums">{formatNumber(match.cs_per_min, 1)}</p>
                <p className="text-xs text-muted">CS/min</p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

// ── Columna lateral ───────────────────────────────────────────────────────────

function RoleSummaryPanel({ playerId }: { playerId: number }) {
  const summary = useQuery({
    queryKey: queryKeys.playerSummary(playerId),
    queryFn: () => unwrap(api.GET("/players/{player_id}/summary", { params: { path: { player_id: playerId } } })),
  });

  return (
    <Card>
      <CardHeader title="By role" description="All stored games." />
      {summary.isPending ? (
        <Skeleton className="m-5 h-24" />
      ) : summary.isError ? (
        <ErrorState error={summary.error} onRetry={() => void summary.refetch()} />
      ) : summary.data.length === 0 ? (
        <EmptyState title="No games yet" />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[11px] tracking-wider text-muted uppercase">
                <th scope="col" className="px-5 py-2 font-semibold">
                  Role
                </th>
                <th scope="col" className="px-2 py-2 text-right font-semibold">
                  WR
                </th>
                <th scope="col" className="px-2 py-2 text-right font-semibold">
                  KDA
                </th>
                <th scope="col" className="px-5 py-2 text-right font-semibold">
                  GD@14
                </th>
              </tr>
            </thead>
            <tbody>
              {summary.data.map((row) => (
                <tr key={row.role} className="border-t border-border/40">
                  <th scope="row" className="px-5 py-2 text-left font-normal">
                    <span className="flex items-center gap-2">
                      <RoleIcon role={row.role} size={18} />
                      <span className="text-fg">{roleLabel(row.role)}</span>
                      <span className="text-xs text-muted">{row.games}</span>
                    </span>
                  </th>
                  <td className={cn("px-2 py-2 text-right tabular-nums", toneText[winRateTone(row.win_rate)])}>
                    {formatPercent(row.win_rate, 0)}
                  </td>
                  <td className={cn("px-2 py-2 text-right tabular-nums", toneText[kdaTone(row.kda)])}>
                    {formatNumber(row.kda, 2)}
                  </td>
                  <td
                    className={cn(
                      "px-5 py-2 text-right tabular-nums",
                      row.gold_diff_14 === null ? "text-muted" : row.gold_diff_14 >= 0 ? "text-stat-green" : "text-stat-red",
                    )}
                  >
                    {row.gold_diff_14 === null ? "—" : formatSigned(row.gold_diff_14)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function MostPlayedPanel({ playerId }: { playerId: number }) {
  const champions = useQuery({
    queryKey: queryKeys.mostPlayed(playerId),
    queryFn: () =>
      unwrap(api.GET("/matches/player/{player_id}/most-played", { params: { path: { player_id: playerId } } })),
  });

  return (
    <Card>
      <CardHeader title="Most played" />
      {champions.isPending ? (
        <Skeleton className="m-5 h-24" />
      ) : champions.isError ? (
        <ErrorState error={champions.error} onRetry={() => void champions.refetch()} />
      ) : champions.data.length === 0 ? (
        <EmptyState title="No champions yet" />
      ) : (
        <ul className="flex flex-col gap-1 p-3">
          {champions.data.slice(0, 6).map((champion) => (
            <li key={champion.champion_name} className="flex items-center gap-3 rounded-lg px-2 py-1.5">
              <ChampionIcon name={champion.champion_name} size={32} />
              <span className="min-w-0 flex-1 truncate text-sm font-medium text-fg">{champion.champion_name}</span>
              <span className="text-xs text-muted tabular-nums">{champion.games_played} games</span>
              <span className={cn("w-10 text-right text-sm font-semibold tabular-nums", toneText[winRateTone(champion.win_rate)])}>
                {formatPercent(champion.win_rate, 0)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function NotesPanel({ player }: { player: Player }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const saved = player.notes ?? "";
  const [notes, setNotes] = useState(saved);

  const save = useMutation({
    mutationFn: () =>
      unwrap(api.PUT("/players/{player_id}", { params: { path: { player_id: player.id } }, body: playerUpdate(player, { notes }) })),
    onSuccess: (updated) => {
      updateCachedPlayer(queryClient, updated);
      toast.success("Notes saved");
    },
    onError: (error) => toast.error(error.message),
  });

  return (
    <Card>
      <CardHeader title="Coach notes" />
      <form
        className="flex flex-col gap-3 p-5"
        onSubmit={(event) => {
          event.preventDefault();
          save.mutate();
        }}
      >
        <label htmlFor="player-notes" className="sr-only">
          Notes
        </label>
        <Textarea
          id="player-notes"
          value={notes}
          maxLength={1000}
          placeholder="Habits, goals, things to review…"
          onChange={(event) => setNotes(event.target.value)}
        />
        {notes !== saved && (
          <div className="flex justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={() => setNotes(saved)}>
              Discard
            </Button>
            <Button type="submit" size="sm" loading={save.isPending}>
              Save notes
            </Button>
          </div>
        )}
      </form>
    </Card>
  );
}
