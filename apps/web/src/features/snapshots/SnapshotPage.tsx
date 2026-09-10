import { useMutation, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";
import { ArrowLeft, GitCompareArrows, Trash } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";

import { PageHeader } from "@/app/AppLayout";
import { NotFound } from "@/app/RouteError";
import { DeathHeatmap } from "@/components/charts/DeathHeatmap";
import { DeathsByPhase } from "@/components/charts/DeathsByPhase";
import { MetricGrid } from "@/components/charts/MetricGrid";
import { PerformanceRadar, type RadarSeries } from "@/components/charts/PerformanceRadar";
import { TrendChart } from "@/components/charts/TrendChart";
import { ChampionIcon } from "@/components/player/PlayerBits";
import { Button, buttonClasses } from "@/components/ui/Button";
import { Card, CardHeader, Skeleton } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Input, Select, Textarea } from "@/components/ui/Field";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/Overlay";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { api, isApiError, unwrap } from "@/lib/api/client";
import { cn } from "@/lib/cn";
import { ddragonUrl, useDDragon } from "@/lib/ddragon";
import { formatDate, formatPercent } from "@/lib/format";
import { deathPoints } from "@/lib/heatmap";
import { palette } from "@/lib/palette";
import { parseId } from "@/lib/params";
import { queryKeys } from "@/lib/queryKeys";
import { normalizeTier, RANK_COLORS, tierOrder } from "@/lib/rank";
import { parseRiotId } from "@/lib/riotId";
import { REGIONS, roleLabel } from "@/lib/roles";
import { toneText, winRateTone } from "@/lib/stats";

import { MatchTable } from "./MatchTable";
import { compareKey, fetchDashboard, useSnapshotMatches, type CompareTarget, type Dashboard, type Match } from "./queries";

export function SnapshotPage() {
  const params = useParams();
  const playerId = parseId(params.playerId);
  const snapshotId = parseId(params.snapshotId);
  if (playerId === null || snapshotId === null) return <NotFound />;
  return <SnapshotDashboard key={snapshotId} playerId={playerId} snapshotId={snapshotId} />;
}

