"""Agregados derivados de eventos de partida: fases de muerte, mapa y dragones."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ygg_core.domain.participant import DeathEvent, DragonSetup, WardEvent

MAP_SIZE = 15_000
EARLY_PHASE_END_SEC = 480  # minuto 8
LANE_PHASE_END_SEC = 840  # minuto 14


def deaths_by_phase(death_events: Sequence[DeathEvent] | None) -> dict[str, int]:
    early = mid = late = 0
    for death in death_events or []:
        t = death.get("time", 0)
        if t < EARLY_PHASE_END_SEC:
            early += 1
        elif t < LANE_PHASE_END_SEC:
            mid += 1
        else:
            late += 1
    return {"early_deaths": early, "mid_deaths": mid, "late_deaths": late}


def normalize_position(x: float, y: float) -> tuple[float, float]:
    """Coordenadas de juego → [0,1] con el origen arriba a la izquierda (como en pantalla)."""
    nx = max(0.0, min(1.0, x / MAP_SIZE))
    ny = max(0.0, min(1.0, 1.0 - y / MAP_SIZE))
    return round(nx, 4), round(ny, 4)


def normalized_death_events(events: Sequence[DeathEvent] | None) -> list[dict[str, Any]]:
    result = []
    for death in events or []:
        x, y = death.get("x", 0), death.get("y", 0)
        nx, ny = normalize_position(x, y)
        result.append(
            {
                "x": x,
                "y": y,
                "norm_x": nx,
                "norm_y": ny,
                "time": death.get("time", 0),
                "assistingParticipantIds": death.get("assistingParticipantIds", []),
            }
        )
    return result


def normalized_ward_events(events: Sequence[WardEvent] | None) -> list[dict[str, Any]]:
    result = []
    for ward in events or []:
        x, y = ward.get("x", 0), ward.get("y", 0)
        nx, ny = normalize_position(x, y)
        result.append(
            {
                "x": x,
                "y": y,
                "norm_x": nx,
                "norm_y": ny,
                "time": ward.get("time", 0),
                "type": ward.get("type", "unknown"),
            }
        )
    return result


def dragon_setups_summary(setups: Sequence[DragonSetup] | None) -> dict[str, Any]:
    team = [s for s in setups or [] if s.get("team_dragon")]
    if not team:
        return {
            "team_dragons": 0,
            "setup_rate": None,
            "presence_at_kill_rate": None,
            "secure_rate": None,
        }
    n = len(team)

    def rate(flag: str) -> float:
        return round(sum(1 for s in team if s.get(flag)) / n * 100, 1)

    return {
        "team_dragons": n,
        "setup_rate": rate("in_prep_zone"),
        "presence_at_kill_rate": rate("at_kill_zone"),
        "secure_rate": rate("secured_by_jg"),
    }


def trend_window_size(n_games: int) -> int:
    """Ventana de la media móvil: 15 % de las partidas, entre 3 y 10."""
    return max(3, min(10, round(n_games * 0.15)))


def moving_average(values: Sequence[float], window: int) -> list[float]:
    result = []
    for index in range(len(values)):
        chunk = values[max(0, index - window + 1) : index + 1]
        result.append(round(sum(chunk) / len(chunk), 2) if chunk else 0.0)
    return result
