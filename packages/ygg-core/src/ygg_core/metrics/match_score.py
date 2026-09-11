"""Nota de rendimiento en una partida frente a la media Challenger del rol.

Cada métrica se compara con su rango Challenger (benchmarks.py):

    nota = 70 + 15 * (valor - centro del rango) / ancho del rango      (entre 0 y 100)

Estar en el centro del rango vale 70; cada «ancho de rango» por encima suma 15
puntos y por debajo los resta (en las muertes, al revés). Kills, muertes y
asistencias se llevan antes a una partida de 28 minutos para no premiar ni
castigar la duración. La nota final es la media de las ocho métricas con los
pesos del rol, así que 70 es jugar como un Challenger medio: es estricta a
propósito.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from typing import Final

from ygg_core.domain.match_summary import MatchSummary, ParticipantSummary
from ygg_core.metrics.benchmarks import CHALLENGER_BENCHMARKS, LOWER_IS_BETTER, PER_GAME

CHALLENGER_SCORE: Final = 70.0
POINTS_PER_RANGE: Final = 15.0
REFERENCE_MINUTES: Final = 28.0
# Una remake o un FF muy temprano no debería multiplicar las kills por cinco.
MIN_MINUTES: Final = 15.0
# Como en los dashboards: sin rol conocido se juzga como mid.
FALLBACK_ROLE: Final = "MID"

# Qué pesa en cada rol (cada fila suma 1). Las muertes son lo que más pesa en
# todos los roles; su peso sale de las tres métricas de daño, que se solapan.
SCORE_WEIGHTS: Final[dict[str, dict[str, float]]] = {
    "TOP": {
        "kills": 0.10,
        "deaths": 0.30,
        "assists": 0.05,
        "cs_per_min": 0.15,
        "damage_per_min": 0.10,
        "efficiency": 0.10,
        "kill_participation": 0.10,
        "damage_share": 0.10,
    },
    "JUNGLE": {
        "kills": 0.10,
        "deaths": 0.30,
        "assists": 0.10,
        "cs_per_min": 0.10,
        "damage_per_min": 0.05,
        "efficiency": 0.05,
        "kill_participation": 0.20,
        "damage_share": 0.10,
    },
    "MID": {
        "kills": 0.15,
        "deaths": 0.30,
        "assists": 0.05,
        "cs_per_min": 0.15,
        "damage_per_min": 0.10,
        "efficiency": 0.05,
        "kill_participation": 0.10,
        "damage_share": 0.10,
    },
    "ADC": {
        "kills": 0.15,
        "deaths": 0.30,
        "assists": 0.05,
        "cs_per_min": 0.15,
        "damage_per_min": 0.10,
        "efficiency": 0.05,
        "kill_participation": 0.10,
        "damage_share": 0.10,
    },
    "SUPPORT": {
        "kills": 0.05,
        "deaths": 0.30,
        "assists": 0.20,
        "cs_per_min": 0.05,
        "damage_per_min": 0.05,
        "efficiency": 0.05,
        "kill_participation": 0.20,
        "damage_share": 0.10,
    },
}


def scoring_role(role: str) -> str:
    return role if role in CHALLENGER_BENCHMARKS else FALLBACK_ROLE


def metric_values(participant: ParticipantSummary, minutes: float, gold_share: float) -> dict[str, float]:
    """Las métricas tal como se comparan con la tabla (totales llevados a 28 minutos).

    `gold_share` es el % del oro de su equipo (0-100), para la eficiencia.
    """
    scale = REFERENCE_MINUTES / max(minutes, MIN_MINUTES)
    values = {
        "kills": float(participant.kills),
        "deaths": float(participant.deaths),
        "assists": float(participant.assists),
        "cs_per_min": participant.cs_per_min,
        "damage_per_min": participant.damage_per_min,
        "efficiency": participant.damage_share / gold_share if gold_share > 0 else 0.0,
        "kill_participation": participant.kill_participation,
        "damage_share": participant.damage_share,
    }
    return {metric: value * scale if metric in PER_GAME else value for metric, value in values.items()}


def metric_score(metric: str, value: float, reference: tuple[float, float]) -> float:
    """Nota 0-100 de una métrica: 70 en el centro del rango Challenger, ±15 por ancho de rango."""
    low, high = reference
    distance = (value - (low + high) / 2) / (high - low)
    if metric in LOWER_IS_BETTER:
        distance = -distance
    return min(100.0, max(0.0, CHALLENGER_SCORE + POINTS_PER_RANGE * distance))


def performance_score(participant: ParticipantSummary, minutes: float, gold_share: float) -> float:
    role = scoring_role(participant.role)
    values = metric_values(participant, minutes, gold_share)
    references = CHALLENGER_BENCHMARKS[role]
    return sum(
        weight * metric_score(metric, values[metric], references[metric])
        for metric, weight in SCORE_WEIGHTS[role].items()
    )


def gold_shares(participants: Sequence[ParticipantSummary]) -> list[float]:
    """% del oro de su equipo que se llevó cada jugador (0-100)."""
    team_gold: dict[int, int] = {}
    for participant in participants:
        team_gold[participant.team_id] = team_gold.get(participant.team_id, 0) + participant.gold
    return [
        100 * participant.gold / team_gold[participant.team_id] if team_gold[participant.team_id] else 0.0
        for participant in participants
    ]


def rank_participants(participants: Sequence[ParticipantSummary], minutes: float) -> list[ParticipantSummary]:
    """Nota, posición 1-10 y las insignias MVP (mejor del equipo ganador) y ACE (mejor del perdedor)."""
    raw = [
        performance_score(participant, minutes, share)
        for participant, share in zip(participants, gold_shares(participants), strict=True)
    ]
    order = sorted(range(len(participants)), key=lambda i: (raw[i], participants[i].kda), reverse=True)
    placement = {index: position + 1 for position, index in enumerate(order)}
    mvp = next((i for i in order if participants[i].win), None)
    ace = next((i for i in order if not participants[i].win), None)
    return [
        replace(
            participant,
            score=round(raw[i]),
            placement=placement[i],
            badge="MVP" if i == mvp else "ACE" if i == ace else None,
        )
        for i, participant in enumerate(participants)
    ]


def score_match(summary: MatchSummary) -> MatchSummary:
    """Pone (o rehace, si cambió la tabla) las notas de todos los participantes."""
    ranked = rank_participants(summary.participants(), max(summary.duration / 60, 1.0))
    teams = tuple(
        replace(team, participants=tuple(p for p in ranked if p.team_id == team.team_id))
        for team in summary.teams
    )
    return replace(summary, teams=teams)
