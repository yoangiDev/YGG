import pytest
from factories import blank_stats, enriched
from ygg_core.domain.roles import DASHBOARD_ROLES
from ygg_core.metrics.benchmarks import RANKS, target
from ygg_core.metrics.benchmarks import average as rank_average
from ygg_core.metrics.dashboard import compute_dashboard, played_champions
from ygg_core.metrics.radar import (
    DEATH_AXES,
    RADAR_MAX_POSITIVE,
    average,
    build_radar_values,
    normalize_radar_metric,
    rank_benchmarks,
)
from ygg_core.metrics.status import check_status


@pytest.mark.parametrize(
    ("key", "value", "role", "expected"),
    [
        ("Solo Kills", 1.2, "", "good"),
        ("Solo Deaths", 1.3, "", "bad"),
        ("Roaming", 4.0, "", "excellent"),
        ("Early Gank Deaths", 0.36, "", "normal"),
        # The KDA, fixed threshold: grey below 3, green from 3 to 4, orange from 4.
        ("KDA", 2.9, "", "bad"),
        ("KDA", 3.5, "", "normal"),
        ("KDA", 4.0, "", "excellent"),
        # The per-league measures no longer have a fixed threshold: benchmarks.py judges them.
        ("CS/Min", 99.0, "", "normal"),
        ("unknown metric", 1, "", "normal"),
    ],
)
def test_check_status(key, value, role, expected):
    assert check_status(key, value, role) == expected


class TestNormalizeRadar:
    def test_positive_metric_scales_to_ceiling(self):
        cap = RADAR_MAX_POSITIVE["CS/Min"]["TOP"]
        assert normalize_radar_metric("CS/Min", cap / 2, "TOP") == 50.0
        assert normalize_radar_metric("CS/Min", 99, "TOP") == 100.0

    def test_deaths_are_anchored_to_the_challenger_average(self):
        deaths = rank_benchmarks("TOP")["CHALLENGER"]["Deaths/Game"]
        assert normalize_radar_metric("Deaths/Game", deaths, "TOP") == 80.0
        assert normalize_radar_metric("Deaths/Game", 2 * deaths, "TOP") == 40.0
        assert normalize_radar_metric("Deaths/Game", deaths / 2, "TOP") == normalize_radar_metric("Deaths/Game", 0, "TOP") == 100.0
        assert normalize_radar_metric("Deaths/Game", 3 * deaths, "TOP") == normalize_radar_metric("Deaths/Game", 50, "TOP") == 0.0

    def test_unknown_key_and_role(self):
        assert normalize_radar_metric("Invented", 3.0, "TOP") == 0.0
        assert normalize_radar_metric("KDA", RADAR_MAX_POSITIVE["KDA"]["MID"] / 2, "COACH") == 50.0  # MID ceiling

    @pytest.mark.parametrize("role", DASHBOARD_ROLES)
    def test_the_challenger_reference_is_balanced(self, role):
        challenger = rank_benchmarks(role)["CHALLENGER"]
        assert all(normalize_radar_metric(axis, challenger[axis], role) == 80.0 for axis in DEATH_AXES)
        positive = [axis for axis in challenger if axis not in DEATH_AXES]
        assert all(79 <= normalize_radar_metric(axis, challenger[axis], role) <= 81 for axis in positive)
        # Every death falls before or after minute 14. The before and after come from the replay events and the
        # total from the scoreboard: they have to add up.
        assert challenger["Laning Deaths"] + challenger["Post-14 Deaths"] == pytest.approx(challenger["Deaths/Game"], rel=0.03)


def test_average_ignores_missing_values():
    items = [blank_stats(fullclear_time=100), blank_stats(fullclear_time=None), blank_stats(fullclear_time=200)]
    assert average(items, lambda p: p.fullclear_time) == 150.0
    assert average([], lambda p: p.kills) == 0.0


def test_radar_kda_is_the_kda_of_the_whole_period():
    games = [blank_stats(kills=10, deaths=0, assists=10), blank_stats(kills=2, deaths=4, assists=2)]
    # The mean KDA per match would give (20 + 1) / 2 = 10.5 because of the match with no deaths.
    assert build_radar_values(games, "MID")["KDA"] == 6.0


def test_radar_dmg_gold_is_damage_share_over_gold_share():
    games = [
        blank_stats(damage_share=30, gold_share=25, damage=30_000, gold=10_000),
        blank_stats(damage_share=20, gold_share=25, damage=20_000, gold=10_000),
    ]
    # Raw damage ÷ raw gold would give 2.5.
    assert build_radar_values(games, "MID")["Dmg/Gold"] == 1.0


