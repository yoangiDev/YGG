"""Rift zones in game coordinates (0-15000, origin at the bottom left)."""

from __future__ import annotations

# Lane of each role (the jungler has none) and roles that play each lane.
ROLE_LANE: dict[str, str] = {"TOP": "TOP", "MID": "MID", "ADC": "BOT", "SUPPORT": "BOT"}
LANE_ROLES: dict[str, tuple[str, ...]] = {"TOP": ("TOP",), "MID": ("MID",), "BOT": ("ADC", "SUPPORT")}


def in_base(x: float, y: float) -> bool:
    return (x < 3000 and y < 3000) or (x > 12000 and y > 12000)


def is_mid_lane(x: float, y: float) -> bool:
    # The main diagonal goes from (0,0) to (15000,15000): mid is near x = y.
    return not in_base(x, y) and abs(x - y) < 2500


def is_top_lane(x: float, y: float) -> bool:
    return not in_base(x, y) and ((x <= 3200 and y >= 3000) or (y >= 11800 and x <= 12000))


def is_bot_lane(x: float, y: float) -> bool:
    return not in_base(x, y) and ((y <= 3200 and x >= 3000) or (x >= 11800 and y <= 12000))


def lane_at(x: float, y: float) -> str | None:
    """TOP, MID or BOT if the point is in a lane; None in jungle, river or base."""
    if is_top_lane(x, y):
        return "TOP"
    if is_bot_lane(x, y):
        return "BOT"
    if is_mid_lane(x, y):
        return "MID"
    return None
