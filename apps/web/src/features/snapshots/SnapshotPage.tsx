import { useMutation, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";
import { ArrowLeft, GitCompareArrows, Lock, Sparkles, Trash } from "lucide-react";
import { lazy, Suspense, useMemo, useState, type ComponentProps } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";

import { NotFound } from "@/app/RouteError";
import { DeathHeatmap } from "@/components/charts/DeathHeatmap";
import { MetricGrid } from "@/components/charts/MetricGrid";
import type { RadarSeries } from "@/components/charts/PerformanceRadar";
import { PageHeader } from "@/components/ui/PageHeader";
import { ChampionIcon } from "@/components/player/PlayerBits";
import { Button, buttonClasses } from "@/components/ui/Button";
import { Card, CardHeader, Skeleton } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Input, Select } from "@/components/ui/Field";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/Overlay";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/features/auth/AuthProvider";
import { api, isApiError, unwrap } from "@/lib/api/client";
import { cn } from "@/lib/cn";
import { ddragonUrl, useDDragon } from "@/lib/ddragon";
import { formatDate, formatNumber, formatPercent } from "@/lib/format";
import { deathPoints, type DeathPhase } from "@/lib/heatmap";
import { palette } from "@/lib/palette";
import { parseId } from "@/lib/params";
import { queryKeys } from "@/lib/queryKeys";
import { normalizeTier, RANK_COLORS, tierOrder } from "@/lib/rank";
import { parseRiotId } from "@/lib/riotId";
import { REGIONS, roleLabel, toRegion, type Region } from "@/lib/roles";
import { statTone, toneText, winRateTone } from "@/lib/stats";

import { ChampionBreakdown } from "./ChampionBreakdown";
import { PremiumPanel, PremiumTeaser } from "./PremiumPanel";
import { compareKey, fetchDashboard, useSnapshotMatches, type CompareTarget, type Dashboard, type Match } from "./queries";

// Recharts and TanStack Table go in separate chunks: the metric cards are painted as soon as the data
// arrives, without waiting for the chart and table libraries.
const LazyPerformanceRadar = lazy(() =>
  import("@/components/charts/PerformanceRadar").then((m) => ({ default: m.PerformanceRadar })),
);
const LazyTrendChart = lazy(() => import("@/components/charts/TrendChart").then((m) => ({ default: m.TrendChart })));
const LazyMatchTable = lazy(() => import("./MatchTable").then((m) => ({ default: m.MatchTable })));

function PerformanceRadar(props: ComponentProps<typeof LazyPerformanceRadar>) {
  return (
    <Suspense fallback={<Skeleton className="h-[340px] w-full" />}>
      <LazyPerformanceRadar {...props} />
    </Suspense>
  );
}

function TrendChart(props: ComponentProps<typeof LazyTrendChart>) {
  return (
    <Suspense fallback={<Skeleton className="h-[300px] w-full" />}>
      <LazyTrendChart {...props} />
    </Suspense>
  );
}

