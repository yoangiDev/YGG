from ygg_core.metrics.aggregates import normalized_death_events, trend_window_size


def test_map_coordinates_are_normalized_for_screen():
    deaths = normalized_death_events([
        {"time": 100, "x": 0, "y": 0},
        {"time": 200, "x": 15000, "y": 15000},
        {"time": 300, "x": 7500, "y": 7500},
    ])
    assert [(d["norm_x"], d["norm_y"]) for d in deaths] == [(0.0, 1.0), (1.0, 0.0), (0.5, 0.5)]
    assert deaths[0]["assistingParticipantIds"] == []


def test_trend_window_size():
    assert trend_window_size(2) == 3
    assert trend_window_size(40) == 6
    assert trend_window_size(200) == 10
