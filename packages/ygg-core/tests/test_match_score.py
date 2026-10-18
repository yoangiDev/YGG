from dataclasses import replace
from itertools import pairwise

import pytest
from ygg_core.domain.match_summary import ParticipantSummary
from ygg_core.domain.roles import DASHBOARD_ROLES
from ygg_core.metrics.benchmarks import (
    _DATA,
    CHALLENGER_BENCHMARKS,
    LOWER_IS_BETTER,
    RANK_BENCHMARKS,
    RANKS,
    average,
    reference,
    target,
)
from ygg_core.metrics.match_score import (
    METRIC_CAP,
    REFERENCE_MATCH_KILLS,
    SCORE_WEIGHTS,
    final_score,
    gold_shares,
    metric_score,
    metric_status,
    metric_values,
    pace_factor,
    rank_participants,
    weighted_score,
)

METRICS = tuple(SCORE_WEIGHTS["MID"])


def performance_score(participant: ParticipantSummary, *, pace: float, gold_share: float) -> float:
    return final_score(weighted_score(participant, pace=pace, gold_share=gold_share))


def percentile(role: str, metric: str, which: int) -> float:
    """The 10th, 35th, 50th, 65th or 90th Challenger percentile in that role."""
    return reference("CHALLENGER", role, metric)[(10, 35, 50, 65, 90).index(which)]


def beyond_excellent(role: str, metric: str, steps: float) -> float:
    """`steps` times the stretch between the target and the excellent, beyond the excellent (15 points each)."""
    p10, p35, _, p65, p90 = reference("CHALLENGER", role, metric)
    return p10 - steps * (p35 - p10) if metric in LOWER_IS_BETTER else p90 + steps * (p90 - p65)


def gold_share_for(damage_share: float, efficiency: float) -> float:
    """The gold % with which the efficiency (damage % ÷ gold %) comes out as the one wanted."""
    return damage_share / efficiency


def target_gold_share(role: str) -> float:
    return gold_share_for(target("CHALLENGER", role, "damage_share"), target("CHALLENGER", role, "efficiency"))


def participant(role: str, *, win: bool = True, gold: int = 10_000, **overrides: float) -> ParticipantSummary:
    """A player exactly on the Challenger target in each metric of their role (except what is changed)."""
    values = {metric: target("CHALLENGER", role, metric) for metric in METRICS} | overrides
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
    assert set(METRICS) == set(SCORE_WEIGHTS[role]) <= set(CHALLENGER_BENCHMARKS[role])
    assert sum(SCORE_WEIGHTS[role].values()) == pytest.approx(1)


@pytest.mark.parametrize("role", DASHBOARD_ROLES)
def test_deaths_weigh_more_than_anything_else(role):
    weights = SCORE_WEIGHTS[role]
    assert all(weights["deaths"] > weight for metric, weight in weights.items() if metric != "deaths")


def test_metric_score_follows_the_percentiles_of_the_rank():
    percentiles = (1.0, 2.0, 3.0, 4.0, 5.0)  # 10, 35, 50, 65, 90
    assert [metric_score("kills", v, percentiles) for v in (1, 2, 3, 4, 5)] == [40, 55, 62.5, 70, 85]
    assert metric_score("kills", 4.5, percentiles) == pytest.approx(77.5)
    # Outside the anchors it follows the slope of the last stretch, down to 0 and 130.
    assert (metric_score("kills", 6, percentiles), metric_score("kills", 0, percentiles)) == (100, 25)
    assert (metric_score("kills", 20, percentiles), metric_score("kills", -9, percentiles)) == (METRIC_CAP, 0)
    # For deaths, the other way round: the 10th percentile is the excellent.
    assert [metric_score("deaths", v, percentiles) for v in (1, 2, 3, 4, 5)] == [85, 70, 62.5, 55, 40]


def test_the_seven_measured_tiers_go_from_gold_to_challenger():
    assert RANKS == ("GOLD", "PLATINUM", "EMERALD", "DIAMOND", "MASTER", "GRANDMASTER", "CHALLENGER")
    assert all(_DATA["games"][rank] == 143 for rank in RANKS)


