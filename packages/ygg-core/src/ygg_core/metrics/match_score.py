"""Performance grade in a match against the role's Challenger matches.

Each metric is placed among the 143 Challenger matches measured in that role
(benchmarks.py), with their percentiles as anchors:

    Challenger percentile     10    35    50     65    90
    metric grade              40    55    62.5   70    85       (for deaths, reversed)

Between anchors it is interpolated and beyond them the slope of the last stretch is followed,
between 0 and 130: each metric can exceed 100 so that something exceptional
makes up for something bad. 70 is playing better than two out of three Challenger
matches, and a median match scores 62.5. The final grade is the mean of the
eight with the role's weights; above 85 each point counts double (nobody is
far above Challenger in all eight at once, and without that 100 would be
unreachable) and it is clamped between 0 and 100. It is strict on purpose: the aim is for the
player to improve, not to resemble the average.

Kills, deaths and assists depend on the pace of the match, so before
comparing them they are brought to that of an average Challenger match: in one with double
the kills they count half (the factor stays between 0.5 and 2).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from typing import Final

from ygg_core.domain.match_summary import MatchSummary, ParticipantSummary
from ygg_core.domain.roles import normalize_role
from ygg_core.metrics.benchmarks import (
    CHALLENGER_BENCHMARKS,
    DEFAULT_TARGET_RANK,
    LOWER_IS_BETTER,
    MATCH_KILLS,
    PER_GAME,
    Percentiles,
    reference,
)
from ygg_core.metrics.status import check_status

# Grade of the league's 10th, 35th, 50th, 65th and 90th percentiles: the 65th is the target and the 90th the excellent one.
ANCHOR_SCORES: Final = (40.0, 55.0, 62.5, 70.0, 85.0)
TARGET_SCORE: Final = 70.0
NORMAL_FROM: Final = 55.0
METRIC_CAP: Final = 130.0
# Elite zone: from 85 each point of the average counts double, so 100 is reached at 92.5.
ELITE_FROM: Final = 85.0
ELITE_STRETCH: Final = 2.0
# Kills of both teams in an average Challenger match (measured).
REFERENCE_MATCH_KILLS: Final = MATCH_KILLS["CHALLENGER"]
# Without a limit, a 10-kill match would multiply each death by five.
PACE_LIMITS: Final = (0.5, 2.0)
# As in the dashboards: with no known role it is judged as mid.
FALLBACK_ROLE: Final = "MID"

# What weighs in each role (each row sums to 1). Deaths weigh the most in
# every role; their weight comes from the three damage metrics, which overlap.
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


def pace_factor(match_kills: float) -> float:
    """By how much kills, deaths and assists are multiplied to bring them to Challenger pace."""
    low, high = PACE_LIMITS
    if match_kills <= 0:
        return high
    return min(high, max(low, REFERENCE_MATCH_KILLS / match_kills))


def metric_values(participant: ParticipantSummary, *, pace: float, gold_share: float) -> dict[str, float]:
    """The metrics as they are compared with the table.

    `pace` comes from `pace_factor` and `gold_share` is the % of their team's gold (0-100).
    """
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
    return {metric: value * pace if metric in PER_GAME else value for metric, value in values.items()}


def metric_score(metric: str, value: float, reference: Percentiles) -> float:
    """Grade 0-130 of a metric according to which percentile of the league it falls in (see the module docstring)."""
    scores = ANCHOR_SCORES[::-1] if metric in LOWER_IS_BETTER else ANCHOR_SCORES
    points = list(zip(reference, scores, strict=True))
    # The stretch it falls in; outside the anchors, the first or the last.
    i = next((i for i in range(len(points) - 1) if value <= points[i + 1][0]), len(points) - 2)
    (x0, y0), (x1, y1) = points[i], points[i + 1]
    score = y0 + (y1 - y0) * (value - x0) / (x1 - x0)
    return min(METRIC_CAP, max(0.0, score))


def metric_status(metric: str, value: float, role: str | None, rank: str = DEFAULT_TARGET_RANK) -> str:
    """excellent / good / normal / bad against the matches of rank `rank` in the role.

    With the same bands that colour the grade: 85, 70 and 55, which are the 90th, 65th (the target) and 35th percentiles of the
    rank (10th, 35th and 65th for deaths). Not the KDA: it has its fixed threshold (status.py).
    """
    if metric == "kda":
        return check_status("KDA", value)
    score = metric_score(metric, value, reference(rank, scoring_role(normalize_role(role)), metric))
    if score >= ELITE_FROM:
        return "excellent"
    if score >= TARGET_SCORE:
        return "good"
    return "normal" if score >= NORMAL_FROM else "bad"


def weighted_score(participant: ParticipantSummary, *, pace: float, gold_share: float) -> float:
    """Mean of the eight grades with the role's weights, unclamped (it can exceed 100)."""
    role = scoring_role(participant.role)
    values = metric_values(participant, pace=pace, gold_share=gold_share)
    references = CHALLENGER_BENCHMARKS[role]
    return sum(
        weight * metric_score(metric, values[metric], references[metric])
        for metric, weight in SCORE_WEIGHTS[role].items()
    )


def final_score(weighted: float) -> float:
    """The weighted mean converted into the 0-100 grade that is shown."""
    if weighted > ELITE_FROM:
        weighted = ELITE_FROM + (weighted - ELITE_FROM) * ELITE_STRETCH
    return min(100.0, weighted)


def gold_shares(participants: Sequence[ParticipantSummary]) -> list[float]:
    """% of their team's gold that each player took (0-100)."""
    team_gold: dict[int, int] = {}
    for participant in participants:
        team_gold[participant.team_id] = team_gold.get(participant.team_id, 0) + participant.gold
    return [
        100 * participant.gold / team_gold[participant.team_id] if team_gold[participant.team_id] else 0.0
        for participant in participants
    ]


def rank_participants(participants: Sequence[ParticipantSummary]) -> list[ParticipantSummary]:
    """Grade, position 1-10 and the MVP (best of the winning team) and ACE (best of the losing one) badges.

    If the match was read with the timeline, the grade is the WPA one; if not, the stats one.
    """
    grades = [participant.wpa_grade for participant in participants]
    if all(grade is not None for grade in grades):
        raw = [float(grade or 0) for grade in grades]
        scores = [int(grade or 0) for grade in grades]
    else:
        pace = pace_factor(sum(participant.kills for participant in participants))
        # Sorted by the unclamped mean so that two players with 100 don't tie.
        raw = [
            weighted_score(participant, pace=pace, gold_share=share)
            for participant, share in zip(participants, gold_shares(participants), strict=True)
        ]
        scores = [round(final_score(value)) for value in raw]
    order = sorted(range(len(participants)), key=lambda i: (raw[i], participants[i].kda), reverse=True)
    placement = {index: position + 1 for position, index in enumerate(order)}
    mvp = next((i for i in order if participants[i].win), None)
    ace = next((i for i in order if not participants[i].win), None)
    return [
        replace(
            participant,
            score=scores[i],
            placement=placement[i],
            badge="MVP" if i == mvp else "ACE" if i == ace else None,
        )
        for i, participant in enumerate(participants)
    ]


def score_match(summary: MatchSummary) -> MatchSummary:
    """Set (or redo, if the table changed) the grades of all participants."""
    ranked = rank_participants(summary.participants())
    teams = tuple(
        replace(team, participants=tuple(p for p in ranked if p.team_id == team.team_id))
        for team in summary.teams
    )
    return replace(summary, teams=teams)
