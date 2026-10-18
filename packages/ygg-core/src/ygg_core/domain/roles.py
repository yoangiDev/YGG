"""Roles: translation from Riot and filtering rules."""

from __future__ import annotations

# match-v5 teamPosition → internal role.
RIOT_POSITION_TO_ROLE: dict[str, str] = {
    "TOP": "TOP",
    "JUNGLE": "JUNGLE",
    "MIDDLE": "MID",
    "BOTTOM": "ADC",
    "UTILITY": "SUPPORT",
}

_ROLE_ALIASES: dict[str, str] = {
    **RIOT_POSITION_TO_ROLE,
    "MID": "MID",
    "ADC": "ADC",
    "SUPPORT": "SUPPORT",
}

DASHBOARD_ROLES: tuple[str, ...] = ("TOP", "JUNGLE", "MID", "ADC", "SUPPORT")


def role_from_position(team_position: str | None) -> str:
    return RIOT_POSITION_TO_ROLE.get((team_position or "").upper(), "UNKNOWN")


def normalize_role(role: str | None) -> str:
    """Accepts both Riot names (MIDDLE, UTILITY) and internal ones (MID, SUPPORT)."""
    if not role:
        return "UNKNOWN"
    return _ROLE_ALIASES.get(role.upper(), role.upper())


def role_filter_for_player(player_role: str | None) -> str:
    """Role used to filter a registered player's matches."""
    if not player_role:
        return "ALL"
    role = player_role.upper()
    return "ADC" if role == "BOTTOM" else role


def dashboard_role(player_role: str | None) -> str:
    """Role used to compute the dashboard. With no fixed role MID is used."""
    role = role_filter_for_player(player_role)
    return "MID" if role == "ALL" else role


def role_matches_filter(player_role: str, role_filter: str | None) -> bool:
    if not role_filter or role_filter.upper() == "ALL":
        return True
    return player_role.upper() == role_filter.upper()


def lane_opponent_id(participant_id: int) -> int:
    """In match-v5 the ids 1-5 and 6-10 are ordered by position."""
    return participant_id + 5 if participant_id <= 5 else participant_id - 5
