"""Roles: traducción desde Riot y reglas de filtrado."""

from __future__ import annotations

# teamPosition de match-v5 → rol interno.
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
    """Acepta tanto nombres de Riot (MIDDLE, UTILITY) como internos (MID, SUPPORT)."""
    if not role:
        return "UNKNOWN"
    return _ROLE_ALIASES.get(role.upper(), role.upper())


def role_filter_for_player(player_role: str | None) -> str:
    """Rol con el que se filtran las partidas de un jugador registrado."""
    if not player_role:
        return "ALL"
    role = player_role.upper()
    return "ADC" if role == "BOTTOM" else role


def dashboard_role(player_role: str | None) -> str:
    """Rol con el que se calcula el dashboard. Sin rol fijo se usa MID."""
    role = role_filter_for_player(player_role)
    return "MID" if role == "ALL" else role


def role_matches_filter(player_role: str, role_filter: str | None) -> bool:
    if not role_filter or role_filter.upper() == "ALL":
        return True
    return player_role.upper() == role_filter.upper()


def lane_opponent_id(participant_id: int) -> int:
    """En match-v5 los ids 1-5 y 6-10 están ordenados por posición."""
    return participant_id + 5 if participant_id <= 5 else participant_id - 5
