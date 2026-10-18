"""The history grade with timeline (ygg_core.metrics.timeline_grade)."""

from ygg_core.metrics.timeline_grade import grade_from_total, model, respawn_seconds


def test_the_model_has_the_five_roles_with_one_weight_per_variable():
    m = model()
    assert set(m["positions"]) == {"TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"}
    for role in m["positions"].values():
        assert len(role["weight"]) == len(role["mu"]) == len(role["sd"]) == len(m["variables"])


def test_respawn_time_grows_with_level_and_after_minute_15():
    assert respawn_seconds(1, 5) == 10 and respawn_seconds(18, 5) == 52.5
    assert respawn_seconds(11, 20) > respawn_seconds(11, 10) and respawn_seconds(11, 40) > respawn_seconds(11, 20)


def test_the_grade_uses_the_analysis_scale_and_never_leaves_1_100():
    cuts = model()["positions"]["BOTTOM"]["cuts"]
    assert grade_from_total(cuts[2], "BOTTOM") == 62 or grade_from_total(cuts[2], "BOTTOM") == 63  # the Challenger median scores 62.5
    assert grade_from_total(-999, "BOTTOM") == 1 and grade_from_total(999, "BOTTOM") == 100
