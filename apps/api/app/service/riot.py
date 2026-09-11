"""Puente entre la API y ygg-core.

Construye clientes de Riot con la configuración de la API y traduce entre los
objetos de dominio del core (ParticipantStats) y los modelos ORM.
"""

from dataclasses import MISSING, fields
from typing import Any

from ygg_core.domain.participant import (
    TIMELINE_FIELDS,
    ParticipantStats,
    PlayerRef,
    RankInfo,
    SummonerInfo,
)
from ygg_core.riot.client import RiotAPIClient
from ygg_core.riot.http import create_secure_session

from app.core.config import settings
from app.db.models.match import Match
from app.db.models.participant import MatchParticipant
from app.db.models.player import Player

__all__ = [
    "apply_rank",
    "apply_summoner",
    "copy_timeline_fields",
    "create_secure_session",
    "match_row",
    "participant_from_row",
    "participant_row",
    "player_ref",
    "riot_client",
]

_MATCH_COLUMNS = tuple(column.key for column in Match.__table__.columns)
_PARTICIPANT_COLUMNS = tuple(
    column.key for column in MatchParticipant.__table__.columns if column.key != "id"
)
_DOMAIN_FIELDS = fields(ParticipantStats)


def riot_client(region: str) -> RiotAPIClient:
    return RiotAPIClient(settings.riot_api_key, region.lower())


def player_ref(player: Player) -> PlayerRef:
    return PlayerRef(
        puuid=player.puuid,
        game_name=player.game_name or "",
        tag_line=player.tag_line or "",
    )


def match_row(stats: ParticipantStats) -> dict[str, Any]:
    return {name: getattr(stats, name) for name in _MATCH_COLUMNS}


def participant_row(stats: ParticipantStats) -> dict[str, Any]:
    return {name: getattr(stats, name) for name in _PARTICIPANT_COLUMNS}


def participant_from_row(row: MatchParticipant) -> ParticipantStats:
    """Fila ORM → dominio. Los valores NULL toman el valor por defecto del dominio.

    duration, queue_id y game_version llegan de la partida a través de las
    propiedades de MatchParticipant.
    """
    values = {}
    for f in _DOMAIN_FIELDS:
        value = getattr(row, f.name)
        if value is None:
            if f.default_factory is not MISSING:
                value = f.default_factory()
            elif f.default is not MISSING:
                value = f.default
        values[f.name] = value
    return ParticipantStats(**values)


def copy_timeline_fields(target: MatchParticipant, source: ParticipantStats | MatchParticipant) -> None:
    """Refresca en una fila existente las métricas derivadas del timeline."""
    for name in TIMELINE_FIELDS:
        setattr(target, name, getattr(source, name))


def apply_rank(player: Player, rank: RankInfo | None) -> bool:
    if rank is None:
        return False
    player.tier = rank.tier
    player.rank = rank.rank
    player.lp = rank.lp
    player.wins = rank.wins
    player.losses = rank.losses
    return True


def apply_summoner(player: Player, summoner: SummonerInfo | None) -> None:
    if summoner is not None:
        player.profile_icon_id = summoner.profile_icon_id
