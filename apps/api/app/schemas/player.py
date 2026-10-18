from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, computed_field
from ygg_core.metrics.benchmarks import RANK_BENCHMARKS
from ygg_core.metrics.match_score import metric_status

from app.schemas.common import Region

TargetRank = Literal[tuple(RANK_BENCHMARKS)]  # the 7 measured leagues, from GOLD to CHALLENGER


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
    """What the API receives when creating a player. No puuid or id — the system generates them."""
    region: Region


class PlayerUpdate(BaseModel):
    """Fields updatable from the UI."""
    game_name: str
    tag_line: str
    role: Role
    nickname: str = ""
    notes: str = ""
    target_rank: TargetRank | None = None  # None: stays as it is


class PlayerResponse(PlayerBase):
    """What the API returns. Includes id, puuid, rank data and icon."""
    id: int
    puuid: str
    tier: str | None = ""
    rank: str | None = ""
    lp: int | None = 0
    profile_icon_id: int | None = 0  # the frontend builds the URL with Data Dragon
    wins: int | None = 0
    losses: int | None = 0
    win_rate: float = 0.0
    target_rank: TargetRank = "CHALLENGER"
    verified: bool = False  # whether it has been checked that the account belongs to whoever linked it (the profile icon)
    verify_icon: int | None = None  # the icon that has to be put on in the client to verify it

    model_config = {"from_attributes": True}


class EloPoint(BaseModel):
    """The rank of one day (the last one queried that day)."""
    day: date
    tier: str
    division: str
    lp: int
    wins: int
    losses: int

    model_config = {"from_attributes": True}


class SeasonSync(BaseModel):
    """Result of fetching a page of the season."""
    downloaded: int          # matches of this page (new or already stored)
    stored_games: int        # season matches stored in total
    done: bool               # Riot returns no more matches from the season
    next_offset: int         # from where to request the next page


class RoleSummary(BaseModel):
    """A player's aggregated performance in one role (SQL query player_role_summary)."""
    role: str
    games: int
    win_rate: float
    kda: float
    cs_per_min: float
    gold_diff_14: float | None
    deaths: float

    @computed_field
    @property
    def kda_status(self) -> str:
        """KDA against the role's Challenger matches."""
        return metric_status("kda", self.kda, self.role)
