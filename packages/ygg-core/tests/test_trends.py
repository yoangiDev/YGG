from datetime import UTC, datetime

from factories import blank_stats
from ygg_core.domain.participant import TIMELINE_VERSION
from ygg_core.metrics.benchmarks import average, target
from ygg_core.metrics.trends import SnapshotTrends, TrendSeries, compute_trends


def game(day: int, **overrides):
    values = {"timeline_enriched": True, "timeline_version": TIMELINE_VERSION, **overrides}
    return blank_stats(match_id=f"EUW1_{day}", creation_time=datetime(2026, 5, day, tzinfo=UTC), **values)


def series(trends: SnapshotTrends, group: str, key: str) -> TrendSeries:
    metrics = next(g for g in trends.groups if g.key == group).metrics
    return next(m for m in metrics if m.key == key)


def test_each_role_has_its_own_trends():
    keys = {role: [g.key for g in compute_trends([game(1)], role).groups] for role in ("TOP", "JUNGLE", "MID", "ADC", "SUPPORT")}
    assert keys == {
        "TOP": ["solo_kills", "vision", "map_contribution", "deaths"],
        "JUNGLE": ["objective_setup", "objective_vision", "ganks", "deaths"],
        "MID": ["gold", "damage", "deaths", "vs"],
        "ADC": ["gold", "damage", "deaths", "vs"],
        "SUPPORT": ["kill_participation", "roams", "vision", "deaths"],
    }


def test_games_are_chronological():
    trends = compute_trends([game(3, deaths=4), game(1, deaths=2)], "MID")
    assert [(g.game_num, g.match_id) for g in trends.games] == [(1, "EUW1_1"), (2, "EUW1_3")]
    deaths = series(trends, "deaths", "deaths")
    assert (deaths.values, deaths.moving_average) == ([2, 4], [2.0, 3.0])


def test_ratio_trends_add_the_games_of_the_window():
    trends = compute_trends([game(1, lane_visits=[{"takedowns": 1}]), game(2, lane_visits=[{}, {}, {"deaths": 1}])], "JUNGLE")
    success = series(trends, "ganks", "gank_success")
    assert success.values == [100.0, 0.0]
    assert success.moving_average == [100.0, 25.0]  # 1 of 4 ganks, not the mean of 100 and 0


def test_role_metrics_are_missing_in_games_from_an_older_version():
    trends = compute_trends([game(1, turret_plates=3), game(2, turret_plates=5, timeline_version=1)], "TOP")
    plates = series(trends, "solo_kills", "turret_plates")
    assert (plates.values, plates.moving_average) == ([3.0, None], [3.0, 3.0])
    assert plates.challenger is None


def test_timeline_metrics_are_missing_without_timeline():
    trends = compute_trends([game(1, gold_diff_14=300), game(2, timeline_enriched=False)], "MID")
    gold = series(trends, "vs", "gold_diff_14")
    assert (gold.values, gold.moving_average) == ([300.0, None], [300.0, 300.0])
    assert (gold.challenger, gold.signed) == (0.0, True)


def test_deaths_are_split_at_minute_14():
    trends = compute_trends([game(1, deaths=3, death_events=[{"time": 100}, {"time": 839}, {"time": 840}])], "TOP")
    keys = ("deaths", "laning_deaths", "mid_late_deaths")
    assert [series(trends, "deaths", key).values for key in keys] == [[3], [2.0], [1.0]]


def test_references_follow_the_role():
    # The dotted line is the measured Challenger mean in the role, not the target (which is above it).
    mid = compute_trends([game(1)], "MID")
    assert series(mid, "gold", "cs_per_min").challenger == round(average("CHALLENGER", "MID", "cs_per_min"), 2)
    assert series(mid, "deaths", "laning_deaths").challenger == round(average("CHALLENGER", "MID", "laning_deaths"), 2)
    support = compute_trends([game(1)], "SUPPORT")
    assert series(support, "vision", "vision_per_min").challenger == round(
        average("CHALLENGER", "SUPPORT", "vision_per_min"), 2
    )
    assert series(mid, "gold", "cs_per_min").challenger < target("CHALLENGER", "MID", "cs_per_min")
