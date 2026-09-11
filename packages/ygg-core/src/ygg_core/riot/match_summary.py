"""Payload match-v5 → MatchSummary con los 10 participantes.

Copia build y estadísticas de cada jugador y les pone nota frente a la media
Challenger de su rol (ver ygg_core.metrics.match_score).
"""

from __future__ import annotations

from datetime import UTC, datetime

from ygg_core.domain.match_summary import MatchSummary, ParticipantSummary, TeamSummary
from ygg_core.domain.roles import role_from_position
from ygg_core.metrics.match_score import score_match
from ygg_core.riot.parsers import JsonDict, _runes, normalize_champion


def _ratio(value: float, total: float) -> float:
    return value / total if total > 0 else 0.0


def _int(participant: JsonDict, key: str) -> int:
    return int(participant.get(key) or 0)


def _participant(
    participant: JsonDict, minutes: float, team_kills: dict[int, int], team_damage: dict[int, int]
) -> ParticipantSummary:
    team_id = int(participant["teamId"])
    kills, deaths, assists = _int(participant, "kills"), _int(participant, "deaths"), _int(participant, "assists")
    cs = _int(participant, "totalMinionsKilled") + _int(participant, "neutralMinionsKilled")
    damage = _int(participant, "totalDamageDealtToChampions")
    vision = _int(participant, "visionScore")
    keystone, secondary_tree = _runes(participant)
    return ParticipantSummary(
        puuid=str(participant.get("puuid") or ""),
        game_name=str(participant.get("riotIdGameName") or participant.get("summonerName") or ""),
        tag_line=str(participant.get("riotIdTagline") or ""),
        champion=normalize_champion(str(participant.get("championName") or "")),
        champion_level=_int(participant, "champLevel"),
        team_id=team_id,
        role=role_from_position(participant.get("teamPosition")),
        win=bool(participant.get("win", False)),
        kills=kills,
        deaths=deaths,
        assists=assists,
        kda=round((kills + assists) / max(deaths, 1), 2),
        kill_participation=round(_ratio(kills + assists, team_kills.get(team_id, 0)) * 100, 1),
        cs=cs,
        cs_per_min=round(cs / minutes, 1),
        gold=_int(participant, "goldEarned"),
        damage=damage,
        damage_per_min=round(damage / minutes, 1),
        damage_share=round(_ratio(damage, team_damage.get(team_id, 0)) * 100, 1),
        damage_taken=_int(participant, "totalDamageTaken"),
        vision_score=vision,
        vision_per_min=round(vision / minutes, 2),
        wards_placed=_int(participant, "wardsPlaced"),
        control_wards=_int(participant, "visionWardsBoughtInGame"),
        items=tuple(_int(participant, f"item{slot}") for slot in range(6)),
        trinket=_int(participant, "item6"),
        spells=(_int(participant, "summoner1Id"), _int(participant, "summoner2Id")),
        keystone=int(keystone or 0),
        secondary_tree=int(secondary_tree or 0),
    )


def _team(team: JsonDict, participants: list[ParticipantSummary], fallback_kills: int) -> TeamSummary:
    objectives: JsonDict = team.get("objectives", {})

    def kills(name: str) -> int:
        return int(objectives.get(name, {}).get("kills", 0) or 0)

    return TeamSummary(
        team_id=int(team["teamId"]),
        win=bool(team.get("win", False)),
        kills=kills("champion") or fallback_kills,
        towers=kills("tower"),
        inhibitors=kills("inhibitor"),
        dragons=kills("dragon"),
        barons=kills("baron"),
        heralds=kills("riftHerald"),
        grubs=kills("horde"),
        atakhans=kills("atakhan"),
        participants=tuple(participants),
    )


def parse_match_summary(match_data: JsonDict) -> MatchSummary:
    info: JsonDict = match_data["info"]
    duration = int(info["gameDuration"])
    minutes = max(duration / 60, 1.0)
    raw_participants: list[JsonDict] = info.get("participants", [])

    team_kills: dict[int, int] = {}
    team_damage: dict[int, int] = {}
    for participant in raw_participants:
        team_id = int(participant["teamId"])
        team_kills[team_id] = team_kills.get(team_id, 0) + _int(participant, "kills")
        team_damage[team_id] = team_damage.get(team_id, 0) + _int(participant, "totalDamageDealtToChampions")

    participants = [_participant(p, minutes, team_kills, team_damage) for p in raw_participants]
    teams = tuple(
        _team(team, [p for p in participants if p.team_id == int(team["teamId"])], team_kills.get(int(team["teamId"]), 0))
        for team in sorted(info.get("teams", []), key=lambda team: int(team["teamId"]))
    )
    return score_match(
        MatchSummary(
            match_id=str(match_data["metadata"]["matchId"]),
            creation_time=datetime.fromtimestamp(info["gameCreation"] / 1000 + duration, tz=UTC),
            duration=duration,
            queue_id=int(info.get("queueId", 420)),
            game_version=str(info.get("gameVersion", "")),
            teams=teams,
        )
    )
