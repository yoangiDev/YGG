import logging
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.crud.player import get_player_by_id
from app.crud.snapshot import get_matches_page, get_snapshot_by_id, snapshot_summary
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.common import Page, PageParams
from app.schemas.match import MatchResponse, MostPlayedChampionResponse, SnapshotStatsResponse
from app.service.ddragon_client import FALLBACK_VERSION, DDragonClient, get_ddragon_client
from app.service.match_history import get_history_from_cache, is_history_fresh, update_history_cache
from app.service.riot import create_secure_session, player_ref, riot_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/matches", tags=["matches"])


def _to_responses(matches) -> list[MatchResponse]:
    """Acepta filas ORM o ParticipantStats del core: MatchResponse lee atributos."""
    return [MatchResponse.model_validate(m) for m in matches]


@router.get(
    "/player/{player_id}",
    response_model=list[MatchResponse],
    responses={503: {"description": "Riot API unavailable and nothing cached"}},
)
async def list_live_matches(
    player_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    live: bool = Query(default=False, description="Force full fetch from Riot API"),
    sync: bool = Query(default=False, description="Fetch new matches from Riot until stored history is reached"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Últimas N partidas del jugador (caché de 1 h), sin filtro de rol ni dependencia de snapshots."""
    player = await get_player_by_id(db, player_id, user_id=current_user.id)
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found.")

    if not (live or sync) and is_history_fresh(player):
        cached = await get_history_from_cache(db, player_id, limit=limit)
        if cached:
            return _to_responses(cached)

    try:
        client = riot_client(player.region)
        async with create_secure_session() as session:
            participants = await client.fetch_participants(
                session, player_ref(player), max_matches=limit, role_filter=None, include_timeline=False
            )
        if participants:
            await update_history_cache(db, player, participants)
            return _to_responses(participants)
    except Exception as exc:
        await db.rollback()
        logger.warning("[%s] History fetch failed (%s); serving stale cache.", player.game_name, exc)
        stale = await get_history_from_cache(db, player_id, limit=limit)
        if stale:
            return _to_responses(stale)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not load match history. Riot API unavailable, please try again later.",
        )
    return []


async def _require_snapshot(db: AsyncSession, snapshot_id: int, user: User) -> None:
    if not await get_snapshot_by_id(db, snapshot_id, user_id=user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snapshot not found.")


@router.get("/snapshot/{snapshot_id}", response_model=Page[MatchResponse])
async def list_matches(
    snapshot_id: int,
    page: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Partidas de un snapshot, de la más reciente a la más antigua (solo BD)."""
    await _require_snapshot(db, snapshot_id, current_user)
    matches, total = await get_matches_page(
        db, snapshot_id, current_user.id, limit=page.limit, offset=page.offset
    )
    return Page[MatchResponse](items=_to_responses(matches), total=total, limit=page.limit, offset=page.offset)


@router.get("/snapshot/{snapshot_id}/stats", response_model=SnapshotStatsResponse)
async def get_stats(
    snapshot_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Estadísticas agregadas de un snapshot, calculadas en SQL (queries/snapshot_summary.sql)."""
    await _require_snapshot(db, snapshot_id, current_user)
    summary = await snapshot_summary(db, snapshot_id)
    games = summary["games_played"]
    return SnapshotStatsResponse(
        snapshot_id=snapshot_id,
        games_played=games,
        winrate=float(summary["winrate"]),
        avg_kda=float(summary["avg_kda"]),
        avg_cs_per_min=float(summary["avg_cs_per_min"]),
        avg_damage_per_min=float(summary["avg_damage_per_min"]),
        avg_gold_per_min=float(summary["avg_gold_per_min"]),
        avg_vision=float(summary["avg_vision"]),
        avg_kill_participation=float(summary["avg_kill_participation"]),
        first_dragon_rate=f"{summary['first_dragons']}/{games}",
        herald_rate=f"{summary['heralds']}/{games}",
        two_or_more_void_grubs_rate=f"{summary['void_grubs']}/{games}",
    )


@router.get("/player/{player_id}/most-played", response_model=list[MostPlayedChampionResponse])
async def get_most_played_champions(
    player_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ddragon_client: DDragonClient = Depends(get_ddragon_client),
):
    """Top 3 campeones en las últimas partidas del jugador (desde el historial en BD)."""
    if not await get_player_by_id(db, player_id, user_id=current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found.")

    counts: Counter[str] = Counter()
    wins: Counter[str] = Counter()
    for match in await get_history_from_cache(db, player_id):
        counts[match.champion] += 1
        wins[match.champion] += match.win

    version = ddragon_client.version or FALLBACK_VERSION
    return [
        MostPlayedChampionResponse(
            champion_name=name,
            games_played=count,
            win_rate=round(wins[name] / count * 100, 2),
            icon_url=ddragon_client.champion_icon_url(version, name),
        )
        for name, count in counts.most_common(3)
    ]