function SnapshotDashboard({ playerId, snapshotId }: { playerId: number; snapshotId: number }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") === "matches" ? "matches" : "overview";
  const champion = params.get("champion");
  const [confirmDelete, setConfirmDelete] = useState(false);

  const dashboard = useQuery({
    queryKey: queryKeys.dashboard(snapshotId),
    queryFn: () => fetchDashboard(snapshotId),
    staleTime: 5 * 60_000,
  });
  const matches = useSnapshotMatches(snapshotId);

  const remove = useMutation({
    mutationFn: () => unwrap(api.DELETE("/snapshots/{snapshot_id}", { params: { path: { snapshot_id: snapshotId } } })),
    onSuccess: () => {
      toast.success("Snapshot deleted");
      void queryClient.invalidateQueries({ queryKey: queryKeys.snapshots(playerId) });
      void navigate(`/players/${playerId}`, { replace: true });
    },
    onError: (error) => toast.error(error.message),
  });

  const updateParams = (changes: Record<string, string | null>) =>
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        for (const [key, value] of Object.entries(changes)) {
          if (value === null) next.delete(key);
          else next.set(key, value);
        }
        return next;
      },
      { replace: true },
    );

  const filteredMatches = useMemo(
    () => (matches.data ?? []).filter((match) => !champion || match.champion === champion),
    [matches.data, champion],
  );

  if (dashboard.isPending) return <DashboardSkeleton />;
  if (dashboard.isError) {
    if (isApiError(dashboard.error, 404)) return <NotFound />;
    return (
      <Card>
        <ErrorState error={dashboard.error} onRetry={() => void dashboard.refetch()} />
      </Card>
    );
  }

  const data = dashboard.data;

  return (
    <>
      <PageHeader
        back={
          <Link to={`/players/${playerId}`} className="mb-2 inline-flex items-center gap-1 text-xs text-muted hover:text-fg">
            <ArrowLeft className="size-3.5" aria-hidden="true" />
            Back to player
          </Link>
        }
        title={data.player_name}
        description={`${formatDate(data.date_from)} – ${formatDate(data.date_to)} · ${data.games_played} games · ${roleLabel(data.active_role)}`}
        actions={
          <>
            <Link
              to={`/players/${playerId}/snapshots/compare?a=${snapshotId}`}
              className={buttonClasses({ variant: "outline" })}
            >
              <GitCompareArrows className="size-4" aria-hidden="true" />
              Compare
            </Link>
            <Button variant="danger" onClick={() => setConfirmDelete(true)}>
              <Trash className="size-4" aria-hidden="true" />
              Delete
            </Button>
          </>
        }
      />

      <SnapshotNotes
        key={`${data.description ?? ""}|${data.notes ?? ""}`}
        snapshotId={snapshotId}
        playerId={playerId}
        description={data.description ?? ""}
        notes={data.notes ?? ""}
      />

      {data.games_played === 0 ? (
        <Card className="mt-6">
          <EmptyState
            title="No ranked games in this period"
            description="Riot returned no ranked games between these dates. Try a wider range."
          />
        </Card>
      ) : (
        <Tabs value={tab} onValueChange={(value) => updateParams({ tab: value === "overview" ? null : value })} className="mt-6">
          <TabsList aria-label="Snapshot sections">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="matches">Matches{matches.data ? ` (${matches.data.length})` : ""}</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="mt-6 flex flex-col gap-6 focus:outline-none">
            <MetricGrid metrics={data.role_averages} />
            <div className="grid gap-6 lg:grid-cols-5">
              <RadarPanel className="lg:col-span-3" dashboard={data} snapshotId={snapshotId} />
              <DeathsPanel className="lg:col-span-2" dashboard={data} matches={matches} champion={champion} />
              <Card className="min-w-0 lg:col-span-3">
                <CardHeader title="Trends" description="Each game, with the moving average in bold." />
                <div className="p-4">
                  <TrendChart points={data.performance_trends} />
                </div>
              </Card>
              <ChampionsPanel
                className="lg:col-span-2"
                champions={data.played_champions}
                onSelect={(name) => updateParams({ tab: "matches", champion: name })}
              />
            </div>
          </TabsContent>

          <TabsContent value="matches" className="mt-6 focus:outline-none">
            <Card>
              <div className="flex flex-wrap items-center gap-3 border-b border-border/60 p-4">
                <label className="flex items-center gap-2 text-xs text-muted">
                  Champion
                  <Select
                    className="h-9 w-52"
                    value={champion ?? ""}
                    onChange={(event) => updateParams({ champion: event.target.value || null })}
                  >
                    <option value="">All champions</option>
                    {data.played_champions.map((played) => (
                      <option key={played.champion_name} value={played.champion_name}>
                        {played.champion_name} ({played.games_played})
                      </option>
                    ))}
                  </Select>
                </label>
                <p className="text-xs text-muted">{filteredMatches.length} games</p>
              </div>
              {matches.isPending ? (
                <div className="flex flex-col gap-2 p-4">
                  {Array.from({ length: 6 }, (_, index) => (
                    <Skeleton key={index} className="h-12" />
                  ))}
                </div>
              ) : matches.isError ? (
                <ErrorState error={matches.error} onRetry={() => void matches.refetch()} />
              ) : filteredMatches.length === 0 ? (
                <EmptyState title="No games with this filter" />
              ) : (
                <MatchTable matches={filteredMatches} />
              )}
            </Card>
          </TabsContent>
        </Tabs>
      )}

      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title="Delete this snapshot?"
        description="The analysis is removed. Its matches stay stored and are reused by future analyses."
        loading={remove.isPending}
        onConfirm={() => remove.mutate()}
      />
    </>
  );
}

function DashboardSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading analysis" className="flex flex-col gap-6">
      <Skeleton className="h-14 w-72" />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {Array.from({ length: 6 }, (_, index) => (
          <Skeleton key={index} className="h-24 rounded-xl" />
        ))}
      </div>
      <div className="grid gap-6 lg:grid-cols-5">
        <Skeleton className="h-96 rounded-xl lg:col-span-3" />
        <Skeleton className="h-96 rounded-xl lg:col-span-2" />
      </div>
    </div>
  );
}

// ── Descripción y notas ───────────────────────────────────────────────────────

