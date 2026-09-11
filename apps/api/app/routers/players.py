from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.crud.player import (
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
from app.schemas.player import PlayerCreate, PlayerResponse, PlayerUpdate, RoleSummary

router = APIRouter(prefix="/players", tags=["players"])


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
    """Jugadores del usuario autenticado."""
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
    """Crea un jugador validándolo contra la Riot API. 404 si no existe en Riot."""
    try:
        player = await create_player(db, player_in, user_id=current_user.id)
    except ValueError as e:
        if str(e) == "duplicate":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This player is already in your list.")
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


@router.get("/{player_id}/summary", response_model=list[RoleSummary])
async def get_player_summary(
    player_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Rendimiento por rol sobre todas las partidas guardadas del jugador."""
    player = await _owned_player(player_id, db, current_user)
    return [RoleSummary.model_validate(dict(row)) for row in await role_summary(db, player.puuid)]


@router.put("/{player_id}", response_model=PlayerResponse)
async def edit_player(
    player_id: int,
    player_in: PlayerUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Actualiza los campos editables de un jugador (rol, apodo, notas)."""
    return await update_player(db, await _owned_player(player_id, db, current_user), player_in)


@router.post("/{player_id}/refresh", response_model=PlayerResponse)
async def refresh_player(
    player_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Refresca el rango e icono del jugador consultando la Riot API."""
    return await refresh_player_rank(db, await _owned_player(player_id, db, current_user))


@router.delete("/{player_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_player(
    player_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Elimina un jugador y sus snapshots."""
    await delete_player(db, await _owned_player(player_id, db, current_user))
