import logging

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.config import settings
from app.crud.player import champion_stats, get_player_by_id
from app.crud.snapshot import get_matches_page, get_snapshot_by_id, get_snapshot_match
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.common import Page, PageParams
from app.schemas.match import MatchResponse, PlayerChampionStats, WpaTimelineResponse
from app.schemas.match_details import LobbyRank, MatchDetailsResponse
from app.service.lobby_rank import get_lobby_rank
from app.service.match_details import (
    MatchDetailsUnavailable,
    get_match_summary,
    ranked_participants,
    user_can_view_match,
)
from app.service.match_history import fetch_history_page, get_history_from_cache, is_history_fresh
from app.service.season import season_range

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/matches", tags=["matches"])

# match-v5 ids: platform and number (EUW1_7200000123, KR_7123456789).
MATCH_ID_PATTERN = r"^[A-Za-z0-9]+(?:_[A-Za-z0-9]+)+$"


def _to_responses(matches) -> list[MatchResponse]:
    """Accepts ORM rows or core ParticipantStats: MatchResponse reads attributes."""
    return [MatchResponse.model_validate(m) for m in matches]


async def _history_responses(db: AsyncSession, puuid: str, matches) -> list[MatchResponse]:
    """Like _to_responses, with the grade, position and MVP/ACE badge of each match."""
    responses = _to_responses(matches)
    ranked = await ranked_participants(db, puuid, [r.match_id for r in responses])
    for response in responses:
        if participant := ranked.get(response.match_id):
            response.score, response.placement, response.badge = participant.score, participant.placement, participant.badge
    return responses


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
    """The player's history by pages, from the newest match to the oldest.

    The first page comes from the database if it was synced less than an
    hour ago; the others follow Riot's pagination, reusing what is already stored. If
    Riot fails, what is stored is served for that page.
    """
    player = await get_player_by_id(db, player_id, user_id=current_user.id)
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found.")

    # In the demo the database is the only source: Riot is never queried.
    from_cache = settings.demo_mode or (offset == 0 and not (live or sync) and is_history_fresh(player))
    name, puuid = player.game_name, player.puuid  # after a rollback the ORM attributes expire
    if from_cache:
        cached = await get_history_from_cache(db, player_id, limit=limit, offset=offset)
        # fresh is not complete: if the last sync downloaded 20 and now 100 are requested, you have to go to Riot
        if settings.demo_mode or len(cached) >= limit:
            return await _history_responses(db, puuid, cached)

    try:
        page, _ = await fetch_history_page(db, player, offset=offset, limit=limit)
        return await _history_responses(db, puuid, page)
    except Exception as exc:
        await db.rollback()
        logger.warning("[%s] History page offset=%d failed (%s); serving stored matches.", name, offset, exc)

    stored = await get_history_from_cache(db, player_id, limit=limit, offset=offset)
    if not stored:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not load match history. Riot API unavailable, please try again later.",
        )
    return await _history_responses(db, puuid, stored)


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
    """Matches of a snapshot, from newest to oldest (DB only)."""
    await _require_snapshot(db, snapshot_id, current_user)
    matches, total = await get_matches_page(
        db, snapshot_id, current_user.id, limit=page.limit, offset=page.offset
    )
    return Page[MatchResponse](items=_to_responses(matches), total=total, limit=page.limit, offset=page.offset)


@router.get(
    "/snapshot/{snapshot_id}/{match_id}/wpa",
    response_model=WpaTimelineResponse,
    responses={404: {"description": "Not a match of that snapshot"}},
)
async def get_match_wpa(
    snapshot_id: int,
    match_id: str = Path(max_length=50, pattern=MATCH_ID_PATTERN),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """WPA timeline of a match in the snapshot: each event the player took part in,
    with the win-probability points attributed to them, the WP curve and the grade."""
    row = await get_snapshot_match(db, snapshot_id, current_user.id, match_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found in this snapshot.")
    return WpaTimelineResponse.from_participant(row)


@router.get("/player/{player_id}/champions", response_model=list[PlayerChampionStats])
async def get_champion_stats(
    player_id: int,
    limit: int = Query(default=10, ge=1, le=200),
    season: bool = Query(default=False, description="Only games from the current season"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Per-champion performance over the player's stored matches (history and analysis)."""
    if not await get_player_by_id(db, player_id, user_id=current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found.")
    start, end = season_range()
    rows = await champion_stats(db, player_id, limit=limit, since=start if season else None, until=end if season else None)
    return [PlayerChampionStats.model_validate(dict(row)) for row in rows]


@router.get(
    "/{match_id}/details",
    response_model=MatchDetailsResponse,
    responses={
        404: {"description": "Not a match of the user's players (or not stored, in the demo)"},
        503: {"description": "Riot API unavailable"},
    },
)
async def get_match_details(
    match_id: str = Path(max_length=50, pattern=MATCH_ID_PATTERN),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The 10 participants of a match: build, stats and relative score.

    The first time it is requested from Riot and stored; afterwards it comes from the database.
    """
    if not await user_can_view_match(db, match_id, current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found.")
    try:
        summary = await get_match_summary(db, match_id)
    except MatchDetailsUnavailable as exc:
        code = status.HTTP_404_NOT_FOUND if settings.demo_mode else status.HTTP_503_SERVICE_UNAVAILABLE
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    except Exception as exc:
        await db.rollback()
        logger.warning("Match %s details failed (%s).", match_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not load match details. Riot API unavailable, please try again later.",
        ) from exc
    return MatchDetailsResponse.model_validate(summary.to_dict())


@router.get(
    "/{match_id}/lobby-rank",
    response_model=LobbyRank,
    responses={
        404: {"description": "Not a match of the user's players"},
        503: {"description": "Riot API unavailable"},
    },
)
async def get_match_lobby_rank(
    match_id: str = Path(max_length=50, pattern=MATCH_ID_PATTERN),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Rank of the 10 players and the lobby's average elo.

    It is requested when the match is expanded. It is computed the first time with the rank of that
    moment (Riot doesn't store the one they had when playing) and afterwards it is served stored.
    """
    if not await user_can_view_match(db, match_id, current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found.")
    try:
        return await get_lobby_rank(db, match_id)
    except MatchDetailsUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