function SnapshotNotes({
  snapshotId,
  playerId,
  description,
  notes,
}: {
  snapshotId: number;
  playerId: number;
  description: string;
  notes: string;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [descriptionDraft, setDescriptionDraft] = useState(description);
  const [notesDraft, setNotesDraft] = useState(notes);

  const onSaved = (message: string) => {
    toast.success(message);
    void queryClient.invalidateQueries({ queryKey: queryKeys.dashboards(snapshotId) });
    void queryClient.invalidateQueries({ queryKey: queryKeys.snapshots(playerId) });
  };

  const saveDescription = useMutation({
    mutationFn: () =>
      unwrap(
        api.PATCH("/snapshots/{snapshot_id}/description", {
          params: { path: { snapshot_id: snapshotId } },
          body: { description: descriptionDraft.trim() },
        }),
      ),
    onSuccess: () => onSaved("Description saved"),
    onError: (error) => toast.error(error.message),
  });

  const saveNotes = useMutation({
    mutationFn: () =>
      unwrap(
        api.PATCH("/snapshots/{snapshot_id}/notes", { params: { path: { snapshot_id: snapshotId } }, body: { notes: notesDraft } }),
      ),
    onSuccess: () => onSaved("Notes saved"),
    onError: (error) => toast.error(error.message),
  });

  return (
    <Card className="grid gap-4 p-4 md:grid-cols-2">
      <form
        className="flex flex-col gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          saveDescription.mutate();
        }}
      >
        <label htmlFor="snapshot-description" className="text-[11px] font-semibold tracking-[0.12em] text-muted uppercase">
          Description
        </label>
        <div className="flex gap-2">
          <Input
            id="snapshot-description"
            value={descriptionDraft}
            maxLength={200}
            placeholder="What was going on in this period?"
            onChange={(event) => setDescriptionDraft(event.target.value)}
          />
          {descriptionDraft !== description && (
            <Button type="submit" size="md" loading={saveDescription.isPending}>
              Save
            </Button>
          )}
        </div>
      </form>
      <form
        className="flex flex-col gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          saveNotes.mutate();
        }}
      >
        <label htmlFor="snapshot-notes" className="text-[11px] font-semibold tracking-[0.12em] text-muted uppercase">
          Coach notes
        </label>
        <Textarea
          id="snapshot-notes"
          className="min-h-10"
          rows={1}
          value={notesDraft}
          placeholder="Takeaways, things to drill…"
          onChange={(event) => setNotesDraft(event.target.value)}
        />
        {notesDraft !== notes && (
          <div className="flex justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={() => setNotesDraft(notes)}>
              Discard
            </Button>
            <Button type="submit" size="sm" loading={saveNotes.isPending}>
              Save notes
            </Button>
          </div>
        )}
      </form>
    </Card>
  );
}

// ── Radar ─────────────────────────────────────────────────────────────────────

function RadarPanel({ dashboard, snapshotId, className }: { dashboard: Dashboard; snapshotId: number; className?: string }) {
  const rankKeys = useMemo(
    () => Object.keys(dashboard.radar_data.rank_datasets).sort((a, b) => tierOrder(a) - tierOrder(b)),
    [dashboard],
  );
  const [ranks, setRanks] = useState<string[]>(() => {
    const challenger = rankKeys.find((key) => normalizeTier(key) === "CHALLENGER");
    return challenger ? [challenger] : rankKeys.slice(-1);
  });
  const [compare, setCompare] = useState<CompareTarget | null>(null);

  // La comparación va en otra query: si la cuenta no existe, el dashboard principal no se ve afectado.
  const comparison = useQuery({
    queryKey: queryKeys.dashboard(snapshotId, compareKey(compare)),
    queryFn: () => fetchDashboard(snapshotId, compare),
    enabled: compare !== null,
    retry: false,
    staleTime: 5 * 60_000,
  });

  const series: RadarSeries[] = [
    {
      id: "player",
      label: dashboard.player_name,
      color: palette.primary,
      dataset: dashboard.radar_data.player_dataset,
      fillOpacity: 0.18,
    },
    ...ranks.flatMap((key) => {
      const dataset = dashboard.radar_data.rank_datasets[key];
      if (!dataset) return [];
      const tier = normalizeTier(key);
      return [{ id: `rank-${key}`, label: `${dataset.label} avg`, color: tier ? RANK_COLORS[tier] : palette.gray, dataset, dashed: true }];
    }),
    ...(compare && comparison.data
      ? Object.entries(comparison.data.radar_data.pro_datasets).map(([key, dataset], index) => ({
          id: `compare-${key}`,
          label: dataset.label,
          color: index === 0 ? palette.gold : palette.blue,
          dataset,
          fillOpacity: 0.06,
        }))
      : []),
  ];

  const compareError = comparison.isError
    ? isApiError(comparison.error, 404)
      ? "That account was not found in this region."
      : comparison.error.message
    : null;

  return (
    <Card className={cn("min-w-0", className)}>
      <CardHeader title="Performance radar" description="0 = worst · Challenger avg ≈ 82 · Deaths: lower is better" />
      <div className="p-4">
        {rankKeys.length > 0 && (
          <div role="group" aria-label="Rank benchmarks" className="mb-2 flex flex-wrap gap-1.5">
            {rankKeys.map((key) => {
              const active = ranks.includes(key);
              const tier = normalizeTier(key);
              return (
                <button
                  key={key}
                  type="button"
                  aria-pressed={active}
                  onClick={() => setRanks((current) => (active ? current.filter((k) => k !== key) : [...current, key]))}
                  className={cn(
                    "cursor-pointer rounded-full border px-2.5 py-1 text-[11px] font-semibold transition",
                    active ? "border-transparent text-bg" : "border-border text-muted hover:text-fg",
                  )}
                  style={active ? { background: tier ? RANK_COLORS[tier] : palette.gray } : undefined}
                >
                  {dashboard.radar_data.rank_datasets[key]?.label ?? key}
                </button>
              );
            })}
          </div>
        )}
        <PerformanceRadar axes={dashboard.radar_data.axes} series={series} />
        <CompareForm
          active={compare !== null}
          loading={comparison.isFetching}
          error={compareError}
          onSubmit={setCompare}
          onClear={() => setCompare(null)}
        />
      </div>
    </Card>
  );
}