function MatchTable(props: ComponentProps<typeof LazyMatchTable>) {
  return (
    <Suspense fallback={<Skeleton className="m-4 h-96" />}>
      <LazyMatchTable {...props} />
    </Suspense>
  );
}

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
  const requestedTab = params.get("tab");
  const tab =
    requestedTab === "matches" || requestedTab === "champions" || requestedTab === "premium" ? requestedTab : "overview";
  const champion = params.get("champion");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const { isPremium } = useAuth();

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
      void navigate("/account", { replace: true });
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
      { replace: true, preventScrollReset: true },
    );

  /** The snapshot's matches (of one champion, if given) in the matches table, with their loading states. */
  const games = (only: string | null) => {
    if (matches.isPending) {
      return (
        <div className="flex flex-col gap-2 p-4">
          {Array.from({ length: 6 }, (_, index) => (
            <Skeleton key={index} className="h-12" />
          ))}
        </div>
      );
    }
    if (matches.isError) return <ErrorState error={matches.error} onRetry={() => void matches.refetch()} />;
    const shown = only ? matches.data.filter((match) => match.champion === only) : matches.data;
    return shown.length === 0 ? <EmptyState title="No games" /> : <MatchTable matches={shown} snapshotId={snapshotId} />;
  };

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
          <Link to="/account" className="-my-1 mb-2 inline-flex items-center gap-1 py-1 text-xs text-muted hover:text-text">
            <ArrowLeft className="size-3.5" aria-hidden="true" />
            Back to player
          </Link>
        }
        title={data.player_name}
        documentTitle={`${data.player_name} · ${formatDate(data.date_from)} – ${formatDate(data.date_to)}`}
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

      <SnapshotDescription
        key={data.description ?? ""}
        snapshotId={snapshotId}
        playerId={playerId}
        description={data.description ?? ""}
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
            <TabsTrigger value="champions">Champion stats</TabsTrigger>
            <TabsTrigger value="premium">
              {isPremium ? (
                <Sparkles className="size-3.5 text-stat-gold" aria-hidden="true" />
              ) : (
                <Lock className="size-3.5 text-stat-gold" aria-hidden="true" />
              )}
              Replay analysis
            </TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="mt-6 flex flex-col gap-6 focus:outline-none">
            {!isPremium && <PremiumTeaser />}
            <MetricGrid metrics={data.role_averages} />
            <div className="grid gap-6 lg:grid-cols-5">
              <RadarPanel className="lg:col-span-3" dashboard={data} snapshotId={snapshotId} />
              <ChampionsPanel
                className="lg:col-span-2"
                champions={data.played_champions}
                role={data.active_role}
                onSelect={(name) => updateParams({ tab: "champions", champion: name })}
              />
            </div>
            <DeathsPanel matches={matches} champion={champion} />
            <div className="grid gap-6 lg:grid-cols-2">
              {data.trends.groups.map((group) => (
                <Card key={group.key} className="min-w-0">
                  <CardHeader title={group.label} description="Each game, its moving average and the Challenger expected value (dashed)." />
                  <div className="p-4">
                    <TrendChart games={data.trends.games} group={group} />
                  </div>
                </Card>
              ))}
            </div>
          </TabsContent>

          <TabsContent value="matches" className="mt-6 focus:outline-none">
            <Card>{games(null)}</Card>
          </TabsContent>

          <TabsContent value="champions" className="mt-6 focus:outline-none">
            <ChampionBreakdown
              champions={data.played_champions}
              selected={champion}
              onSelect={(name) => updateParams({ champion: name === champion ? null : name })}
              history={games}
            />
          </TabsContent>

          <TabsContent value="premium" className="mt-6 focus:outline-none">
            <PremiumPanel snapshotId={snapshotId} />
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
          <Skeleton key={index} className="h-24" />
        ))}
      </div>
      <div className="grid gap-6 lg:grid-cols-5">
        <Skeleton className="h-96 lg:col-span-3" />
        <Skeleton className="h-96 lg:col-span-2" />
      </div>
    </div>
  );
}

// ── Description ───────────────────────────────────────────────────────────────

function SnapshotDescription({
  snapshotId,
  playerId,
  description,
}: {
  snapshotId: number;
  playerId: number;
  description: string;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [descriptionDraft, setDescriptionDraft] = useState(description);

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

  return (
    <Card className="p-4">
      <form
        className="flex flex-col gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          saveDescription.mutate();
        }}
      >
        <div className="flex gap-2">
          <Input
            aria-label="Description"
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
    </Card>
  );
}

// ── Radar ─────────────────────────────────────────────────────────────────────

