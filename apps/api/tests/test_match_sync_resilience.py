"""Tests for resilient match history / sync fallbacks."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from ygg_core.domain.participant import ParticipantStats

from app.db.models.match import Match
from app.db.models.player import Player
from app.service.match_sync import (
    backfill_role_bound_items,
    re_enrich_missing_quest_stats,
    sync_player_recent_matches,
)


def _player() -> Player:
    return Player(id=1, game_name="Test", tag_line="EUW", region="euw", puuid="puuid-1")


def _s26_match(match_id: str) -> Match:
    return Match(
        match_id=match_id,
        creation_time=datetime(2026, 5, 1, tzinfo=timezone.utc),
        champion="Ahri",
        win=True,
        duration=1800,
        timeline_enriched=True,
    )


class TestReEnrich:
    async def test_stops_after_consecutive_riot_failures(self):
        client = MagicMock()
        client.fetch_participant = AsyncMock(return_value=None)
        matches = [_s26_match("EUW1_1"), _s26_match("EUW1_2"), _s26_match("EUW1_3")]

        with patch("app.service.match_sync.riot_client", return_value=client), patch(
            "app.service.match_sync.create_secure_session"
        ):
            updated = await re_enrich_missing_quest_stats(MagicMock(), _player(), matches, limit=3)

        assert updated == 0
        assert client.fetch_participant.await_count == 2

    async def test_copies_recomputed_quest_fields_onto_row(self):
        row = _s26_match("EUW1_1")
        fresh = ParticipantStats(
            match_id="EUW1_1",
            creation_time=row.creation_time,
            duration=1800,
            role_bound_item=1209,
            quest_completed=True,
            quest_completion_time=600,
            timeline_enriched=True,
        )
        client = MagicMock()
        client.fetch_participant = AsyncMock(return_value=fresh)
        db = MagicMock()

        with patch("app.service.match_sync.riot_client", return_value=client), patch(
            "app.service.match_sync.create_secure_session"
        ):
            updated = await re_enrich_missing_quest_stats(db, _player(), [row])

        assert updated == 1
        assert (row.quest_completion_time, row.role_bound_item) == (600, 1209)
        db.commit.assert_called_once()


class TestBackfillRoleBoundItems:
    async def test_reads_reward_item_from_match_payload(self):
        row = _s26_match("EUW1_1")
        row.role_bound_item = 0
        payload = {"info": {"participants": [{"puuid": "puuid-1", "roleBoundItem": 1209}]}}
        client = MagicMock()
        client.fetch_match = AsyncMock(return_value=payload)

        with patch("app.service.match_sync.riot_client", return_value=client), patch(
            "app.service.match_sync.create_secure_session"
        ):
            updated = await backfill_role_bound_items(MagicMock(), _player(), [row])

        assert updated == 1
        assert row.role_bound_item == 1209


class TestSyncFallback:
    async def test_returns_stored_matches_when_riot_sync_fails(self):
        stored = [_s26_match("EUW1_cached")]

        with patch(
            "app.service.match_sync.get_latest_snapshot_for_player",
            return_value=MagicMock(id=99),
        ), patch(
            "app.service.match_sync.create_secure_session",
            side_effect=RuntimeError("rate limit"),
        ), patch(
            "app.service.match_sync.get_stored_player_matches",
            side_effect=[stored, stored],
        ), patch(
            "app.service.match_sync.needs_quest_reenrich",
            return_value=False,
        ), patch(
            "app.service.match_sync.backfill_role_bound_items",
            AsyncMock(return_value=0),
        ):
            result = await sync_player_recent_matches(MagicMock(), _player(), user_id=1, limit=20)

        assert len(result) == 1
        assert result[0].match_id == "EUW1_cached"
