from dataclasses import replace

import pytest
from ygg_core.domain.match_summary import ParticipantSummary
from ygg_core.domain.roles import DASHBOARD_ROLES
from ygg_core.metrics.benchmarks import CHALLENGER_BENCHMARKS, METRICS
from ygg_core.metrics.match_score import (
    MIN_MINUTES,
    REFERENCE_MINUTES,
    SCORE_WEIGHTS,
    gold_shares,
    metric_score,
    metric_values,
    performance_score,
    rank_participants,
)


def centre(role: str, metric: str) -> float:
    low, high = CHALLENGER_BENCHMARKS[role][metric]
    return (low + high) / 2


def centre_gold_share(role: str) -> float:
    """El % de oro con el que la eficiencia cae justo en el centro de su rango."""
    return centre(role, "damage_share") / centre(role, "efficiency")


def participant(role: str, *, win: bool = True, gold: int = 10_000, **overrides: float) -> ParticipantSummary:
    """Un jugador justo en el centro de cada rango Challenger de su rol (salvo lo que se cambie)."""
    values = {metric: centre(role, metric) for metric in METRICS} | overrides
    return ParticipantSummary(
        puuid=f"{role}-{win}-{sorted(overrides.items())}",
        game_name="Player",
        tag_line="TEST",
        champion="Ahri",
        champion_level=16,
        team_id=100 if win else 200,
        role=role,
        win=win,
        kills=values["kills"],
        deaths=values["deaths"],
        assists=values["assists"],
        kda=(values["kills"] + values["assists"]) / max(values["deaths"], 1),
        kill_participation=values["kill_participation"],
        cs=0,
        cs_per_min=values["cs_per_min"],
        gold=gold,
        damage=0,
        damage_per_min=values["damage_per_min"],
        damage_share=values["damage_share"],
        damage_taken=0,
        vision_score=0,
        vision_per_min=0.0,
        wards_placed=0,
        control_wards=0,
        items=(0, 0, 0, 0, 0, 0),
        trinket=0,
        spells=(4, 14),
        keystone=0,
        secondary_tree=0,
    )


@pytest.mark.parametrize("role", DASHBOARD_ROLES)
def test_references_and_weights_cover_every_metric(role):
    assert set(CHALLENGER_BENCHMARKS[role]) == set(METRICS) == set(SCORE_WEIGHTS[role])
    assert all(low < high for low, high in CHALLENGER_BENCHMARKS[role].values())
    assert sum(SCORE_WEIGHTS[role].values()) == pytest.approx(1)


@pytest.mark.parametrize("role", DASHBOARD_ROLES)
def test_deaths_weigh_more_than_anything_else(role):
    weights = SCORE_WEIGHTS[role]
    assert all(weights["deaths"] > weight for metric, weight in weights.items() if metric != "deaths")


def test_metric_score_is_70_at_the_centre_and_moves_15_points_per_range():
    kills = (4.5, 5.5)
    assert metric_score("kills", 5.0, kills) == 70
    assert metric_score("kills", 5.5, kills) == pytest.approx(77.5)
    assert metric_score("kills", 6.0, kills) == pytest.approx(85)
    assert metric_score("kills", 3.0, kills) == pytest.approx(40)
    assert (metric_score("kills", 20, kills), metric_score("kills", 0, kills)) == (100, 0)


def test_fewer_deaths_score_higher():
    deaths = (4.0, 4.8)
    assert metric_score("deaths", 4.0, deaths) == pytest.approx(77.5)
    assert metric_score("deaths", 4.8, deaths) == pytest.approx(62.5)


@pytest.mark.parametrize("role", DASHBOARD_ROLES)
def test_a_challenger_average_game_scores_70(role):
    assert performance_score(participant(role), REFERENCE_MINUTES, centre_gold_share(role)) == pytest.approx(70)


def test_efficiency_is_damage_share_over_gold_share():
    jungler = participant("JUNGLE", damage_share=18)
    assert metric_values(jungler, REFERENCE_MINUTES, gold_share=20)["efficiency"] == pytest.approx(0.9)
    team = [participant("TOP", gold=12_000), participant("SUPPORT", gold=8_000), participant("MID", win=False)]
    assert gold_shares(team) == [60, 40, 100]


def test_each_role_is_judged_against_its_own_references():
    support = participant("SUPPORT")
    share = centre_gold_share("SUPPORT")
    assert performance_score(replace(support, role="MID"), REFERENCE_MINUTES, share) < 40


def test_unknown_role_is_judged_as_mid():
    mid = participant("MID")
    assert performance_score(replace(mid, role="UNKNOWN"), 31, 21) == performance_score(mid, 31, 21)


def test_kills_deaths_and_assists_are_scaled_to_a_28_minute_game():
    base = participant("ADC")
    share = centre_gold_share("ADC")
    doubled = replace(base, kills=base.kills * 2, deaths=base.deaths * 2, assists=base.assists * 2)
    assert performance_score(doubled, 2 * REFERENCE_MINUTES, share) == pytest.approx(70)
    assert performance_score(doubled, REFERENCE_MINUTES, share) < 70


def test_very_short_games_are_scaled_as_15_minutes():
    top = participant("TOP")
    assert metric_values(top, 4, 22) == metric_values(top, MIN_MINUTES, 22)


def test_ranks_by_score_with_mvp_for_the_best_winner_and_ace_for_the_best_loser():
    # Mismo rol y mismo oro: solo cambian kills, muertes o asistencias.
    players = [
        participant("MID"),
        participant("MID", deaths=12),
        participant("MID", win=False, kills=15),
        participant("MID", win=False, assists=8),
    ]
    ranked = rank_participants(players, REFERENCE_MINUTES)

    assert [p.placement for p in ranked] == [3, 4, 1, 2]
    assert [p.badge for p in ranked] == ["MVP", None, "ACE", None]
    assert all(0 <= p.score <= 100 for p in ranked)
