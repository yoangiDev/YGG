import pytest
from factories import blank_stats, enriched
from ygg_core.metrics.dashboard import compute_dashboard, played_champions
from ygg_core.metrics.radar import average, normalize_radar_metric
from ygg_core.metrics.status import check_status


@pytest.mark.parametrize(
    ("key", "value", "role", "expected"),
    [
        ("KDA", 5.0, "", "excellent"),
        ("KDA", 2.9, "", "bad"),
        ("Deaths", 3.0, "", "excellent"),
        ("Deaths", 5.1, "", "bad"),
        ("Gold Diff", -100, "", "normal"),
        ("CS Diff", 8, "", "good"),
        ("Vision Score/Min", 2.2, "", "excellent"),
        ("Vision Score", 54, "", "normal"),
        ("Pink Wards", 6, "SUPPORT", "good"),
        ("Pink Wards", 6, "JUNGLE", "excellent"),
        ("Pink Wards", 3, "", "good"),
        ("KP%", 61, "", "good"),
        ("Lane Deaths", 45.0, "", "good"),
        ("Early Gank Deaths", 0.36, "", "normal"),
        ("métrica desconocida", 1, "", "normal"),
    ],
)
def test_check_status(key, value, role, expected):
    assert check_status(key, value, role) == expected


class TestNormalizeRadar:
    def test_positive_metric_scales_to_ceiling(self):
        assert normalize_radar_metric("CS/Min", 5.25, "TOP") == 50.0
        assert normalize_radar_metric("CS/Min", 99, "TOP") == 100.0

    def test_death_metrics_are_inverted(self):
        assert normalize_radar_metric("Deaths/Game", 3.0, "TOP") == 50.0
        assert normalize_radar_metric("Deaths/Game", 0, "TOP") == 100.0
        assert normalize_radar_metric("Deaths/Game", 50, "TOP") == 0.0

    def test_unknown_key_and_role(self):
        assert normalize_radar_metric("Inventada", 3.0, "TOP") == 0.0
        assert normalize_radar_metric("KDA", 4.25, "COACH") == 50.0  # techo de MID


def test_average_ignores_missing_values():
    items = [blank_stats(fullclear_time=100), blank_stats(fullclear_time=None), blank_stats(fullclear_time=200)]
    assert average(items, lambda p: p.fullclear_time) == 150.0
    assert average([], lambda p: p.kills) == 0.0


class TestDashboard:
    @pytest.mark.parametrize(
        ("pid", "role", "keys"),
        [
            (1, "TOP", ["gold_diff_14", "cs_diff_14", "solo_kills", "solo_deaths", "efficiency",
                        "struct_dmg", "kda", "cs_min", "deaths", "early_gank_deaths"]),
            (2, "JUNGLE", ["gold_diff_14", "cs_diff_14", "kda", "cs_min", "deaths", "obj_control",
                           "enemy_jg", "pink_wards"]),
            (3, "MID", ["gold_diff_14", "cs_diff_14", "kda", "cs_min", "deaths", "solo_deaths",
                        "lane_deaths", "side_deaths", "roaming", "early_gank_deaths"]),
            (4, "ADC", ["gold_diff_14", "cs_diff_14", "dmg_share", "efficiency", "cs_min",
                        "lane_deaths", "side_deaths", "kda", "deaths", "early_gank_deaths"]),
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
        assert radar.player_dataset.normalized_values["KDA"] == 26.9
        assert radar.player_dataset.normalized_values["Deaths/Game"] == 33.3
        assert radar.player_dataset.normalized_values["Laning Deaths"] == 54.5
        assert radar.rank_datasets["CHALLENGER"].label == "Challenger"

    def test_jungle_objective_control(self):
        blue = {m.key: m.value for m in compute_dashboard([enriched(2)], "JUNGLE", "").role_averages}
        red = {m.key: m.value for m in compute_dashboard([enriched(7)], "JUNGLE", "").role_averages}
        assert blue["obj_control"] == 100.0
        assert red["obj_control"] == 33.3

    def test_support_radar_uses_vision(self):
        assert compute_dashboard([enriched(5)], "SUPPORT", "").radar.axes[0] == "Vision/Min"

    def test_empty_snapshot(self):
        metrics = compute_dashboard([], "MID", "Nadie")
        assert metrics.role_averages == []
        assert metrics.played_champions == []
        assert metrics.radar.axes == []


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