@pytest.mark.parametrize("rank", RANK_BENCHMARKS)
def test_every_rank_has_the_same_metrics_for_every_role(rank):
    assert set(RANK_BENCHMARKS[rank]) == set(CHALLENGER_BENCHMARKS)
    for role, table in RANK_BENCHMARKS[rank].items():
        assert set(table) == set(CHALLENGER_BENCHMARKS[role])
        # Strictly increasing: between two equal anchors the grade would not be defined.
        assert all(all(a < b for a, b in pairwise(p)) for p in table.values())


@pytest.mark.parametrize("metric", ["cs_per_min", "damage_per_min", "deaths"])
def test_the_target_beats_two_of_three_games_of_the_rank(metric):
    _, p35, p50, p65, _ = reference("CHALLENGER", "MID", metric)
    if metric in LOWER_IS_BETTER:
        assert target("CHALLENGER", "MID", metric) == p35 < p50  # fewer deaths than the typical match
    else:
        assert target("CHALLENGER", "MID", metric) == p65 > p50  # better than the typical match


def test_the_average_of_the_rank_is_normal_not_good():
    # Playing like the league average is normal: to be good you have to be above it.
    for rank in ("GOLD", "CHALLENGER"):
        for role in DASHBOARD_ROLES:
            assert metric_status("cs_per_min", average(rank, role, "cs_per_min"), role, rank) == "normal"
            assert metric_status("deaths", average(rank, role, "deaths"), role, rank) == "normal"


def test_status_against_another_rank():
    # The average of an Emerald mid is normal in Emerald and weak in Challenger.
    emerald = average("EMERALD", "MID", "cs_per_min")
    assert metric_status("cs_per_min", emerald, "MID", "EMERALD") == "normal"
    assert metric_status("cs_per_min", emerald, "MID") == "bad"


def test_status_bands_are_percentiles_of_the_rank():
    p10, p35, _, p65, p90 = reference("CHALLENGER", "MID", "cs_per_min")
    cs = [p90 + 0.01, p65 + 0.01, p35 + 0.01, p35 - 0.01]
    assert [metric_status("cs_per_min", value, "MID") for value in cs] == ["excellent", "good", "normal", "bad"]
    p10, p35, _, p65, p90 = reference("CHALLENGER", "MID", "deaths")
    deaths = [p10 - 0.01, p35 - 0.01, p65 - 0.01, p65 + 0.01]
    assert [metric_status("deaths", value, "MID") for value in deaths] == ["excellent", "good", "normal", "bad"]
    # BOTTOM is ADC and with no role it is judged as mid.
    adc = percentile("ADC", "cs_per_min", 65) + 0.01
    assert metric_status("cs_per_min", adc, "BOTTOM") == metric_status("cs_per_min", adc, "ADC") == "good"
    mid = percentile("MID", "cs_per_min", 65) + 0.01
    assert metric_status("cs_per_min", mid, None) == metric_status("cs_per_min", mid, "MID") == "good"


@pytest.mark.parametrize("role", DASHBOARD_ROLES)
def test_the_kda_has_its_own_fixed_bands_in_every_role_and_rank(role):
    # Grey below 3, green from 3 to 4 and orange from 4; no blue.
    kdas = (2.99, 3.0, 3.99, 4.0, 12.0)
    expected = ["bad", "normal", "normal", "excellent", "excellent"]
    assert [metric_status("kda", kda, role) for kda in kdas] == expected
    assert [metric_status("kda", kda, role, "GOLD") for kda in kdas] == expected


def test_fewer_deaths_score_higher():
    deaths = reference("CHALLENGER", "TOP", "deaths")
    assert metric_score("deaths", deaths[0], deaths) == 85
    assert metric_score("deaths", deaths[3], deaths) == 55


@pytest.mark.parametrize("role", DASHBOARD_ROLES)
def test_a_game_on_the_challenger_target_scores_70(role):
    assert performance_score(participant(role), pace=1, gold_share=target_gold_share(role)) == pytest.approx(70)


@pytest.mark.parametrize("role", DASHBOARD_ROLES)
def test_a_median_challenger_game_scores_62_5(role):
    """70 is the target, above the typical: the median Challenger match stays at 62.5."""
    median = {metric: percentile(role, metric, 50) for metric in METRICS}
    share = gold_share_for(median["damage_share"], median["efficiency"])
    assert performance_score(participant(role, **median), pace=1, gold_share=share) == pytest.approx(62.5)


