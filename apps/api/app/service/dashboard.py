"""A snapshot's dashboard: the API loads the data, ygg-core computes and Redis caches."""

import logging
from dataclasses import asdict

from sqlalchemy.ext.asyncio import AsyncSession
from ygg_core.domain.participant import PlayerRef
from ygg_core.domain.roles import dashboard_role
from ygg_core.metrics.dashboard import comparison_dataset, compute_dashboard

from app.crud.participants import participants_for_snapshot
from app.db.models.snapshot import Snapshot
from app.schemas.dashboard import (
    ChampionStatsResponse,
    RadarChartData,
    RadarDataset,
    RoleAverageMetric,
    SnapshotDashboardResponse,
    SnapshotTrends,
)
from app.service.dashboard_cache import get_cached_dashboard, store_dashboard
from app.service.riot import create_secure_session, participant_from_row, riot_client

logger = logging.getLogger(__name__)

# The compared account is measured with the same sample as the snapshot (its period and its
# number of matches) up to this maximum: each match is two Riot requests.
COMPARE_MAX_MATCHES = 20


async def _comparison_radar(
    game_name: str,
    tag_line: str,
    region: str,
    role: str,
    *,
    start_t: int,
    end_t: int,
    max_matches: int,
) -> dict[str, RadarDataset]:
    """Radar of another Riot account over the snapshot's period. If it fails or they didn't play, the dashboard carries on without it."""
    label = f"{game_name}#{tag_line}"
    try:
        client = riot_client(region)
        async with create_secure_session() as session:
            puuid = await client.get_puuid(session, game_name, tag_line)
            participants = await client.fetch_participants(
                session,
                PlayerRef(puuid, game_name, tag_line),
                start_t=start_t,
                end_t=end_t,
                max_matches=max_matches,
                role_filter=role,
                include_timeline=True,
            )
    except Exception as exc:
        logger.warning("Comparison account %s unavailable: %s", label, exc)
        return {}
    if not participants:
        logger.info("Comparison account %s has no %s games in the snapshot period.", label, role)
        return {}
    return {label: RadarDataset(**asdict(comparison_dataset(label, participants, role)))}


async def build_snapshot_dashboard(db: AsyncSession, snapshot: Snapshot) -> SnapshotDashboardResponse:
    rows = await participants_for_snapshot(db, snapshot.id)
    player = snapshot.player
    role = dashboard_role(player.role.value if player.role else None)
    metrics = compute_dashboard([participant_from_row(r) for r in rows], role, player.game_name, player.target_rank)

    return SnapshotDashboardResponse(
        snapshot_id=snapshot.id,
        player_id=player.id,
        player_name=f"{player.game_name}#{player.tag_line}",
        date_from=snapshot.date_from,
        date_to=snapshot.date_to,
        description=snapshot.description,
        notes=snapshot.notes,
        active_role=role,
        target_rank=player.target_rank,
        games_played=len(rows),
        role_averages=[RoleAverageMetric(**asdict(m)) for m in metrics.role_averages],
        played_champions=[ChampionStatsResponse(**asdict(champion)) for champion in metrics.played_champions],
        trends=SnapshotTrends.model_validate(asdict(metrics.trends)),
        radar_data=RadarChartData.model_validate(asdict(metrics.radar)),
    )


async def get_snapshot_dashboard(
    db: AsyncSession,
    snapshot: Snapshot,
    compare_game_name: str | None = None,
    compare_tag_line: str | None = None,
    compare_region: str | None = None,
) -> SnapshotDashboardResponse:
    """Dashboard from the cache (or computed and cached). The live comparison is never cached."""
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
            start_t=int(snapshot.date_from.timestamp()),
            end_t=int(snapshot.date_to.timestamp()),
            max_matches=min(dashboard.games_played, COMPARE_MAX_MATCHES),
        )
    return dashboard
