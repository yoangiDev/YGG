"""Radar de rendimiento normalizado por rol."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from ygg_core.domain.participant import ParticipantStats

LANE_PHASE_SEC = 840  # 14 minutos

RADAR_AXES: tuple[str, ...] = (
    "CS/Min",
    "KDA",
    "Dmg Share",
    "Dmg/Gold",
    "Deaths/Game",
    "Laning Deaths",
    "Post-14 Deaths",
)
RADAR_AXES_SUPPORT: tuple[str, ...] = ("Vision/Min", *RADAR_AXES[1:])

# Techos del radar.
# Métricas positivas: techo ≈ rendimiento Challenger/pro top.
# Métricas de muertes: techo = «muy malo» (más siempre es peor).
RADAR_MAX_POSITIVE: dict[str, dict[str, float]] = {
    "CS/Min": {"TOP": 10.5, "JUNGLE": 7.5, "MID": 11.0, "ADC": 11.5, "SUPPORT": 1.8},
    "Vision/Min": {"TOP": 2.0, "JUNGLE": 1.8, "MID": 2.0, "ADC": 1.8, "SUPPORT": 3.5},
    "KDA": {"TOP": 6.5, "JUNGLE": 8.0, "MID": 8.5, "ADC": 9.0, "SUPPORT": 8.0},
    "Dmg Share": {"TOP": 31.0, "JUNGLE": 18.0, "MID": 27.0, "ADC": 45.0, "SUPPORT": 14.0},
    "Dmg/Gold": {"TOP": 1.35, "JUNGLE": 1.15, "MID": 1.35, "ADC": 1.60, "SUPPORT": 1.10},
}

RADAR_MAX_NEGATIVE: dict[str, dict[str, float]] = {
    "Deaths/Game": {"TOP": 6.0, "JUNGLE": 6.5, "MID": 6.5, "ADC": 6.0, "SUPPORT": 7.5},
    "Laning Deaths": {"TOP": 2.2, "JUNGLE": 1.8, "MID": 2.2, "ADC": 2.2, "SUPPORT": 2.8},
    "Post-14 Deaths": {"TOP": 3.8, "JUNGLE": 4.2, "MID": 3.8, "ADC": 3.5, "SUPPORT": 4.8},
}

# Medias Challenger por rol: solo se muestran como referencia; la
# normalización depende únicamente de los techos.
RADAR_RANK_BENCHMARKS: dict[str, dict[str, dict[str, float]]] = {
    "TOP": {"CHALLENGER": {"CS/Min": 7.40, "KDA": 2.78, "Dmg Share": 24.5, "Dmg/Gold": 1.12, "Deaths/Game": 3.5, "Laning Deaths": 1.1, "Post-14 Deaths": 1.6}},
    "JUNGLE": {"CHALLENGER": {"CS/Min": 7.09, "KDA": 4.47, "Dmg Share": 17.0, "Dmg/Gold": 1.05, "Deaths/Game": 4.0, "Laning Deaths": 0.7, "Post-14 Deaths": 2.2}},
    "MID": {"CHALLENGER": {"CS/Min": 7.51, "KDA": 3.54, "Dmg Share": 28.0, "Dmg/Gold": 1.18, "Deaths/Game": 3.8, "Laning Deaths": 1.0, "Post-14 Deaths": 1.9}},
    "ADC": {"CHALLENGER": {"CS/Min": 8.00, "KDA": 3.41, "Dmg Share": 32.0, "Dmg/Gold": 1.45, "Deaths/Game": 3.2, "Laning Deaths": 0.9, "Post-14 Deaths": 1.6}},
    "SUPPORT": {"CHALLENGER": {"Vision/Min": 2.87, "KDA": 4.15, "Dmg Share": 11.0, "Dmg/Gold": 0.95, "Deaths/Game": 4.5, "Laning Deaths": 1.2, "Post-14 Deaths": 2.5}},
}


def radar_axes(role: str) -> list[str]:
    return list(RADAR_AXES_SUPPORT if role == "SUPPORT" else RADAR_AXES)


def rank_benchmarks(role: str) -> dict[str, dict[str, float]]:
    return RADAR_RANK_BENCHMARKS.get(role, RADAR_RANK_BENCHMARKS["MID"])


def normalize_radar_metric(key: str, value: float, role: str) -> float:
    """Normaliza a 0-100 con techos simples.

    - Positivas: 0 → 0, techo → 100 (acotado).
    - Muertes: 0 → 100, techo → 0 (acotado; menos es mejor).
    """
    negative = key in RADAR_MAX_NEGATIVE
    caps = (RADAR_MAX_NEGATIVE if negative else RADAR_MAX_POSITIVE).get(key, {})
    cap = caps.get(role, caps.get("MID", 0.0))
    if cap <= 0:
        return 0.0
    clamped = max(0.0, min(float(value), cap))
    if negative:
        return round((1.0 - clamped / cap) * 100.0, 1)
    return round(clamped / cap * 100.0, 1)


# ── Métricas por partida ───────────────────────────────────────────────────────


def match_kda(p: ParticipantStats) -> float:
    return (p.kills + p.assists) / p.deaths if p.deaths > 0 else float(p.kills + p.assists)


def match_cs_min(p: ParticipantStats) -> float:
    return p.total_cs / (p.duration / 60) if p.duration else 0.0


def match_vision_min(p: ParticipantStats) -> float:
    return p.vision / (p.duration / 60) if p.duration else 0.0


def laning_deaths(p: ParticipantStats) -> int:
    return sum(1 for d in (p.death_events or []) if d.get("time", 0) < LANE_PHASE_SEC)


def post14_deaths(p: ParticipantStats) -> int:
    return sum(1 for d in (p.death_events or []) if d.get("time", 0) >= LANE_PHASE_SEC)


def average(
    participants: Sequence[ParticipantStats],
    extractor: Callable[[ParticipantStats], float | int | None],
) -> float:
    values = [v for v in (extractor(p) for p in participants) if v is not None]
    return round(sum(values) / len(values), 2) if values else 0.0


def build_radar_values(participants: Sequence[ParticipantStats], role: str) -> dict[str, float]:
    avg_damage = average(participants, lambda p: p.damage)
    avg_gold = average(participants, lambda p: p.gold)
    if role == "SUPPORT":
        farm_key, farm_value = "Vision/Min", average(participants, match_vision_min)
    else:
        farm_key, farm_value = "CS/Min", average(participants, match_cs_min)
    return {
        farm_key: farm_value,
        "KDA": average(participants, match_kda),
        "Dmg Share": average(participants, lambda p: p.damage_share),
        "Dmg/Gold": round(avg_damage / avg_gold, 2) if avg_gold > 0 else 0.0,
        "Deaths/Game": average(participants, lambda p: p.deaths),
        "Laning Deaths": average(participants, laning_deaths),
        "Post-14 Deaths": average(participants, post14_deaths),
    }
