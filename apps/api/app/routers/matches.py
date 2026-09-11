import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.config import settings
from app.crud.player import champion_stats, get_player_by_id
from app.crud.snapshot import get_matches_page, get_snapshot_by_id, snapshot_summary
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.common import Page, PageParams
from app.schemas.match import MatchResponse, PlayerChampionStats, SnapshotStatsResponse
from app.service.match_history import fetch_history_page, get_history_from_cache, is_history_fresh

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/matches", tags=["matches"])


def _to_responses(matches) -> list[MatchResponse]:
    """Acepta filas ORM o ParticipantStats del core: MatchResponse lee atributos."""
    return [MatchResponse.model_validate(m) for m in matches]


@router.get(
    "/player/{player_id}",
    response_model=list[MatchResponse],
    responses={503: {"description": "Riot API unavailable and nothing stored for that page"}},
)
async def list_player_matches(
    player_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=1000, description="Matches to skip, newest first"),
    live: bool = Query(default=False, description="Force a fresh page from Riot API"),
    sync: bool = Query(default=False, description="Same as live (kept for older clients)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Historial del jugador por páginas, de la partida más reciente a la más antigua.

    La primera página sale de la base de datos si se sincronizó hace menos de una
    hora; las demás siguen la paginación de Riot reutilizando lo ya guardado. Si
    Riot falla, se sirve lo guardado para esa página.
    """
    player = await get_player_by_id(db, player_id, user_id=current_user.id)
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found.")

    # En la demo la base de datos es la única fuente: nunca se consulta a Riot.
    from_cache = settings.demo_mode or (offset == 0 and not (live or sync) and is_history_fresh(player))
    if from_cache:
        return _to_responses(await get_history_from_cache(db, player_id, limit=limit, offset=offset))

    name = player.game_name  # tras un rollback los atributos del ORM caducan
    try:
        return _to_responses(await fetch_history_page(db, player, offset=offset, limit=limit))
    except Exception as exc:
        await db.rollback()
        logger.warning("[%s] History page offset=%d failed (%s); serving stored matches.", name, offset, exc)

    stored = await get_history_from_cache(db, player_id, limit=limit, offset=offset)
    if not stored:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not load match history. Riot API unavailable, please try again later.",
        )
    return _to_responses(stored)


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


@router.get("/player/{player_id}/champions", response_model=list[PlayerChampionStats])
async def get_champion_stats(
    player_id: int,
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Rendimiento por campeón sobre todas las partidas guardadas del jugador (historial y análisis)."""
    if not await get_player_by_id(db, player_id, user_id=current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found.")
    return [PlayerChampionStats.model_validate(dict(row)) for row in await champion_stats(db, player_id, limit=limit)]
