"""Payload match-v5 → ParticipantStats."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ygg_core.domain.participant import ParticipantStats
from ygg_core.domain.roles import role_from_position, role_matches_filter

JsonDict = dict[str, Any]

# Partidas más cortas que esto son remakes y no cuentan.
REMAKE_MAX_SECONDS = 210

# Riot devuelve algunos nombres que no coinciden con las claves de Data Dragon.
_CHAMPION_NAME_FIXES: dict[str, str] = {
    "FiddleSticks": "Fiddlesticks",
}


def normalize_champion(name: str) -> str:
    return _CHAMPION_NAME_FIXES.get(name, name)


def find_participant(match_data: JsonDict, puuid: str) -> JsonDict | None:
    participants: list[JsonDict] = match_data.get("info", {}).get("participants", [])
    return next((p for p in participants if p.get("puuid") == puuid), None)


def player_role_in_match(match_data: JsonDict, puuid: str) -> str:
    participant = find_participant(match_data, puuid)
    if participant is None:
        return "UNKNOWN"
    return role_from_position(participant.get("teamPosition"))


def role_bound_item_for(match_data: JsonDict, puuid: str) -> int | None:
    """Objeto de recompensa de la Role Quest del jugador, o None si no está en la partida."""
    participant = find_participant(match_data, puuid)
    if participant is None:
        return None
    return int(participant.get("roleBoundItem") or 0)


def _runes(participant: JsonDict) -> tuple[int, int]:
    primary_rune = 0
    secondary_tree = 0
    for style in participant.get("perks", {}).get("styles", []):
        description = style.get("description")
        if description == "primaryStyle":
            selections = style.get("selections", [])
            if selections:
                primary_rune = selections[0].get("perk", 0)
        elif description == "subStyle":
            secondary_tree = style.get("style", 0)
    return primary_rune, secondary_tree


def _share(value: float, total: float) -> float:
    return round(value / total * 100, 1) if total > 0 else 0.0


def parse_participant(
    match_data: JsonDict,
    puuid: str,
    role_filter: str | None = "ALL",
) -> ParticipantStats | None:
    """Estadísticas del jugador `puuid` en la partida.

    Devuelve None para remakes, si el jugador no está en la partida o si jugó
    un rol distinto de `role_filter`.
    """
    info = match_data["info"]
    if info["gameDuration"] < REMAKE_MAX_SECONDS:
        return None

    participant = find_participant(match_data, puuid)
    if participant is None:
        return None

    role = role_from_position(participant.get("teamPosition"))
    if not role_matches_filter(role, role_filter):
        return None

    team_id = participant["teamId"]
    team = [p for p in info["participants"] if p["teamId"] == team_id]
    team_kills = sum(p["kills"] for p in team)
    team_damage = sum(p["totalDamageDealtToChampions"] for p in team)
    team_gold = sum(p.get("goldEarned", 0) for p in team)

    team_stats = next((t for t in info.get("teams", []) if t["teamId"] == team_id), None)
    if team_stats is None:
        return None
    objectives = team_stats.get("objectives", {})

    primary_rune, secondary_tree = _runes(participant)

    return ParticipantStats(
        match_id=match_data["metadata"]["matchId"],
        creation_time=datetime.fromtimestamp(
            info["gameCreation"] / 1000 + info["gameDuration"], tz=UTC
        ),
        duration=info["gameDuration"],
        queue_id=info.get("queueId", 420),
        game_version=info.get("gameVersion", ""),
        puuid=puuid,
        participant_id=participant.get("participantId", 0),
        team_id=team_id,
        player_role=role,
        champion=normalize_champion(participant["championName"]),
        win=participant["win"],
        kills=participant["kills"],
        deaths=participant["deaths"],
        assists=participant["assists"],
        kill_participation=_share(participant["kills"] + participant["assists"], team_kills),
        vision=participant["visionScore"],
        damage=participant["totalDamageDealtToChampions"],
        gold=participant["goldEarned"],
        total_cs=participant["totalMinionsKilled"] + participant["neutralMinionsKilled"],
        damage_share=_share(participant["totalDamageDealtToChampions"], team_damage),
        first_dragon=objectives.get("dragon", {}).get("first", False),
        void_grubs=objectives.get("horde", {}).get("kills", 0) >= 2,
        herald=objectives.get("riftHerald", {}).get("kills", 0) > 0,
        summoner1_id=participant.get("summoner1Id", 0),
        summoner2_id=participant.get("summoner2Id", 0),
        item0=participant.get("item0", 0),
        item1=participant.get("item1", 0),
        item2=participant.get("item2", 0),
        item3=participant.get("item3", 0),
        item4=participant.get("item4", 0),
        item5=participant.get("item5", 0),
        item6=participant.get("item6", 0),
        primary_rune=primary_rune,
        secondary_tree=secondary_tree,
        gold_share=_share(participant.get("goldEarned", 0), team_gold),
        damage_structures=int(
            participant.get("damageDealtToBuildings", participant.get("damageDealtToTurrets")) or 0
        ),
        enemy_jg_monsters=participant.get("enemyJungleMonsterKills", 0),
        control_wards=participant.get("visionWardsBoughtInGame", 0),
        role_bound_item=participant.get("roleBoundItem") or 0,
        quest_completed=False,
    )
