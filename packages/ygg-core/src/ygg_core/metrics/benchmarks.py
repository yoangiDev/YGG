"""Referencias Challenger por rol: lo que hace de media un Challenger en una partida.

Cada métrica es un rango (bajo, alto) de medias por partida; los porcentajes van
en 0-100, como en ParticipantSummary. Cambiar esta tabla cambia la nota de todas
las partidas, también las ya guardadas: la nota se calcula al servirlas.
"""

from __future__ import annotations

from typing import Final

METRICS: Final = (
    "kills",
    "deaths",
    "assists",
    "cs_per_min",
    "damage_per_min",
    "efficiency",
    "kill_participation",
    "damage_share",
)

# En estas, menos es mejor.
LOWER_IS_BETTER: Final = frozenset({"deaths"})

# Totales de la partida (no por minuto ni porcentajes): dependen de lo que dure.
PER_GAME: Final = frozenset({"kills", "deaths", "assists"})

# "efficiency" es el Dmg/gold de la tabla: % del daño del equipo ÷ % del oro del
# equipo (como en los dashboards). Con daño bruto ÷ oro bruto salen 1.5-3.5 en
# partidas reales y todos sacarían la máxima nota.
CHALLENGER_BENCHMARKS: Final[dict[str, dict[str, tuple[float, float]]]] = {
    "TOP": {
        "kills": (4.5, 5.5),
        "deaths": (4.0, 4.8),
        "assists": (5.0, 6.5),
        "cs_per_min": (8.5, 9.5),
        "damage_per_min": (600, 700),
        "efficiency": (1.10, 1.25),
        "kill_participation": (40, 50),
        "damage_share": (21, 25),
    },
    "JUNGLE": {
        "kills": (5.0, 6.0),
        "deaths": (3.8, 4.5),
        "assists": (7.5, 9.0),
        "cs_per_min": (5.5, 6.8),
        "damage_per_min": (450, 550),
        "efficiency": (0.95, 1.10),
        "kill_participation": (60, 70),
        "damage_share": (15, 19),
    },
    "MID": {
        "kills": (5.5, 6.8),
        "deaths": (3.5, 4.2),
        "assists": (6.0, 7.5),
        "cs_per_min": (8.8, 9.8),
        "damage_per_min": (650, 800),
        "efficiency": (1.25, 1.45),
        "kill_participation": (50, 60),
        "damage_share": (25, 30),
    },
    "ADC": {
        "kills": (6.0, 7.5),
        "deaths": (3.5, 4.2),
        "assists": (5.5, 7.0),
        "cs_per_min": (9.0, 10.2),
        "damage_per_min": (650, 850),
        "efficiency": (1.20, 1.40),
        "kill_participation": (50, 60),
        "damage_share": (26, 32),
    },
    "SUPPORT": {
        "kills": (1.0, 2.0),
        "deaths": (4.2, 5.2),
        "assists": (10.0, 13.0),
        "cs_per_min": (1.2, 2.0),
        "damage_per_min": (200, 350),
        "efficiency": (0.60, 0.85),
        "kill_participation": (60, 72),
        "damage_share": (8, 12),
    },
}