function RadarPanel({ dashboard, snapshotId, className }: { dashboard: Dashboard; snapshotId: number; className?: string }) {
  const rankKeys = useMemo(
    () => Object.keys(dashboard.radar_data.rank_datasets).sort((a, b) => tierOrder(a) - tierOrder(b)),
    [dashboard],
  );
  // It starts with the player's target rank (the one the cards use).
  const [ranks, setRanks] = useState<string[]>(() => {
    const target = rankKeys.find((key) => normalizeTier(key) === normalizeTier(dashboard.target_rank));
    return target ? [target] : rankKeys.slice(-1);
  });
  const [compare, setCompare] = useState<CompareTarget | null>(null);

  // The comparison goes in another query: if the account doesn't exist, the main dashboard is unaffected.
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

  // The API returns an empty overlay if the account didn't play that role in the period or Riot didn't respond.
  const compareEmpty = compare !== null && comparison.data !== undefined && Object.keys(comparison.data.radar_data.pro_datasets).length === 0;
  const compareError = comparison.isError
    ? isApiError(comparison.error, 404)
      ? "That account was not found in this region."
      : comparison.error.message
    : compareEmpty
      ? "No ranked games found for that account in this role and period."
      : null;

  return (
    <Card className={cn("min-w-0", className)}>
      <CardHeader title="Performance radar" description="0 = worst · Challenger avg ≈ 80 · Deaths: lower is better" />
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
                    "cursor-pointer rounded-full border px-2.5 py-1 text-xs font-bold transition",
                    active ? "border-transparent text-ink" : "border-line text-muted hover:text-text",
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
  const [region, setRegion] = useState<Region>("EUW");
  const [invalid, setInvalid] = useState(false);

  return (
    <form
      className="mt-4 flex flex-col gap-2 border-t border-line/60 pt-4"
      onSubmit={(event) => {
        event.preventDefault();
        const parsed = parseRiotId(riotId);
        setInvalid(parsed === null);
        if (parsed) onSubmit({ ...parsed, region });
      }}
    >
      <p className="text-xs font-bold tracking-caps text-muted uppercase">Overlay another account</p>
      <div className="flex flex-col gap-2 sm:flex-row">
        <Input
          aria-label="Riot ID to compare"
          placeholder="Name#TAG"
          value={riotId}
          aria-invalid={invalid}
          className="sm:flex-1"
          onChange={(event) => setRiotId(event.target.value)}
        />
        <Select aria-label="Region to compare" className="sm:w-28" value={region} onChange={(event) => setRegion(toRegion(event.target.value) ?? "EUW")}>
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
      <p className="text-xs text-muted">
        Computed live from that account's ranked games in the same role and period as this snapshot, up to 20 games.
      </p>
    </form>
  );
}

// ── Deaths and champions ──────────────────────────────────────────────────────

const DEATH_PHASES: { key: DeathPhase; title: string; detail: string }[] = [
  { key: "laning", title: "Laning phase", detail: "0–14 min" },
  { key: "mid_late", title: "Mid–late game", detail: "14+ min" },
];

function DeathsPanel({ matches, champion }: { matches: UseQueryResult<Match[]>; champion: string | null }) {
  const { data: ddragon } = useDDragon();
  const games = useMemo(() => (matches.data ?? []).filter((match) => !champion || match.champion === champion), [matches.data, champion]);
  const phases = useMemo(() => DEATH_PHASES.map((phase) => ({ ...phase, points: deathPoints(games, phase.key) })), [games]);
  const total = phases.reduce((sum, phase) => sum + phase.points.length, 0);
  const mapUrl = ddragon ? ddragonUrl.map(ddragon.version) : null;

  return (
    <Card className="min-w-0">
      <CardHeader title="Deaths" description={`Where you die in each phase of the game${champion ? ` on ${champion}` : ""}.`} />
      <div className="grid gap-8 p-4 md:grid-cols-2">
        {phases.map((phase) => (
          <section key={phase.key} aria-label={`${phase.title} deaths`} className="mx-auto w-full max-w-[460px]">
            <header className="mb-3 flex items-end justify-between gap-3">
              <div>
                <h3 className="text-sm font-black text-text">{phase.title}</h3>
                <p className="microtext mt-0.5 text-subtle">{phase.detail}</p>
              </div>
              <dl className="flex gap-5 text-right">
                <div>
                  <dt className="microtext text-xs text-subtle">Per game</dt>
                  <dd className="mt-0.5 text-sm font-black text-text tabular-nums">
                    {games.length > 0 ? formatNumber(phase.points.length / games.length, 1) : "—"}
                  </dd>
                </div>
                <div>
                  <dt className="microtext text-xs text-subtle">Share</dt>
                  <dd className="mt-0.5 text-sm font-black text-text tabular-nums">
                    {total > 0 ? formatPercent((phase.points.length / total) * 100, 0) : "—"}
                  </dd>
                </div>
              </dl>
            </header>
            {matches.isPending ? <Skeleton className="aspect-square w-full" /> : <DeathHeatmap points={phase.points} mapUrl={mapUrl} />}
          </section>
        ))}
      </div>
    </Card>
  );
}

function ChampionsPanel({
  champions,
  role,
  onSelect,
  className,
}: {
  champions: Dashboard["played_champions"];
  role: string;
  onSelect: (champion: string) => void;
  className?: string;
}) {
  const support = role === "SUPPORT";
  return (
    <Card className={cn("min-w-0", className)}>
      <CardHeader title="Champions" description="Select one to see its games and full stats." />
      <ul aria-label="Champions" className="max-h-[560px] overflow-y-auto">
        {champions.map((played) => (
          <li key={played.champion_name} className="border-b border-line last:border-b-0">
            <button
              type="button"
              onClick={() => onSelect(played.champion_name)}
              className="grid w-full cursor-pointer grid-cols-[32px_minmax(0,1fr)_auto] items-center gap-x-3 px-4 py-2.5 text-left transition-colors hover:bg-white/[0.03]"
            >
              <ChampionIcon name={played.champion_name} size={32} />
              <span className="min-w-0">
                <span className="block truncate text-sm font-black text-text">{played.champion_name}</span>
                <span className="mt-0.5 block truncate text-xs text-subtle tabular-nums">
                  {played.games_played} {played.games_played === 1 ? "game" : "games"} ·{" "}
                  <span className={toneText[statTone("kda", played.kda_status)]}>{formatNumber(played.kda, 2)} KDA</span> ·{" "}
                  {support ? `${formatNumber(played.vision_per_min, 2)} vis/min` : `${formatNumber(played.cs_per_min, 1)} cs/min`} ·{" "}
                  {formatNumber(played.dmg_per_min, 0)} dmg/min
                </span>
              </span>
              <span className="text-right">
                <span className={cn("block text-sm font-black tabular-nums", toneText[winRateTone(played.win_rate)])}>
                  {formatPercent(played.win_rate, 0)}
                </span>
                <span className="block text-xs text-subtle tabular-nums">
                  {played.wins}W {played.losses}L
                </span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </Card>
  );
}
