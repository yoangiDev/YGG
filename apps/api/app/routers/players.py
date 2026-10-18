import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.crud.player import (
    current_icon,
    create_player,
    delete_player,
    get_player_by_id,
    get_players,
    refresh_player_rank,
    role_summary,
    update_player,
)
from app.db.models.player import Player
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.common import Page, PageParams
from app.schemas.player import (
    EloPoint,
    PlayerCreate,
    PlayerResponse,
    PlayerUpdate,
    RoleSummary,
    SeasonSync,
)
from app.service.elo import elo_history
from app.service.season import sync_season_page

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/players", tags=["players"])

MAX_ACCOUNTS = 5  # the main one and a smurf or two


async def _owned_player(player_id: int, db: AsyncSession, user: User) -> Player:
    player = await get_player_by_id(db, player_id, user_id=user.id)
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found.")
    return player


@router.get("/", response_model=Page[PlayerResponse])
async def list_players(
    page: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The authenticated user's players."""
    players, total = await get_players(db, current_user.id, limit=page.limit, offset=page.offset)
    return Page[PlayerResponse](
        items=[PlayerResponse.model_validate(p) for p in players],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.post("/", response_model=PlayerResponse, status_code=status.HTTP_201_CREATED)
async def add_player(
    player_in: PlayerCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Links one of the user's accounts, validating it against the Riot API. 404 if it doesn't exist in Riot, 409 if they already have it
    linked or already have MAX_ACCOUNTS. That it is theirs is proven afterwards by its profile icon (`/verify`)."""
    linked = await db.scalar(select(func.count(Player.id)).where(Player.user_id == current_user.id))
    if (linked or 0) >= MAX_ACCOUNTS:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"You can link up to {MAX_ACCOUNTS} accounts.")
    try:
        player = await create_player(db, player_in, user_id=current_user.id)
    except ValueError as e:
        if str(e) == "duplicate":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This account is already linked.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    if not player:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player not found on Riot Games. Check the name and tag.",
        )
    return player


@router.get("/{player_id}", response_model=PlayerResponse)
async def get_player(player_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    return await _owned_player(player_id, db, current_user)


@router.post(
    "/{player_id}/verify",
    response_model=PlayerResponse,
    responses={409: {"description": "The profile icon is not the one asked, or another user verified it"}},
)
async def verify_player(
    player_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Checks with Riot that the account has the profile icon on that was requested when linking it: only whoever
    has the account can change it. A LoL account is verified by a single YGG user."""
    player = await _owned_player(player_id, db, current_user)
    if player.verified:
        return player
    taken = select(Player.id).where(Player.puuid == player.puuid, Player.verified_at.is_not(None), Player.id != player.id)
    if await db.scalar(taken) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="This League account is already verified by another YGG user.")
    icon = await current_icon(player)
    if icon is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Riot didn't answer. Try again in a minute.")
    if icon != player.verify_icon:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="Your profile icon isn't the one shown yet. Riot can take a minute to see the change.")
    player.verified_at, player.verify_icon, player.profile_icon_id = datetime.now(UTC), None, icon
    await db.commit()
    await db.refresh(player)
    return player


@router.get("/{player_id}/summary", response_model=list[RoleSummary])
async def get_player_summary(
    player_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Performance by role over all the player's stored matches."""
    player = await _owned_player(player_id, db, current_user)
    return [RoleSummary.model_validate(dict(row)) for row in await role_summary(db, player.puuid)]


@router.put("/{player_id}", response_model=PlayerResponse)
async def edit_player(
    player_id: int,
    player_in: PlayerUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Updates a player's editable fields (role, nickname, notes)."""
    return await update_player(db, await _owned_player(player_id, db, current_user), player_in)


@router.post("/{player_id}/refresh", response_model=PlayerResponse)
async def refresh_player(
    player_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Refreshes the player's rank and icon by querying the Riot API."""
    return await refresh_player_rank(db, await _owned_player(player_id, db, current_user))


@router.post(
    "/{player_id}/season-sync",
    response_model=SeasonSync,
    responses={503: {"description": "Riot API unavailable"}},
)
async def sync_season(
    player_id: int,
    offset: int = Query(default=0, ge=0, le=10_000, description="Match ids to skip (next_offset of the previous call)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Downloads a page of the season's ranked matches and stores them.

    It is called in a loop with the `next_offset` it returns until `done` is true;
    that way no request waits for Riot to release quota for hundreds of matches.
    """
    player = await _owned_player(player_id, db, current_user)
    try:
        return await sync_season_page(db, player, offset)
    except Exception as exc:
        await db.rollback()
        logger.warning("Season sync of player %s failed (%s).", player_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not download the season. Riot API unavailable, please try again later.",
        ) from exc


@router.get("/{player_id}/elo", response_model=list[EloPoint])
async def get_elo(player_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """One point per day since tracking was turned on, from oldest to newest."""
    player = await _owned_player(player_id, db, current_user)
    return await elo_history(db, player.id)


@router.delete("/{player_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_player(
    player_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Deletes a player and their snapshots."""
    await delete_player(db, await _owned_player(player_id, db, current_user))
