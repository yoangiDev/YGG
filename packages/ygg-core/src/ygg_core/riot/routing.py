"""Región lógica → endpoints regional (routing) y de plataforma de la Riot API."""

from __future__ import annotations

DEFAULT_ROUTING: tuple[str, str] = ("europe", "euw1")

REGION_ROUTING: dict[str, tuple[str, str]] = {
    # Europa
    "europe": ("europe", "euw1"),
    "euw": ("europe", "euw1"),
    "euw1": ("europe", "euw1"),
    "eune": ("europe", "eun1"),
    "eun1": ("europe", "eun1"),
    "tr": ("europe", "tr1"),
    "tr1": ("europe", "tr1"),
    "ru": ("europe", "ru"),
    # Américas
    "americas": ("americas", "na1"),
    "na": ("americas", "na1"),
    "na1": ("americas", "na1"),
    "lan": ("americas", "la1"),
    "la1": ("americas", "la1"),
    "las": ("americas", "la2"),
    "la2": ("americas", "la2"),
    "br": ("americas", "br1"),
    "br1": ("americas", "br1"),
    # Asia
    "asia": ("asia", "kr"),
    "kr": ("asia", "kr"),
    "jp": ("asia", "jp1"),
    "jp1": ("asia", "jp1"),
    # Esports
    "esports": ("esports", "esports"),
    # SEA / Oceanía
    "sea": ("sea", "oc1"),
    "oce": ("sea", "oc1"),
    "oc1": ("sea", "oc1"),
    "ph": ("sea", "ph2"),
    "ph2": ("sea", "ph2"),
    "sg": ("sea", "sg2"),
    "sg2": ("sea", "sg2"),
    "th": ("sea", "th2"),
    "th2": ("sea", "th2"),
    "tw": ("sea", "tw2"),
    "tw2": ("sea", "tw2"),
    "vn": ("sea", "vn2"),
    "vn2": ("sea", "vn2"),
}


def resolve_region(region: str) -> tuple[str, str]:
    return REGION_ROUTING.get(region.lower(), DEFAULT_ROUTING)


def platform_from_region(region: str) -> str:
    return resolve_region(region)[1]


def region_from_match_id(match_id: str) -> str:
    """EUW1_123 → euw1."""
    return match_id.split("_", 1)[0].lower()
