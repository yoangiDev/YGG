"""Season 26 Role Quest times."""

from factories import blank_stats, load_json
from ygg_core.domain.roles import lane_opponent_id, normalize_role
from ygg_core.timeline.quests import (
    apply_role_quest_stats,
    extract_quest_completion_time,
    quest_reward_item,
)


def _destroy(item_id, participant_id, ts):
    return {"type": "ITEM_DESTROYED", "itemId": item_id, "participantId": participant_id, "timestamp": ts}


def test_riot_role_aliases():
    assert normalize_role("MIDDLE") == "MID"
    assert normalize_role("BOTTOM") == "ADC"
    assert normalize_role("UTILITY") == "SUPPORT"


def test_quest_reward_only_once_the_quest_is_completed():
    # Rewards: the ADC's boots, the top's Unleashed Teleport, the support's control wards.
    assert [quest_reward_item(item) for item in (3006, 1220, 2055)] == [3006, 1220, 2055]
    # In-progress quest markers and matches without a quest.
    assert [quest_reward_item(item) for item in (1202, 1200, 1222, 0, None)] == [0, 0, 0, 0, 0]


def test_lane_opponent_id():
    assert lane_opponent_id(1) == 6
    assert lane_opponent_id(6) == 1


class TestExtractQuestCompletionTime:
    def test_top_destroy_item(self):
        timeline = load_json("role_quest/top_quest_destroy.json")
        assert extract_quest_completion_time(timeline, 1, "TOP") == 684

    def test_adc_role_bound_purchase(self):
        timeline = load_json("role_quest/adc_quest_purchase.json")
        assert extract_quest_completion_time(timeline, 5, "ADC", role_bound_item=3020) == 720

    def test_mid_destroy_item(self):
        timeline = {"info": {"frames": [{"events": [_destroy(1201, 3, 600_000)]}]}}
        assert extract_quest_completion_time(timeline, 3, "MID") == 600

    def test_no_signal_returns_none(self):
        assert extract_quest_completion_time({"info": {"frames": [{"events": []}]}}, 1, "TOP") is None


TOP_LANERS = [
    {"participantId": 1, "teamPosition": "TOP", "roleBoundItem": 1220},
    {"participantId": 6, "teamPosition": "TOP", "roleBoundItem": 1220},
]


class TestApplyRoleQuestStats:
    def test_populates_player_and_enemy_times(self):
        stats = blank_stats()
        timeline = {"info": {"frames": [{"events": [_destroy(1200, 1, 600_000), _destroy(1200, 6, 720_000)]}]}}
        apply_role_quest_stats(stats, timeline, 1, player_role="TOP", participants=TOP_LANERS)
        assert stats.quest_completed is True
        assert (stats.quest_completion_time, stats.enemy_quest_completion_time) == (600, 720)
        assert stats.quest_completion_time_diff == -120

    def test_pre_s26_without_role_bound_item(self):
        stats = blank_stats(quest_completed=True, quest_completion_time=1)
        apply_role_quest_stats(
            stats,
            {"info": {"frames": []}},
            1,
            player_role="TOP",
            participants=[{"participantId": 1, "teamPosition": "TOP", "roleBoundItem": 0}],
        )
        assert stats.quest_completed is False
        assert stats.quest_completion_time is None
        assert stats.enemy_quest_completion_time is None
        assert stats.quest_completion_time_diff is None
