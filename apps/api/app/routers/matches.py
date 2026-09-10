import logging
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.crud.player import get_player_by_id
from app.crud.snapshot import (
    get_matches_by_snapshot,
    get_snapshot_by_id,
)
from app.db.models.match import Match
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.match import (
    MatchResponse,
    MostPlayedChampionResponse,
    SnapshotStatsResponse,
)
from app.service.ddragon_client import DDragonClient, get_ddragon_client
from app.service.match_history import get_history_from_cache, is_history_fresh, update_history_cache
from app.service.riot import create_secure_session, participant_to_match, player_ref, riot_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/matches", tags=["matches"])


def _to_responses(matches: list[Match]) -> list[MatchResponse]:
    return [MatchResponse.model_validate(m) for m in matches]



@router.get("/player/{player_id}", response_model=list[MatchResponse])
async def list_live_matches(
    player_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    live: bool = Query(default=False, description="Force full fetch from Riot API"),
    sync: bool = Query(
        default=False,
        description="Fetch new matches from Riot until stored history is reached",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Últimas N partidas reales del jugador, sin filtro de rol ni dependencia de snapshots."""
    player = get_player_by_id(db, player_id, user_id=current_user.id)
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found.")

    force_refresh = live or sync

    if not force_refresh and is_history_fresh(player):
        cached = get_history_from_cache(db, player_id, limit=limit)
        if cached:
            return _to_responses(cached)

    try:
        client = riot_client(player.region)
        async with create_secure_session() as session:
            participants = await client.fetch_participants(
                session,
                player_ref(player),
                max_matches=limit,
                role_filter=None,
                include_timeline=False,
            )
        matches = [participant_to_match(p) for p in participants]
        if matches:
            update_history_cache(db, player, matches)
            return _to_responses(matches)
    except Exception as exc:
        logger.warning("[%s] History fetch failed (%s); serving stale cache.", player.game_name, exc)
        stale = get_history_from_cache(db, player_id)
        if stale:
            return _to_responses(stale)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not load match history. Riot API unavailable, please try again later.",
        )

    return []


@router.get("/snapshot/{snapshot_id}", response_model=list[MatchResponse])
def list_matches(
    snapshot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Devuelve todas las partidas de un snapshot (solo BD)."""
    snapshot = get_snapshot_by_id(db, snapshot_id, user_id=current_user.id)
    if not snapshot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snapshot not found.")
    matches = get_matches_by_snapshot(db, snapshot_id, user_id=current_user.id)
    return _to_responses(matches)


@router.get("/snapshot/{snapshot_id}/stats", response_model=SnapshotStatsResponse)
def get_stats(
    snapshot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Estadísticas agregadas de un snapshot."""
    snapshot = get_snapshot_by_id(db, snapshot_id, user_id=current_user.id)
    if not snapshot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snapshot not found.")

    matches = get_matches_by_snapshot(db, snapshot_id, user_id=current_user.id)
    match_responses = [MatchResponse.model_validate(m) for m in matches]
    return SnapshotStatsResponse.from_matches(snapshot_id, match_responses)


@router.get("/player/{player_id}/most-played", response_model=list[MostPlayedChampionResponse])
async def get_most_played_champions(
    player_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ddragon_client: DDragonClient = Depends(get_ddragon_client),
):
    """Top 3 campeones en las últimas partidas del jugador (desde snapshot en BD)."""
    player = get_player_by_id(db, player_id, user_id=current_user.id)
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found.")

    matches = get_history_from_cache(db, player_id)

    champion_counts: Counter[str] = Counter()
    champion_wins: Counter[str] = Counter()
    for m in matches:
        match_data = MatchResponse.model_validate(m)
        champion_counts[match_data.champion] += 1
        if match_data.win:
            champion_wins[match_data.champion] += 1

    current_version = ddragon_client.version or "16.9.1"
    response = []
    for name, count in champion_counts.most_common(3):
        wins = champion_wins[name]
        win_rate = round((wins / count) * 100, 2) if count > 0 else 0.0
        response.append(
            MostPlayedChampionResponse(
                champion_name=name,
                games_played=count,
                win_rate=win_rate,
                icon_url=ddragon_client.champion_icon_url(current_version, name),
            )
        )
    return response
