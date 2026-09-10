from pydantic import BaseModel
from typing import Optional
from enum import Enum


class Role(str, Enum):
    TOP     = "TOP"
    JUNGLE  = "JUNGLE"
    MID     = "MID"
    BOTTOM  = "BOTTOM"
    SUPPORT = "SUPPORT"
    ALL     = "ALL"


class PlayerBase(BaseModel):
    game_name: str
    tag_line: str
    region: str
    nickname: str = ""
    role: Role = Role.ALL
    notes: str = ""


class PlayerCreate(PlayerBase):
    """Lo que recibe la API al crear un jugador. Sin puuid ni id — los genera el sistema."""
    pass


class PlayerUpdate(BaseModel):
    """Campos actualizables desde la UI."""
    game_name: str
    tag_line: str
    role: Role
    nickname: str = ""
    notes: str = ""


class PlayerResponse(PlayerBase):
    """Lo que devuelve la API. Incluye id, puuid, datos de rango e icono."""
    id: int
    puuid: str
    tier: str = ""
    rank: str = ""
    lp: int = 0
    profile_icon_id: int = 0  # ID del icono — el frontend construye la URL con Data Dragon
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0

    model_config = {"from_attributes": True}