from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class MatchParticipantDetails(BaseModel):
    """Un participante de la partida. `score` es relativa a la partida (el mejor tiene 100)."""

    puuid: str
    game_name: str
    tag_line: str
    champion: str
    champion_level: int
    team_id: int
    role: str
    win: bool
    kills: int
    deaths: int
    assists: int
    kda: float
    kill_participation: float
    cs: int
    cs_per_min: float
    gold: int
    damage: int
    damage_per_min: float
    damage_share: float
    damage_taken: int
    vision_score: int
    vision_per_min: float
    wards_placed: int
    control_wards: int
    items: list[int]
    trinket: int
    spells: list[int]
    keystone: int
    secondary_tree: int
    score: int
    placement: int
    badge: Literal["MVP", "ACE"] | None = None


class MatchTeamDetails(BaseModel):
    team_id: int
    win: bool
    kills: int
    towers: int
    inhibitors: int
    dragons: int
    barons: int
    heralds: int
    grubs: int
    atakhans: int
    participants: list[MatchParticipantDetails]


class MatchDetailsResponse(BaseModel):
    match_id: str
    creation_time: datetime
    duration: int
    queue_id: int
    game_version: str
    teams: list[MatchTeamDetails]
