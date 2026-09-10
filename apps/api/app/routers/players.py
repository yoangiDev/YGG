from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models.user import User
from app.auth.dependencies import get_current_user
from app.schemas.player import PlayerCreate, PlayerUpdate, PlayerResponse
from app.crud.player import (
    create_player, get_player_by_id, get_all_players,
    update_player, refresh_player_rank, delete_player
)

router = APIRouter(prefix="/players", tags=["players"])


# ── GET /players ───────────────────────────────────────────────────────────────

@router.get("/", response_model=list[PlayerResponse])
def list_players(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Devuelve todos los jugadores del usuario autenticado."""
    return get_all_players(db, user_id=current_user.id)


# ── POST /players ──────────────────────────────────────────────────────────────

@router.post("/", response_model=PlayerResponse, status_code=status.HTTP_201_CREATED)
async def add_player(
    player_in: PlayerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Crea un jugador validándolo contra la Riot API.
    Devuelve 404 si el jugador no existe en Riot.
    """
    try:
        player = await create_player(db, player_in, user_id=current_user.id)
    except ValueError as e:
        if str(e) == "duplicate":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This player is already in your list."
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    if not player:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player not found on Riot Games. Check the name and tag."
        )
    return player


# ── GET /players/{player_id} ───────────────────────────────────────────────────

@router.get("/{player_id}", response_model=PlayerResponse)
def get_player(
    player_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Devuelve un jugador por su ID."""
    player = get_player_by_id(db, player_id, user_id=current_user.id)
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found.")
    return player


# ── PUT /players/{player_id} ───────────────────────────────────────────────────

@router.put("/{player_id}", response_model=PlayerResponse)
def edit_player(
    player_id: int,
    player_in: PlayerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Actualiza los campos editables de un jugador (rol, apodo, notas)."""
    player = get_player_by_id(db, player_id, user_id=current_user.id)
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found.")
    return update_player(db, player, player_in)


# ── POST /players/{player_id}/refresh ─────────────────────────────────────────

@router.post("/{player_id}/refresh", response_model=PlayerResponse)
async def refresh_player(
    player_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Refresca el rango e icono del jugador consultando la Riot API."""
    player = get_player_by_id(db, player_id, user_id=current_user.id)
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found.")
    return await refresh_player_rank(db, player)


# ── DELETE /players/{player_id} ───────────────────────────────────────────────

@router.delete("/{player_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_player(
    player_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Elimina un jugador y todos sus snapshots y partidas en cascada."""
    player = get_player_by_id(db, player_id, user_id=current_user.id)
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found.")
    delete_player(db, player)