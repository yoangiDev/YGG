"""Summary of a match with its 10 participants (what is shown when it is expanded)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from typing import Any

# Bump it if the shape of the summary changes: summaries stored with another version are regenerated.
MATCH_SUMMARY_VERSION = 2  # 2: the timeline grade is the one that predicts the analysis grade (before, the WPA one)


@dataclass(slots=True, frozen=True)
class ParticipantSummary:
    puuid: str
    game_name: str
    tag_line: str
    champion: str
    champion_level: int
    team_id: int
    role: str  # TOP · JUNGLE · MID · ADC · SUPPORT · UNKNOWN
    win: bool
    kills: int
    deaths: int
    assists: int
    kda: float
    kill_participation: float  # 0-100 of the team's kills
    cs: int
    cs_per_min: float
    gold: int
    damage: int  # to champions
    damage_per_min: float
    damage_share: float  # 0-100 of the team's damage
    damage_taken: int
    vision_score: int
    vision_per_min: float
    wards_placed: int
    control_wards: int
    items: tuple[int, ...]  # the 6 item slots
    trinket: int
    spells: tuple[int, ...]  # the 2 summoner spells
    keystone: int
    secondary_tree: int
    # Grade 0-100 against the Challenger average for the role (70 = that average) and its position 1-10.
    score: int = 0
    placement: int = 0
    badge: str | None = None  # "MVP" (best of the winning team) · "ACE" (best of the losing one)
    # WPA grade (metrics/wpa.py), if it was read with the timeline. The grade and the position are given from it.
    wpa_grade: int | None = None


@dataclass(slots=True, frozen=True)
class TeamSummary:
    team_id: int  # 100 blue · 200 red
    win: bool
    kills: int
    towers: int
    inhibitors: int
    dragons: int
    barons: int
    heralds: int
    grubs: int
    atakhans: int
    participants: tuple[ParticipantSummary, ...]


def _known(cls: type, data: Mapping[str, Any]) -> dict[str, Any]:
    names = {f.name for f in fields(cls)}
    return {key: value for key, value in data.items() if key in names}


@dataclass(slots=True, frozen=True)
class MatchSummary:
    match_id: str
    creation_time: datetime  # end of the match, UTC (as in ParticipantStats)
    duration: int  # seconds
    queue_id: int
    game_version: str
    teams: tuple[TeamSummary, ...]

    def participants(self) -> list[ParticipantSummary]:
        return [participant for team in self.teams for participant in team.participants]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["creation_time"] = self.creation_time.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> MatchSummary:
        teams = tuple(
            TeamSummary(
                **{
                    **_known(TeamSummary, team),
                    "participants": tuple(
                        ParticipantSummary(
                            **{
                                **_known(ParticipantSummary, participant),
                                "items": tuple(participant["items"]),
                                "spells": tuple(participant["spells"]),
                            }
                        )
                        for participant in team["participants"]
                    ),
                }
            )
            for team in data["teams"]
        )
        return cls(
            match_id=data["match_id"],
            creation_time=datetime.fromisoformat(data["creation_time"]),
            duration=data["duration"],
            queue_id=data["queue_id"],
            game_version=data["game_version"],
            teams=teams,
        )
