"""Puente entre la API y ygg-core.

Construye clientes de Riot con la configuración de la API y traduce entre los
objetos de dominio del core (ParticipantStats) y los modelos ORM.
"""

from dataclasses import MISSING, fields

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
from app.db.models.player import Player

__all__ = [
    "apply_rank",
    "apply_summoner",
    "copy_timeline_fields",
    "create_secure_session",
    "match_to_participant",
    "participant_to_match",
    "player_ref",
    "riot_client",
]

_MATCH_COLUMNS = {column.key for column in Match.__table__.columns} - {"id"}
# Campos del dominio que existen como columna. puuid, participant_id, team_id,
# queue_id y game_version no caben en la tabla ancha actual (llegan en la Fase 2).
_SHARED_FIELDS = tuple(f for f in fields(ParticipantStats) if f.name in _MATCH_COLUMNS)


def riot_client(region: str) -> RiotAPIClient:
    return RiotAPIClient(settings.riot_api_key, region.lower())


def player_ref(player: Player) -> PlayerRef:
    return PlayerRef(
        puuid=player.puuid,
        game_name=player.game_name or "",
        tag_line=player.tag_line or "",
    )


def participant_to_match(stats: ParticipantStats) -> Match:
    return Match(**{f.name: getattr(stats, f.name) for f in _SHARED_FIELDS})


def match_to_participant(match: Match) -> ParticipantStats:
    """Fila ORM → dominio. Las columnas NULL toman el valor por defecto del dominio."""
    values = {}
    for f in _SHARED_FIELDS:
        value = getattr(match, f.name)
        if value is None:
            if f.default_factory is not MISSING:
                value = f.default_factory()
            elif f.default is not MISSING:
                value = f.default
        values[f.name] = value
    return ParticipantStats(**values)


def copy_timeline_fields(target: Match, source: ParticipantStats | Match) -> None:
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
