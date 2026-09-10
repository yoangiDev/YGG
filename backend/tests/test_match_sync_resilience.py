"""Tests for resilient match history / sync fallbacks."""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.db.models.match import Match
from app.db.models.player import Player
from app.service.match_sync import (
    re_enrich_missing_quest_stats,
    sync_player_recent_matches,
)


def _s26_match(match_id: str) -> Match:
    return Match(
        match_id=match_id,
        creation_time=datetime(2026, 5, 1, tzinfo=timezone.utc),
        champion="Ahri",
        win=True,
        duration=1800,
        timeline_enriched=True,
    )


class TestReEnrichRateLimit:
    @pytest.mark.asyncio
    async def test_stops_after_consecutive_riot_failures(self):
        player = Player(
            id=1,
            game_name="Test",
            tag_line="EUW",
            region="euw",
            puuid="puuid-1",
        )
        db = MagicMock()
        matches = [_s26_match("EUW1_1"), _s26_match("EUW1_2"), _s26_match("EUW1_3")]

        client = MagicMock()
        client._fetch_timeline = AsyncMock(return_value=None)
        client._fetch_single_match = AsyncMock(return_value=None)

        with patch(
            "app.service.match_sync.RiotAPIClient",
            return_value=client,
        ), patch(
            "app.service.match_sync.create_secure_session",
        ):
            updated = await re_enrich_missing_quest_stats(
                db, player, matches, limit=3
            )

        assert updated == 0
        assert client._fetch_timeline.await_count == 2


class TestSyncFallback:
    @pytest.mark.asyncio
    async def test_returns_stored_matches_when_riot_sync_fails(self):
        player = Player(
            id=1,
            game_name="Test",
            tag_line="EUW",
            region="euw",
            puuid="puuid-1",
        )
        stored = [_s26_match("EUW1_cached")]
        db = MagicMock()

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
        ):
            result = await sync_player_recent_matches(db, player, user_id=1, limit=20)

        assert len(result) == 1
        assert result[0].match_id == "EUW1_cached"