class TestDashboard:
    @pytest.mark.parametrize(
        ("pid", "role", "keys"),
        [
            (1, "TOP", ["gold_diff_14", "cs_diff_14", "solo_kills", "solo_deaths", "efficiency",
                        "struct_dmg", "kda", "cs_min", "deaths", "early_gank_deaths"]),
            (2, "JUNGLE", ["gold_diff_14", "cs_diff_14", "kda", "cs_min", "deaths", "obj_control",
                           "enemy_jg", "pink_wards"]),
            (3, "MID", ["gold_diff_14", "cs_diff_14", "kda", "cs_min", "deaths", "solo_deaths",
                        "laning_deaths", "post14_deaths", "roaming", "early_gank_deaths"]),
            (4, "ADC", ["gold_diff_14", "cs_diff_14", "dmg_share", "efficiency", "cs_min",
                        "laning_deaths", "post14_deaths", "kda", "deaths", "early_gank_deaths"]),
            (5, "SUPPORT", ["vision_min", "pink_wards", "kp_percent", "vision_score", "deaths", "obj_vision"]),
        ],
    )
    def test_metrics_per_role(self, pid, role, keys):
        metrics = compute_dashboard([enriched(pid)], role, f"P{pid}")
        assert metrics.active_role == role
        assert [m.key for m in metrics.role_averages] == keys
        assert all(m.status in {"excellent", "good", "normal", "bad"} for m in metrics.role_averages)

    def test_top_values(self):
        metrics = compute_dashboard([enriched(1)], "TOP", "Gnar main")
        by_key = {m.key: m for m in metrics.role_averages}
        assert by_key["gold_diff_14"].value == -350.0
        assert (by_key["early_gank_deaths"].value, by_key["early_gank_deaths"].status) == (1.0, "bad")

        radar = metrics.radar
        assert radar.axes[0] == "CS/Min"
        assert radar.player_dataset.label == "Gnar main"
        assert radar.player_dataset.values["KDA"] == 1.75
        assert radar.player_dataset.normalized_values["KDA"] == round(1.75 / RADAR_MAX_POSITIVE["KDA"]["TOP"] * 100, 1)
        # 4 deaths and 1 in lanes, against the Challenger averages: 80 at par, 0 with triple.
        challenger = rank_benchmarks("TOP")["CHALLENGER"]
        for axis, value in (("Deaths/Game", 4), ("Laning Deaths", 1)):
            expected = max(0.0, min(100.0, 80 * (3 - value / challenger[axis]) / 2))
            assert radar.player_dataset.normalized_values[axis] == round(expected, 1)
        assert radar.rank_datasets["CHALLENGER"].label == "Challenger"
        assert list(radar.rank_datasets) == list(RANKS)

    def test_cards_with_rank_data_follow_the_target_rank(self):
        challenger = {m.key: m for m in compute_dashboard([enriched(3)], "MID", "").role_averages}
        emerald = {m.key: m for m in compute_dashboard([enriched(3)], "MID", "", "EMERALD").role_averages}
        # The target is the chosen league's 65th percentile (35th for deaths): higher in Challenger.
        for key, metric in (("cs_min", "cs_per_min"), ("laning_deaths", "laning_deaths")):
            for cards, rank in ((challenger, "CHALLENGER"), (emerald, "EMERALD")):
                assert cards[key].threshold == round(target(rank, "MID", metric), 2)
        assert challenger["cs_min"].threshold > emerald["cs_min"].threshold
        # Without per-rank data or with a fixed threshold: the same with any target.
        assert challenger["roaming"].threshold == emerald["roaming"].threshold == 3.0
        assert challenger["kda"].threshold == emerald["kda"].threshold == 4.0

    def test_radar_references_are_the_measured_averages(self):
        mid = rank_benchmarks("MID")
        assert list(mid) == list(RANKS) == ["GOLD", "PLATINUM", "EMERALD", "DIAMOND", "MASTER", "GRANDMASTER", "CHALLENGER"]
        assert mid["CHALLENGER"]["CS/Min"] == round(rank_average("CHALLENGER", "MID", "cs_per_min"), 2)
        # You farm more and die less as you climb; the Challenger support sees more.
        assert mid["GOLD"]["CS/Min"] < mid["CHALLENGER"]["CS/Min"]
        assert mid["GOLD"]["Deaths/Game"] > mid["CHALLENGER"]["Deaths/Game"]
        support = rank_benchmarks("SUPPORT")
        assert support["GOLD"]["Vision/Min"] < support["CHALLENGER"]["Vision/Min"]

    def test_jungle_objective_control(self):
        blue = {m.key: m.value for m in compute_dashboard([enriched(2)], "JUNGLE", "").role_averages}
        red = {m.key: m.value for m in compute_dashboard([enriched(7)], "JUNGLE", "").role_averages}
        assert blue["obj_control"] == 100.0
        assert red["obj_control"] == 33.3

    def test_opponent_camps_are_enemy_jungle_cs_divided_by_four(self):
        by_key = {m.key: m.value for m in compute_dashboard([enriched(2)], "JUNGLE", "").role_averages}
        assert by_key["enemy_jg"] == 6.0  # 24 CS in the enemy jungle

    def test_support_radar_uses_vision(self):
        assert compute_dashboard([enriched(5)], "SUPPORT", "").radar.axes[0] == "Vision/Min"

    def test_empty_snapshot(self):
        metrics = compute_dashboard([], "MID", "Nobody")
        assert metrics.role_averages == []
        assert metrics.played_champions == []
        assert metrics.radar.axes == []


def test_played_champions_include_their_stats():
    games = [
        blank_stats(champion="Ahri", win=True, kills=10, assists=10, total_cs=240, timeline_enriched=True, gold_diff_14=400),
        blank_stats(
            champion="Ahri",
            kills=2,
            deaths=4,
            assists=2,
            total_cs=180,
            timeline_enriched=True,
            gold_diff_14=-200,
            death_events=[{"time": 300}, {"time": 500}, {"time": 1000}, {"time": 1500}],
        ),
    ]
    [ahri] = played_champions(games)
    assert (ahri.wins, ahri.losses, ahri.kda) == (1, 1, 6.0)
    assert ahri.cs_per_min == 7.0  # 420 CS in 60 minutes
    assert (ahri.gold_diff_14, ahri.laning_deaths, ahri.mid_late_deaths) == (100.0, 1.0, 1.0)


def test_played_champions_sorted_by_games():
    games = [
        blank_stats(champion="Ahri", win=True),
        blank_stats(champion="Zed", win=False),
        blank_stats(champion="Ahri", win=True),
        blank_stats(champion="Ahri", win=False),
    ]
    summary = played_champions(games)
    assert [(c.champion_name, c.games_played, c.win_rate) for c in summary] == [
        ("Ahri", 3, 66.7),
        ("Zed", 1, 0.0),
    ]
