"""Deaths on the minimap and moving-average window of the trends."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ygg_core.domain.participant import DeathEvent

MAP_SIZE = 15_000


def normalize_position(x: float, y: float) -> tuple[float, float]:
    """Game coordinates → [0,1] with the origin at the top left (as on screen)."""
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


def trend_window_size(n_games: int) -> int:
    """Moving-average window: 15% of the matches, between 3 and 10."""
    return max(3, min(10, round(n_games * 0.15)))