function CompareForm({
  active,
  loading,
  error,
  onSubmit,
  onClear,
}: {
  active: boolean;
  loading: boolean;
  error: string | null;
  onSubmit: (target: CompareTarget) => void;
  onClear: () => void;
}) {
  const [riotId, setRiotId] = useState("");
  const [region, setRegion] = useState("EUW");
  const [invalid, setInvalid] = useState(false);

  return (
    <form
      className="mt-4 flex flex-col gap-2 border-t border-border/60 pt-4"
      onSubmit={(event) => {
        event.preventDefault();
        const parsed = parseRiotId(riotId);
        setInvalid(parsed === null);
        if (parsed) onSubmit({ ...parsed, region });
      }}
    >
      <p className="text-[11px] font-semibold tracking-[0.12em] text-muted uppercase">Overlay another account</p>
      <div className="flex flex-col gap-2 sm:flex-row">
        <Input
          aria-label="Riot ID to compare"
          placeholder="Name#TAG"
          value={riotId}
          aria-invalid={invalid}
          className="sm:flex-1"
          onChange={(event) => setRiotId(event.target.value)}
        />
        <Select aria-label="Region to compare" className="sm:w-28" value={region} onChange={(event) => setRegion(event.target.value)}>
          {REGIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.value}
            </option>
          ))}
        </Select>
        <Button type="submit" variant="outline" loading={loading}>
          Compare
        </Button>
        {active && (
          <Button variant="ghost" onClick={onClear}>
            Clear
          </Button>
        )}
      </div>
      {invalid && <p className="text-xs text-stat-red">Use the format Name#TAG</p>}
      {error && (
        <p role="alert" className="text-xs text-stat-red">
          {error}
        </p>
      )}
      <p className="text-xs text-muted">Computed live from that account's recent ranked games in the same role.</p>
    </form>
  );
}

// ── Muertes y campeones ───────────────────────────────────────────────────────

function DeathsPanel({
  dashboard,
  matches,
  champion,
  className,
}: {
  dashboard: Dashboard;
  matches: UseQueryResult<Match[]>;
  champion: string | null;
  className?: string;
}) {
  const { data: ddragon } = useDDragon();
  const points = useMemo(
    () => deathPoints((matches.data ?? []).filter((match) => !champion || match.champion === champion)),
    [matches.data, champion],
  );

  return (
    <Card className={cn("min-w-0", className)}>
      <CardHeader title="Deaths" description={champion ? `Heatmap on ${champion}` : "Where you die, and when"} />
      <div className="flex flex-col gap-5 p-4">
        {matches.isPending ? (
          <Skeleton className="aspect-square w-full" />
        ) : (
          <DeathHeatmap points={points} mapUrl={ddragon ? ddragonUrl.map(ddragon.version) : null} />
        )}
        <DeathsByPhase phases={dashboard.deaths_by_phase} games={dashboard.games_played} />
      </div>
    </Card>
  );
}

function ChampionsPanel({
  champions,
  onSelect,
  className,
}: {
  champions: Dashboard["played_champions"];
  onSelect: (champion: string) => void;
  className?: string;
}) {
  return (
    <Card className={cn("min-w-0", className)}>
      <CardHeader title="Champions" description="Select one to see its games." />
      <ul className="flex max-h-80 flex-col gap-0.5 overflow-y-auto p-2">
        {champions.map((played) => (
          <li key={played.champion_name}>
            <button
              type="button"
              onClick={() => onSelect(played.champion_name)}
              className="flex w-full cursor-pointer items-center gap-3 rounded-lg px-3 py-2 text-left transition hover:bg-surface-2"
            >
              <ChampionIcon name={played.champion_name} size={32} />
              <span className="min-w-0 flex-1 truncate text-sm font-medium text-fg">{played.champion_name}</span>
              <span className="text-xs text-muted tabular-nums">{played.games_played} games</span>
              <span className={cn("w-11 text-right text-sm font-semibold tabular-nums", toneText[winRateTone(played.win_rate)])}>
                {formatPercent(played.win_rate, 0)}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </Card>
  );
}
