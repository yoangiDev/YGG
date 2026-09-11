from enum import Enum

from pydantic import BaseModel


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
    nickname: str | None = ""
    role: Role = Role.ALL
    notes: str | None = ""


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
    tier: str | None = ""
    rank: str | None = ""
    lp: int | None = 0
    profile_icon_id: int | None = 0  # el frontend construye la URL con Data Dragon
    wins: int | None = 0
    losses: int | None = 0
    win_rate: float = 0.0

    model_config = {"from_attributes": True}


class RoleSummary(BaseModel):
    """Rendimiento agregado de un jugador en un rol (consulta SQL player_role_summary)."""
    role: str
    games: int
    win_rate: float
    kda: float
    cs_per_min: float
    gold_diff_14: float | None
    deaths: float
