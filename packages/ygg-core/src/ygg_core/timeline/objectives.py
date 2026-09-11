"""Control de objetivos: dragon setups del jungla y visión previa a dragón/barón."""

from __future__ import annotations

from typing import Any, TypedDict

from ygg_core.domain.participant import DragonSetup, WardEvent

JsonDict = dict[str, Any]

# Fosos de objetivos en coordenadas de juego (0-15000). Los eventos
# ELITE_MONSTER_KILL suelen venir sin `position`.
OBJECTIVE_PIT_POSITIONS: dict[str, tuple[int, int]] = {
    "DRAGON": (9866, 4414),
    "BARON_NASHOR": (5007, 10471),
}
OBJECTIVE_RADIUS = 2500
OBJECTIVE_PREP_WINDOW_MS = 90_000
DRAGON_CONTEST_AFTER_MS = 30_000

_OBJECTIVE_RADIUS_SQ = OBJECTIVE_RADIUS * OBJECTIVE_RADIUS


class EliteKill(TypedDict):
    x: int
    y: int
    timestamp: int


def _frames(timeline: JsonDict) -> list[JsonDict]:
    frames: list[JsonDict] = timeline.get("info", {}).get("frames", [])
    return frames


def within_objective_radius(px: float, py: float, ox: float, oy: float) -> bool:
    dx = px - ox
    dy = py - oy
    return (dx * dx + dy * dy) <= _OBJECTIVE_RADIUS_SQ


def _jungler_in_zone_during_window(
    frames: list[JsonDict],
    participant_id: int,
    start_ms: int,
    end_ms: int,
    pit: tuple[int, int],
) -> bool:
    pid_key = str(participant_id)
    for frame in frames:
        ts = frame.get("timestamp", 0)
        if ts < start_ms:
            continue
        if ts > end_ms:
            break
        position = (frame.get("participantFrames", {}).get(pid_key) or {}).get("position")
        if position and within_objective_radius(
            position.get("x", 0), position.get("y", 0), *pit
        ):
            return True
    return False


def _jungler_at_kill_moment(
    frames: list[JsonDict],
    participant_id: int,
    kill_ts: int,
    pit: tuple[int, int],
) -> bool:
    sample: JsonDict | None = None
    for frame in frames:
        if frame.get("timestamp", 0) <= kill_ts:
            sample = frame
        else:
            break
    if sample is None:
        return False
    position = (sample.get("participantFrames", {}).get(str(participant_id)) or {}).get("position")
    if not position:
        return False
    return within_objective_radius(position.get("x", 0), position.get("y", 0), *pit)


def _dragon_contested(frames: list[JsonDict], kill_ts: int, pit: tuple[int, int]) -> bool:
    start_ms = kill_ts - OBJECTIVE_PREP_WINDOW_MS
    end_ms = kill_ts + DRAGON_CONTEST_AFTER_MS
    for frame in frames:
        for event in frame.get("events", []):
            if event.get("type") != "CHAMPION_KILL":
                continue
            if not start_ms <= event.get("timestamp", 0) <= end_ms:
                continue
            position = event.get("position") or {}
            if within_objective_radius(position.get("x", 0), position.get("y", 0), *pit):
                return True
    return False


def extract_dragon_setups(
    timeline: JsonDict,
    participant_id: int,
    player_team_id: int,
) -> list[DragonSetup]:
    """Señales de control de cada dragón para el jungla.

    Usa todos los frames de la ventana de preparación de 90 s, no un único
    instante 30 s antes.
    """
    frames = _frames(timeline)
    if not frames:
        return []

    pit = OBJECTIVE_PIT_POSITIONS["DRAGON"]
    setups: list[DragonSetup] = []
    for frame in frames:
        for event in frame.get("events", []):
            if event.get("type") != "ELITE_MONSTER_KILL" or event.get("monsterType") != "DRAGON":
                continue
            kill_ts = event.get("timestamp", 0)
            setups.append(
                DragonSetup(
                    dragon_time=kill_ts // 1000,
                    dragon_type=event.get("monsterSubType", "UNKNOWN"),
                    team_dragon=event.get("killerTeamId", 0) == player_team_id,
                    in_prep_zone=_jungler_in_zone_during_window(
                        frames, participant_id, kill_ts - OBJECTIVE_PREP_WINDOW_MS, kill_ts, pit
                    ),
                    at_kill_zone=_jungler_at_kill_moment(frames, participant_id, kill_ts, pit),
                    secured_by_jg=event.get("killerId") == participant_id,
                    contested=_dragon_contested(frames, kill_ts, pit),
                )
            )
    return setups


def _elite_monster_position(event: JsonDict) -> tuple[int, int] | None:
    fallback = OBJECTIVE_PIT_POSITIONS.get(event.get("monsterType", ""))
    if fallback is None:
        return None
    position = event.get("position") or {}
    x, y = position.get("x", 0), position.get("y", 0)
    if x > 0 and y > 0:
        return (x, y)
    return fallback


def extract_elite_objective_kills(timeline: JsonDict) -> list[EliteKill]:
    """Muertes de dragón y barón con la posición del foso resuelta."""
    kills: list[EliteKill] = []
    for frame in _frames(timeline):
        for event in frame.get("events", []):
            if event.get("type") != "ELITE_MONSTER_KILL":
                continue
            position = _elite_monster_position(event)
            if position is None:
                continue
            kills.append(EliteKill(x=position[0], y=position[1], timestamp=event.get("timestamp", 0)))
    return kills


def compute_objective_vision_score(
    ward_events: list[WardEvent] | None,
    *,
    timeline: JsonDict | None = None,
    elite_kills: list[EliteKill] | None = None,
) -> int:
    """Wards colocados a menos de 2500 unidades de dragón/barón en los 90 s previos a su muerte."""
    wards = ward_events or []
    if not wards:
        return 0
    kills = elite_kills if elite_kills is not None else (
        extract_elite_objective_kills(timeline) if timeline else []
    )
    if not kills:
        return 0

    score = 0
    for ward in wards:
        ward_ms = ward.get("time", 0) * 1000
        for kill in kills:
            if not 0 <= kill["timestamp"] - ward_ms <= OBJECTIVE_PREP_WINDOW_MS:
                continue
            if within_objective_radius(ward.get("x", 0), ward.get("y", 0), kill["x"], kill["y"]):
                score += 1
                break
    return score