def test_the_final_score_never_goes_above_100():
    monster = participant(
        "ADC", kills=30, deaths=0, assists=30, cs_per_min=15, damage_per_min=2000, kill_participation=100, damage_share=60
    )
    assert performance_score(monster, pace=1, gold_share=10) == 100


def test_only_the_elite_zone_is_stretched():
    assert (final_score(40), final_score(70), final_score(85)) == (40, 70, 85)
    assert final_score(90) == 95
    assert (final_score(92.5), final_score(110)) == (100, 100)


def test_a_dominant_game_reaches_100_and_a_very_good_one_does_not():
    share = target_gold_share("MID")
    skill = [metric for metric in METRICS if metric != "efficiency"]  # the efficiency comes from the damage and gold %
    stomp = participant("MID", **{metric: beyond_excellent("MID", metric, 2) for metric in skill})
    very_good = participant("MID", **{metric: beyond_excellent("MID", metric, 0.3) for metric in skill})
    assert performance_score(stomp, pace=1, gold_share=share) == 100
    assert 85 < performance_score(very_good, pace=1, gold_share=share) < 95


def test_an_outstanding_stat_makes_up_for_a_weak_one():
    p10, p35, *_ = reference("CHALLENGER", "MID", "cs_per_min")
    weak_cs = participant("MID", cs_per_min=p10 - (p35 - p10))  # 25 en CS/min: -45
    carry = replace(weak_cs, kills=beyond_excellent("MID", "kills", 2))  # 115 in kills: +45, impossible with a cap of 100
    share = target_gold_share("MID")
    assert performance_score(weak_cs, pace=1, gold_share=share) < 70
    assert performance_score(carry, pace=1, gold_share=share) == pytest.approx(70)


def test_efficiency_is_damage_share_over_gold_share():
    jungler = participant("JUNGLE", damage_share=18)
    assert metric_values(jungler, pace=1, gold_share=20)["efficiency"] == pytest.approx(0.9)
    team = [participant("TOP", gold=12_000), participant("SUPPORT", gold=8_000), participant("MID", win=False)]
    assert gold_shares(team) == [60, 40, 100]


def test_each_role_is_judged_against_its_own_references():
    support = participant("SUPPORT")
    share = target_gold_share("SUPPORT")
    assert performance_score(support, pace=1, gold_share=share) == pytest.approx(70)
    assert performance_score(replace(support, role="MID"), pace=1, gold_share=share) < 55


def test_unknown_role_is_judged_as_mid():
    mid = participant("MID")
    assert performance_score(replace(mid, role="UNKNOWN"), pace=1.2, gold_share=21) == performance_score(
        mid, pace=1.2, gold_share=21
    )


def test_pace_follows_the_kills_of_the_match_within_limits():
    assert pace_factor(REFERENCE_MATCH_KILLS) == pytest.approx(1)
    assert pace_factor(REFERENCE_MATCH_KILLS * 1.6) == pytest.approx(1 / 1.6)
    assert (pace_factor(300), pace_factor(10), pace_factor(0)) == (0.5, 2.0, 2.0)


def test_kills_deaths_and_assists_are_brought_to_the_challenger_pace():
    base = participant("ADC")
    share = target_gold_share("ADC")
    doubled = replace(base, kills=base.kills * 2, deaths=base.deaths * 2, assists=base.assists * 2)
    # In a match with double the kills, double of everything is playing like the target.
    assert performance_score(doubled, pace=0.5, gold_share=share) == pytest.approx(70)
    assert performance_score(doubled, pace=1, gold_share=share) < 70


def test_ranks_by_score_with_mvp_for_the_best_winner_and_ace_for_the_best_loser():
    # Same role and same gold: only kills, deaths or assists change.
    assists = target("CHALLENGER", "MID", "assists")
    players = [
        participant("MID"),
        participant("MID", deaths=12),
        participant("MID", win=False, kills=15),
        participant("MID", win=False, assists=assists + 2),
    ]
    ranked = rank_participants(players)

    assert [p.placement for p in ranked] == [3, 4, 1, 2]
    assert [p.badge for p in ranked] == ["MVP", None, "ACE", None]
    assert all(0 <= p.score <= 100 for p in ranked)
