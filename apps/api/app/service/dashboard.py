"""Dashboard de un snapshot: la API carga los datos y ygg-core hace el cálculo."""

import logging
from dataclasses import asdict

from sqlalchemy.orm import Session
from ygg_core.domain.participant import PlayerRef
from ygg_core.domain.roles import dashboard_role
from ygg_core.metrics.dashboard import comparison_dataset, compute_dashboard

from app.db.models.match import Match
from app.db.models.match_snapshot import MatchSnapshot
from app.db.models.snapshot import Snapshot
from app.schemas.dashboard import (
    ChampionStatsResponse,
    RadarChartData,
    RadarDataset,
    RoleAverageMetric,
    SnapshotDashboardResponse,
)
from app.schemas.match import MatchResponse
from app.service.ddragon_client import FALLBACK_VERSION, get_ddragon_client
from app.service.riot import create_secure_session, match_to_participant, riot_client

logger = logging.getLogger(__name__)

COMPARE_MAX_MATCHES = 50


async def _comparison_radar(
    game_name: str, tag_line: str, region: str, role: str
) -> dict[str, RadarDataset]:
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


async def build_snapshot_dashboard(
    db: Session,
    snapshot: Snapshot,
    compare_game_name: str | None = None,
    compare_tag_line: str | None = None,
    compare_region: str | None = None,
) -> SnapshotDashboardResponse:
    matches = (
        db.query(Match)
        .join(MatchSnapshot, MatchSnapshot.match_id == Match.id)
        .filter(MatchSnapshot.snapshot_id == snapshot.id)
        .all()
    )
    player = snapshot.player
    role = dashboard_role(player.role.value if player.role else None)
    metrics = compute_dashboard(
        [match_to_participant(m) for m in matches], role, player.game_name
    )

    ddragon = await get_ddragon_client()
    version = ddragon.version or FALLBACK_VERSION

    radar = RadarChartData.model_validate(asdict(metrics.radar))
    if matches and compare_game_name and compare_tag_line:
        radar.pro_datasets = await _comparison_radar(
            compare_game_name,
            compare_tag_line,
            compare_region or player.region or "euw",
            role,
        )

    return SnapshotDashboardResponse(
        snapshot_id=snapshot.id,
        player_id=player.id,
        player_name=f"{player.game_name}#{player.tag_line}",
        date_from=snapshot.date_from,
        date_to=snapshot.date_to,
        description=snapshot.description,
        notes=snapshot.notes,
        active_role=role,
        role_averages=[RoleAverageMetric(**asdict(m)) for m in metrics.role_averages],
        played_champions=[
            ChampionStatsResponse(
                **asdict(champion),
                icon_url=ddragon.champion_icon_url(version, champion.champion_name),
            )
            for champion in metrics.played_champions
        ],
        matches=[MatchResponse.model_validate(m) for m in matches],
        radar_data=radar,
    )
