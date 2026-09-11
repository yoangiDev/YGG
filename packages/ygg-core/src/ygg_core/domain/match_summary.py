"""Resumen de una partida con sus 10 participantes (lo que se ve al desplegarla)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from typing import Any

# Súbelo si cambia la forma del resumen: los guardados con otra versión se regeneran.
MATCH_SUMMARY_VERSION = 1


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
    kill_participation: float  # 0-100 sobre las kills del equipo
    cs: int
    cs_per_min: float
    gold: int
    damage: int  # a campeones
    damage_per_min: float
    damage_share: float  # 0-100 del daño del equipo
    damage_taken: int
    vision_score: int
    vision_per_min: float
    wards_placed: int
    control_wards: int
    items: tuple[int, ...]  # los 6 huecos de objetos
    trinket: int
    spells: tuple[int, ...]  # los 2 hechizos de invocador
    keystone: int
    secondary_tree: int
    # Puntuación 0-100 relativa a esta partida (el mejor tiene 100) y su posición 1-10.
    score: int = 0
    placement: int = 0
    badge: str | None = None  # "MVP" (mejor del equipo ganador) · "ACE" (mejor del perdedor)


@dataclass(slots=True, frozen=True)
class TeamSummary:
    team_id: int  # 100 azul · 200 rojo
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
    creation_time: datetime  # fin de la partida, UTC (como en ParticipantStats)
    duration: int  # segundos
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
