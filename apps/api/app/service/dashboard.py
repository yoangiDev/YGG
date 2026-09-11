"""Dashboard de un snapshot: la API carga los datos, ygg-core calcula y Redis cachea."""

import logging
from collections import Counter
from dataclasses import asdict

from sqlalchemy.ext.asyncio import AsyncSession
from ygg_core.domain.participant import PlayerRef
from ygg_core.domain.roles import dashboard_role
from ygg_core.metrics import aggregates
from ygg_core.metrics.dashboard import comparison_dataset, compute_dashboard

from app.crud.participants import participants_for_snapshot
from app.db.models.snapshot import Snapshot
from app.schemas.dashboard import (
    ChampionStatsResponse,
    DeathsByPhase,
    RadarChartData,
    RadarDataset,
    RoleAverageMetric,
    SnapshotDashboardResponse,
    TrendPoint,
)
from app.schemas.match import MatchResponse
from app.service.dashboard_cache import get_cached_dashboard, store_dashboard
from app.service.ddragon_client import FALLBACK_VERSION, get_ddragon_client
from app.service.riot import create_secure_session, participant_from_row, riot_client

logger = logging.getLogger(__name__)

COMPARE_MAX_MATCHES = 50


def aggregate_deaths_by_phase(matches: list[MatchResponse]) -> DeathsByPhase:
    totals: Counter[str] = Counter()
    for match in matches:
        totals.update(match.deaths_by_phase)
    return DeathsByPhase(
        early_deaths=totals["early_deaths"],
        mid_deaths=totals["mid_deaths"],
        late_deaths=totals["late_deaths"],
    )


def performance_trends(matches: list[MatchResponse]) -> list[TrendPoint]:
    """Rendimiento cronológico con medias móviles para las gráficas de evolución."""
    ordered = sorted(matches, key=lambda m: m.creation_time)
    window = aggregates.trend_window_size(len(ordered))
    kda = aggregates.moving_average([m.kda for m in ordered], window)
    cs = aggregates.moving_average([m.cs_per_min for m in ordered], window)
    gold = aggregates.moving_average([m.gold_per_min for m in ordered], window)
    vision = aggregates.moving_average([m.vision_per_min for m in ordered], window)
    return [
        TrendPoint(
            game_num=index + 1,
            match_id=m.match_id,
            creation_time=m.creation_time,
            champion=m.champion,
            win=m.win,
            kda=m.kda,
            cs_per_min=m.cs_per_min,
            gold_per_min=m.gold_per_min,
            vision_per_min=m.vision_per_min,
            kda_moving_avg=kda[index],
            cs_moving_avg=cs[index],
            gold_moving_avg=gold[index],
            vision_moving_avg=vision[index],
        )
        for index, m in enumerate(ordered)
    ]


async def _comparison_radar(game_name: str, tag_line: str, region: str, role: str) -> dict[str, RadarDataset]:
    """Radar de otra cuenta de Riot descargada en vivo. Si falla, el dashboard sigue sin él."""
    label = f"{game_name}#{tag_line}"
    try:
        client = riot_client(region)
        async with create_secure_session() as session:
            puuid = await client.get_puuid(session, game_name, tag_line)
            participants = await client.fetch_participants(
                session,
                PlayerRef(puuid, game_name, tag_line),
                max_matches=COMPARE_MAX_MATCHES,
                role_filter=role,
                include_timeline=True,
            )
    except Exception as exc:
        logger.warning("Comparison account %s unavailable: %s", label, exc)
        return {}
    return {label: RadarDataset(**asdict(comparison_dataset(label, participants, role)))}


async def build_snapshot_dashboard(db: AsyncSession, snapshot: Snapshot) -> SnapshotDashboardResponse:
    rows = await participants_for_snapshot(db, snapshot.id)
    player = snapshot.player
    role = dashboard_role(player.role.value if player.role else None)
    metrics = compute_dashboard([participant_from_row(r) for r in rows], role, player.game_name)
    matches = [MatchResponse.model_validate(r) for r in rows]

    ddragon = await get_ddragon_client()
    version = ddragon.version or FALLBACK_VERSION

    return SnapshotDashboardResponse(
        snapshot_id=snapshot.id,
        player_id=player.id,
        player_name=f"{player.game_name}#{player.tag_line}",
        date_from=snapshot.date_from,
        date_to=snapshot.date_to,
        description=snapshot.description,
        notes=snapshot.notes,
        active_role=role,
        games_played=len(rows),
        role_averages=[RoleAverageMetric(**asdict(m)) for m in metrics.role_averages],
        played_champions=[
            ChampionStatsResponse(
                **asdict(champion),
                icon_url=ddragon.champion_icon_url(version, champion.champion_name),
            )
            for champion in metrics.played_champions
        ],
        deaths_by_phase=aggregate_deaths_by_phase(matches),
        performance_trends=performance_trends(matches),
        radar_data=RadarChartData.model_validate(asdict(metrics.radar)),
    )


async def get_snapshot_dashboard(
    db: AsyncSession,
    snapshot: Snapshot,
    compare_game_name: str | None = None,
    compare_tag_line: str | None = None,
    compare_region: str | None = None,
) -> SnapshotDashboardResponse:
    """Dashboard desde la caché (o calculado y cacheado). La comparación en vivo nunca se cachea."""
    dashboard = await get_cached_dashboard(snapshot.id)
    if dashboard is None:
        dashboard = await build_snapshot_dashboard(db, snapshot)
        await store_dashboard(dashboard)

    if dashboard.games_played and compare_game_name and compare_tag_line:
        dashboard = dashboard.model_copy(deep=True)
        dashboard.radar_data.pro_datasets = await _comparison_radar(
            compare_game_name,
            compare_tag_line,
            compare_region or snapshot.player.region or "euw",
            dashboard.active_role,
        )
    return dashboard
