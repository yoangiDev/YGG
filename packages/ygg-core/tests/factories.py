"""Payloads sintéticos con el formato de match-v5 y timeline-v5.

Los ficheros de `fixtures/match_v5/` se generan con este módulo:

    python packages/ygg-core/tests/factories.py

y `test_parsers.py` comprueba que siguen coincidiendo con el generador.

Guion de la partida (equipo azul = participantes 1-5):
- min 4:50  el top azul (1) muere en su línea por el top (6) y el jungla rojos (7) → gank
- min 8:20  el support azul (5) coloca un control ward junto al dragón
- min 8-9   el jungla azul (2) está en el foso; a los 9:20 asegura el dragón
- min 10:50 el mid azul (3) consigue una solo kill en mid
- min 11:40 el mid azul (3) rota a bot y participa en una kill → roaming
- min 11:30 / 12:20  tops azul y rojo completan su Role Quest
- min 20:00 el mid azul (3) muere tarde en mid
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ygg_core.domain.participant import ParticipantStats
from ygg_core.riot.parsers import parse_participant
from ygg_core.timeline.enrichment import apply_timeline

JsonDict = dict[str, Any]

FIXTURES = Path(__file__).parent / "fixtures"
MATCH_V5 = FIXTURES / "match_v5"
MATCH_ID = "EUW1_7000000001"
GAME_CREATION_MS = 1_780_000_000_000  # mayo de 2026: temporada 26
DURATION = 1845
POSITIONS = ("TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY")
CHAMPIONS = (
    "Gnar", "LeeSin", "Ahri", "Jinx", "Thresh",
    "Renekton", "Viego", "Syndra", "Kaisa", "Nautilus",
)
ROLE_BOUND_ITEMS = {"TOP": 1220, "JUNGLE": 1209, "MIDDLE": 1206, "BOTTOM": 3006, "UTILITY": 1208}
DRAGON_PIT_NEARBY = {"x": 9800, "y": 4500}
MAP_CENTER = {"x": 7500, "y": 7500}


def puuid(participant_id: int) -> str:
    return f"puuid-{participant_id:02d}"


def position(participant_id: int) -> str:
    return POSITIONS[(participant_id - 1) % 5]


def load_json(relative: str) -> JsonDict:
    data: JsonDict = json.loads((FIXTURES / relative).read_text(encoding="utf-8"))
    return data


def make_participant(pid: int) -> JsonDict:
    team_id = 100 if pid <= 5 else 200
    pos = position(pid)
    laner = pos not in ("JUNGLE", "UTILITY")
    return {
        "participantId": pid,
        "puuid": puuid(pid),
        "riotIdGameName": f"Player{pid:02d}",
        "riotIdTagline": "TEST",
        "teamId": team_id,
        "teamPosition": pos,
        "championName": CHAMPIONS[pid - 1],
        "win": team_id == 100,
        "kills": pid % 5 + 2,
        "deaths": (pid + 2) % 4 + 1,
        "assists": (pid * 3) % 9 + 1,
        "visionScore": 70 if pos == "UTILITY" else 15 + pid * 3,
        "totalDamageDealtToChampions": 10_000 + pid * 1_500,
        "goldEarned": 9_000 + pid * 400,
        "totalMinionsKilled": 180 if laner else 30,
        "neutralMinionsKilled": 150 if pos == "JUNGLE" else 8,
        "summoner1Id": 4,
        "summoner2Id": 11 if pos == "JUNGLE" else 14,
        "item0": 3031,
        "item1": 3006,
        "item2": 6672,
        "item3": 3036,
        "item4": 0,
        "item5": 0,
        "item6": 3340,
        "perks": {
            "styles": [
                {"description": "primaryStyle", "style": 8100, "selections": [{"perk": 8112}, {"perk": 8139}]},
                {"description": "subStyle", "style": 8300, "selections": [{"perk": 8304}]},
            ]
        },
        "damageDealtToBuildings": 2_000 + pid * 300,
        "enemyJungleMonsterKills": 6 if pos == "JUNGLE" else 0,
        "visionWardsBoughtInGame": 6 if pos == "UTILITY" else 2,
        "roleBoundItem": ROLE_BOUND_ITEMS[pos],
    }


def make_match(
    match_id: str = MATCH_ID,
    *,
    duration: int = DURATION,
    game_creation: int = GAME_CREATION_MS,
    overrides: dict[int, JsonDict] | None = None,
) -> JsonDict:
    participants = [make_participant(pid) for pid in range(1, 11)]
    for pid, extra in (overrides or {}).items():
        participants[pid - 1].update(extra)
    return {
        "metadata": {
            "dataVersion": "2",
            "matchId": match_id,
            "participants": [p["puuid"] for p in participants],
        },
        "info": {
            "gameCreation": game_creation,
            "gameDuration": duration,
            "gameMode": "CLASSIC",
            "gameVersion": "16.10.712.3456",
            "mapId": 11,
            "platformId": "EUW1",
            "queueId": 420,
            "participants": participants,
            "teams": [
                {
                    "teamId": 100,
                    "win": True,
                    "objectives": {
                        "dragon": {"first": True, "kills": 3},
                        "horde": {"first": True, "kills": 4},
                        "riftHerald": {"first": True, "kills": 1},
                    },
                },
                {
                    "teamId": 200,
                    "win": False,
                    "objectives": {
                        "dragon": {"first": False, "kills": 1},
                        "horde": {"first": False, "kills": 2},
                        "riftHerald": {"first": False, "kills": 0},
                    },
                },
            ],
        },
    }


def champion_kill(ts: int, killer: int, victim: int, assists: list[int], x: int, y: int) -> JsonDict:
    return {
        "type": "CHAMPION_KILL",
        "timestamp": ts,
        "killerId": killer,
        "victimId": victim,
        "assistingParticipantIds": assists,
        "position": {"x": x, "y": y},
    }


def default_events() -> dict[int, list[JsonDict]]:
    """Eventos por índice de frame (los de un frame ocurren antes de su timestamp)."""
    return {
        3: [{"type": "WARD_PLACED", "timestamp": 170_000, "creatorId": 2, "wardType": "YELLOW_TRINKET"}],
        5: [champion_kill(290_000, killer=6, victim=1, assists=[7], x=1500, y=9000)],
        9: [
            {
                "type": "WARD_PLACED",
                "timestamp": 500_000,
                "creatorId": 5,
                "wardType": "CONTROL_WARD",
                "position": {"x": 9700, "y": 4600},
            }
        ],
        10: [
            {
                "type": "ELITE_MONSTER_KILL",
                "timestamp": 560_000,
                "killerId": 2,
                "killerTeamId": 100,
                "monsterType": "DRAGON",
                "monsterSubType": "FIRE_DRAGON",
            }
        ],
        11: [champion_kill(650_000, killer=3, victim=8, assists=[], x=7400, y=7600)],
        12: [
            {"type": "ITEM_DESTROYED", "timestamp": 690_000, "participantId": 1, "itemId": 1200},
            champion_kill(700_000, killer=3, victim=9, assists=[4], x=12000, y=2000),
        ],
        13: [{"type": "ITEM_DESTROYED", "timestamp": 740_000, "participantId": 6, "itemId": 1200}],
        20: [champion_kill(1_200_000, killer=8, victim=3, assists=[9, 10], x=7000, y=7000)],
    }


def make_timeline(
    match_id: str = MATCH_ID,
    *,
    minutes: int = 31,
    events: dict[int, list[JsonDict]] | None = None,
) -> JsonDict:
    events = default_events() if events is None else events
    frames = []
    for minute in range(minutes):
        participant_frames = {}
        for pid in range(1, 11):
            pos = position(pid)
            laner = pos not in ("JUNGLE", "UTILITY")
            location = DRAGON_PIT_NEARBY if pid == 2 and minute in (8, 9) else MAP_CENTER
            participant_frames[str(pid)] = {
                "participantId": pid,
                "level": min(18, 1 + minute // 2),
                "totalGold": 500 + minute * (380 + pid * 5),
                "xp": minute * (400 + pid * 4),
                "minionsKilled": minute * (7 if pid <= 5 else 6) if laner else 0,
                "jungleMinionsKilled": minute * 5 if pos == "JUNGLE" else 0,
                "position": dict(location),
            }
        frames.append(
            {
                "timestamp": minute * 60_000,
                "participantFrames": participant_frames,
                "events": [dict(event) for event in events.get(minute, [])],
            }
        )
    return {
        "metadata": {"dataVersion": "2", "matchId": match_id},
        "info": {"frameInterval": 60_000, "frames": frames},
    }


def blank_stats(**overrides: Any) -> ParticipantStats:
    values: dict[str, Any] = {
        "match_id": "TEST",
        "creation_time": datetime(2026, 5, 1, tzinfo=UTC),
        "duration": 1800,
    }
    values.update(overrides)
    return ParticipantStats(**values)


def enriched(pid: int, *, match_id: str = MATCH_ID) -> ParticipantStats:
    """Estadísticas completas (partida + timeline) del participante `pid`."""
    match = make_match(match_id)
    stats = parse_participant(match, puuid(pid))
    assert stats is not None
    apply_timeline(stats, match, make_timeline(match_id), puuid(pid))
    return stats


def write_fixtures() -> None:
    MATCH_V5.mkdir(parents=True, exist_ok=True)
    for name, payload in (
        (f"{MATCH_ID}.json", make_match()),
        (f"{MATCH_ID}_timeline.json", make_timeline()),
    ):
        (MATCH_V5 / name).write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    write_fixtures()
