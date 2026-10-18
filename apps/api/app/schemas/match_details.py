from datetime import datetime
from typing import Literal

from pydantic import BaseModel, computed_field
from ygg_core.metrics.match_score import metric_status


class MatchParticipantDetails(BaseModel):
    """A participant in the match.

    `score` is their 0-100 grade against the role's Challenger matches: 70 is playing better than two out of three
    (ygg_core/metrics/match_score.py).
    """

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

    @computed_field
    @property
    def kda_status(self) -> str:
        """KDA against the role's Challenger matches."""
        return metric_status("kda", self.kda, self.role)


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


class PlayerRank(BaseModel):
    """A player's SoloQ rank; tier, division and lp as null if they have none."""

    puuid: str
    tier: str | None = None
    division: str | None = None
    lp: int | None = None


class LobbyRank(BaseModel):
    """Rank of each player and the lobby's average elo, taken the first time the match was opened.

    Riot doesn't store the rank they had when playing. With no ranked players, tier, division and lp are null.
    """

    tier: str | None = None
    division: str | None = None
    lp: int | None = None
    ranked_players: int
    players: list[PlayerRank] = []


class MatchDetailsResponse(BaseModel):
    match_id: str
    creation_time: datetime
    duration: int
    queue_id: int
    game_version: str
    teams: list[MatchTeamDetails]
