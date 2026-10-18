from factories import blank_stats
from ygg_core.domain.participant import TIMELINE_VERSION
from ygg_core.metrics import role_metrics as rm


def with_timeline(**overrides):
    return blank_stats(timeline_enriched=True, timeline_version=TIMELINE_VERSION, **overrides)


def test_what_counts_as_a_successful_visit():
    assert rm.visit_successful({"takedowns": 1, "deaths": 0})
    assert not rm.visit_successful({"takedowns": 1, "deaths": 2, "structures": 1})
    assert rm.visit_successful({"structures": 1})
    assert rm.visit_successful({"swing": rm.SWING_SUCCESS})
    assert not rm.visit_successful({"swing": rm.SWING_SUCCESS - 1})
    assert rm.visit_successful({"takedowns": 1, "deaths": 1, "swing": 400})


def test_ratios_add_the_games_before_dividing():
    one_of_one = with_timeline(lane_visits=[{"takedowns": 1}])
    none_of_three = with_timeline(lane_visits=[{}, {}, {"deaths": 1}])
    assert rm.visit_success_rate([one_of_one]) == 100
    assert rm.visit_success_rate([one_of_one, none_of_three]) == 25
    assert rm.visit_success_rate([with_timeline()]) is None  # with no visits there is no ratio


def test_games_from_an_older_timeline_version_have_no_role_metrics():
    old = blank_stats(timeline_enriched=True, lane_visits=[{"takedowns": 1}])
    assert not rm.has_role_timeline(old)
    assert rm.visit_success_rate([old]) is None


def test_early_deaths_by_place():
    game = with_timeline(
        death_events=[
            {"time": 300, "x": 1500, "y": 9000},  # top
            {"time": 400, "x": 4000, "y": 7000},  # jungle
            {"time": 500, "x": 1000, "y": 1000},  # blue base
            {"time": 900, "x": 1500, "y": 9000},  # after minute 14
        ]
    )
    assert rm.early_deaths_in_lanes(game) == 1
    assert rm.early_deaths_away_from_lane(game, "SUPPORT") == 2  # top and jungle
    assert rm.early_deaths_away_from_lane(game, "TOP") == 1  # only the jungler's
