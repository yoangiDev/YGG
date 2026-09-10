"""Unit tests for Season 26 Role Quest timeline parsing."""

import json
from datetime import datetime, timezone
from pathlib import Path

from app.db.models.match import Match
from app.service.role_quest_parser import (
    apply_role_quest_stats,
    extract_quest_completion_time,
    lane_opponent_id,
    normalize_role,
    resolve_role_bound_item,
)

FIXTURES = Path(__file__).parent / "fixtures" / "role_quest"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class TestNormalizeRole:
    def test_riot_aliases(self):
        assert normalize_role("MIDDLE") == "MID"
        assert normalize_role("BOTTOM") == "ADC"
        assert normalize_role("UTILITY") == "SUPPORT"


class TestLaneOpponentId:
    def test_blue_side(self):
        assert lane_opponent_id(1) == 6

    def test_red_side(self):
        assert lane_opponent_id(6) == 1


class TestExtractQuestCompletionTime:
    def test_top_destroy_item(self):
        timeline = _load_fixture("top_quest_destroy.json")
        assert extract_quest_completion_time(timeline, 1, "TOP") == 684

    def test_adc_role_bound_purchase(self):
        timeline = _load_fixture("adc_quest_purchase.json")
        assert extract_quest_completion_time(
            timeline, 5, "ADC", role_bound_item=3020
        ) == 720

    def test_mid_destroy_item(self):
        timeline = {
            "info": {
                "frames": [
                    {
                        "events": [
                            {
                                "type": "ITEM_DESTROYED",
                                "itemId": 1201,
                                "participantId": 3,
                                "timestamp": 600000,
                            }
                        ]
                    }
                ]
            }
        }
        assert extract_quest_completion_time(timeline, 3, "MID") == 600

    def test_no_signal_returns_none(self):
        timeline = {"info": {"frames": [{"events": []}]}}
        assert extract_quest_completion_time(timeline, 1, "TOP") is None


class TestResolveRoleBoundItem:
    def test_uses_stored_value(self):
        assert resolve_role_bound_item(1209, "JUNGLE", datetime(2026, 5, 1, tzinfo=timezone.utc)) == 1209

    def test_jungle_fallback(self):
        from datetime import timezone
        assert resolve_role_bound_item(0, "JUNGLE", datetime(2026, 5, 1, tzinfo=timezone.utc)) == 1209

    def test_adc_from_build(self):
        from datetime import timezone
        assert resolve_role_bound_item(
            0, "ADC", datetime(2026, 5, 1, tzinfo=timezone.utc), [3031, 3008, 0, 0, 0, 0]
        ) == 3008

    def test_pre_s26_returns_zero(self):
        assert resolve_role_bound_item(0, "JUNGLE", datetime(2025, 12, 1, tzinfo=timezone.utc)) == 0


class TestApplyRoleQuestStats:
    def _participants(self) -> list[dict]:
        return [
            {
                "participantId": 1,
                "teamPosition": "TOP",
                "roleBoundItem": 1220,
            },
            {
                "participantId": 6,
                "teamPosition": "TOP",
                "roleBoundItem": 1220,
            },
        ]

    def test_populates_player_and_enemy_times(self):
        match = Match()
        timeline = {
            "info": {
                "frames": [
                    {
                        "events": [
                            {
                                "type": "ITEM_DESTROYED",
                                "itemId": 1200,
                                "participantId": 1,
                                "timestamp": 600000,
                            },
                            {
                                "type": "ITEM_DESTROYED",
                                "itemId": 1200,
                                "participantId": 6,
                                "timestamp": 720000,
                            },
                        ]
                    }
                ]
            }
        }
        apply_role_quest_stats(
            match,
            timeline,
            1,
            player_role="TOP",
            participants=self._participants(),
        )
        assert match.quest_completed is True
        assert match.quest_completion_time == 600
        assert match.enemy_quest_completion_time == 720
        assert match.quest_completion_time_diff == -120

    def test_pre_s26_no_role_bound_item(self):
        match = Match()
        apply_role_quest_stats(
            match,
            {"info": {"frames": []}},
            1,
            player_role="TOP",
            participants=[{"participantId": 1, "teamPosition": "TOP", "roleBoundItem": 0}],
        )
        assert match.quest_completed is False
        assert match.quest_completion_time is None
        assert match.enemy_quest_completion_time is None
        assert match.quest_completion_time_diff is None
