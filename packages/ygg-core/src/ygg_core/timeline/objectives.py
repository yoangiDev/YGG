"""Vision before dragon and baron: wards placed next to the pit before each objective."""

from __future__ import annotations

from typing import Any, TypedDict

from ygg_core.domain.participant import WardEvent

JsonDict = dict[str, Any]

# Objective pits in game coordinates (0-15000). ELITE_MONSTER_KILL
# events usually come without `position`.
OBJECTIVE_PIT_POSITIONS: dict[str, tuple[int, int]] = {
    "DRAGON": (9866, 4414),
    "BARON_NASHOR": (5007, 10471),
}
OBJECTIVE_RADIUS = 2500
OBJECTIVE_PREP_WINDOW_MS = 90_000

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
    """Dragon and baron kills with the pit position resolved."""
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
    """Wards placed within 2500 units of the dragon/baron in the 90 s before its death."""
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
