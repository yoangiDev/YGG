from ygg_core.metrics.aggregates import (
    deaths_by_phase,
    dragon_setups_summary,
    moving_average,
    normalized_death_events,
    normalized_ward_events,
    trend_window_size,
)


def test_deaths_by_phase_boundaries():
    events = [{"time": t} for t in (100, 479, 480, 800, 840, 1200)]
    assert deaths_by_phase(events) == {"early_deaths": 2, "mid_deaths": 2, "late_deaths": 2}
    assert deaths_by_phase(None) == {"early_deaths": 0, "mid_deaths": 0, "late_deaths": 0}


def test_map_coordinates_are_normalized_for_screen():
    deaths = normalized_death_events([
        {"time": 100, "x": 0, "y": 0},
        {"time": 200, "x": 15000, "y": 15000},
        {"time": 300, "x": 7500, "y": 7500},
    ])
    assert [(d["norm_x"], d["norm_y"]) for d in deaths] == [(0.0, 1.0), (1.0, 0.0), (0.5, 0.5)]
    assert deaths[0]["assistingParticipantIds"] == []

    [ward] = normalized_ward_events([{"time": 50, "x": 3000, "y": 12000, "type": "yellow"}])
    assert (ward["norm_x"], ward["norm_y"], ward["type"]) == (0.2, 0.2, "yellow")


def test_dragon_setups_summary():
    setups = [
        {"team_dragon": True, "in_prep_zone": True, "at_kill_zone": True, "secured_by_jg": True},
        {"team_dragon": True, "in_prep_zone": False, "at_kill_zone": False, "secured_by_jg": False},
        {"team_dragon": False, "in_prep_zone": True, "at_kill_zone": True, "secured_by_jg": False},
    ]
    assert dragon_setups_summary(setups) == {
        "team_dragons": 2,
        "setup_rate": 50.0,
        "presence_at_kill_rate": 50.0,
        "secure_rate": 50.0,
    }
    assert dragon_setups_summary([])["setup_rate"] is None


def test_moving_average_window():
    assert trend_window_size(2) == 3
    assert trend_window_size(40) == 6
    assert trend_window_size(200) == 10
    assert moving_average([2.0, 4.0, 6.0, 8.0], window=3) == [2.0, 3.0, 4.0, 6.0]
