"""Tests for Riot API rate limiter and snapshot fetch cache."""

import asyncio
import time

import pytest

from app.service.riot_rate_limiter import RiotRateLimiter


class TestRiotRateLimiter:
    @pytest.mark.asyncio
    async def test_per_second_limit(self):
        limiter = RiotRateLimiter(per_second=3, per_two_minutes=100)
        start = time.monotonic()
        for _ in range(5):
            await limiter.acquire()
        elapsed = time.monotonic() - start
        assert elapsed >= 0.9

    @pytest.mark.asyncio
    async def test_burst_within_limits(self):
        limiter = RiotRateLimiter(per_second=10, per_two_minutes=100)
        start = time.monotonic()
        for _ in range(10):
            await limiter.acquire()
        elapsed = time.monotonic() - start
        assert elapsed < 0.5

    @pytest.mark.asyncio
    async def test_global_pause_blocks_acquire(self):
        limiter = RiotRateLimiter(per_second=100, per_two_minutes=100)
        assert await limiter.pause(0.3) is True
        assert await limiter.pause(0.2) is False
        start = time.monotonic()
        await limiter.acquire()
        assert time.monotonic() - start >= 0.25


class TestFetchMatchesCache:
    @pytest.mark.asyncio
    async def test_skips_api_for_timeline_enriched_matches(self):
        from datetime import datetime, timezone
        from unittest.mock import AsyncMock, patch

        from app.db.models.match import Match
        from app.db.models.player import Player
        from app.service.riot_client import RiotAPIClient

        player = Player(
            id=1,
            game_name="Test",
            tag_line="EUW",
            puuid="puuid-test",
            region="euw",
        )
        # Fecha fija anterior a la temporada 26: con datetime.now() el test
        # caducó el 1-1-2026, cuando la caché empezó a exigir datos de Role Quest.
        cached = Match(
            match_id="EUW1_CACHED",
            creation_time=datetime(2025, 6, 1, tzinfo=timezone.utc),
            champion="LeeSin",
            win=True,
            duration=1800,
            timeline_enriched=True,
        )

        client = RiotAPIClient()
        session = AsyncMock()

        mock_match = AsyncMock()
        mock_timeline = AsyncMock()
        mock_match.return_value = {
            "metadata": {"matchId": "EUW1_NEW"},
            "info": {
                "gameDuration": 1800,
                "gameCreation": 1_700_000_000_000,
                "participants": [
                    {
                        "puuid": "puuid-test",
                        "participantId": 1,
                        "teamId": 100,
                        "teamPosition": "JUNGLE",
                        "championName": "LeeSin",
                        "win": True,
                        "kills": 3,
                        "deaths": 2,
                        "assists": 5,
                        "visionScore": 20,
                        "totalDamageDealtToChampions": 12000,
                        "goldEarned": 11000,
                        "totalMinionsKilled": 50,
                        "neutralMinionsKilled": 100,
                        "perks": {"styles": []},
                    }
                ],
                "teams": [{"teamId": 100, "objectives": {"dragon": {"first": True}, "horde": {"kills": 2}, "riftHerald": {"kills": 1}}}],
            },
        }
        mock_timeline.return_value = {"info": {"frames": []}}

        with patch.object(
            client, "_fetch_single_match", mock_match
        ), patch.object(
            client, "_fetch_timeline", mock_timeline
        ):
            results = await client.fetch_matches(
                session=session,
                player=player,
                include_timeline=True,
                known_matches={"EUW1_CACHED": cached},
                match_ids=["EUW1_CACHED", "EUW1_NEW"],
            )

        mock_match.assert_called_once_with(session, "EUW1_NEW")
        mock_timeline.assert_called_once_with(session, "EUW1_NEW")
        assert cached in results

    @pytest.mark.asyncio
    async def test_skips_timeline_for_wrong_role(self):
        from datetime import datetime
        from unittest.mock import AsyncMock, patch

        from app.db.models.player import Player
        from app.service.riot_client import RiotAPIClient

        player = Player(
            id=1,
            game_name="Test",
            tag_line="EUW",
            puuid="puuid-test",
            region="euw",
        )
        client = RiotAPIClient()
        session = AsyncMock()

        mid_match = {
            "metadata": {"matchId": "EUW1_MID"},
            "info": {
                "gameDuration": 1800,
                "gameCreation": 1_700_000_000_000,
                "participants": [
                    {
                        "puuid": "puuid-test",
                        "participantId": 1,
                        "teamId": 100,
                        "teamPosition": "MIDDLE",
                        "championName": "Ahri",
                        "win": True,
                        "kills": 3,
                        "deaths": 2,
                        "assists": 5,
                        "visionScore": 20,
                        "totalDamageDealtToChampions": 12000,
                        "goldEarned": 11000,
                        "totalMinionsKilled": 150,
                        "neutralMinionsKilled": 0,
                        "perks": {"styles": []},
                    }
                ],
                "teams": [{"teamId": 100, "objectives": {"dragon": {"first": True}, "horde": {"kills": 0}, "riftHerald": {"kills": 0}}}],
            },
        }

        mock_match = AsyncMock(return_value=mid_match)
        mock_timeline = AsyncMock()

        with patch.object(client, "_fetch_single_match", mock_match), patch.object(
            client, "_fetch_timeline", mock_timeline
        ):
            results = await client.fetch_matches(
                session=session,
                player=player,
                role_filter="JUNGLE",
                include_timeline=True,
                match_ids=["EUW1_MID"],
            )

        mock_match.assert_called_once()
        mock_timeline.assert_not_called()
        assert results == []

    @pytest.mark.asyncio
    async def test_max_matches_limits_scheduled_fetches(self):
        from unittest.mock import AsyncMock, patch

        from app.db.models.player import Player
        from app.service.riot_client import RiotAPIClient

        player = Player(
            id=1,
            game_name="Test",
            tag_line="EUW",
            puuid="puuid-test",
            region="euw",
        )
        client = RiotAPIClient()
        session = AsyncMock()

        fake_ids = [f"EUW1_{i}" for i in range(100)]
        mock_ids_page = AsyncMock(return_value=fake_ids)
        mock_match = AsyncMock(return_value=None)

        with patch.object(client, "_fetch_match_ids_page", mock_ids_page), patch.object(
            client, "_fetch_single_match", mock_match
        ):
            await client.fetch_matches(
                session=session,
                player=player,
                max_matches=20,
                include_timeline=False,
            )

        mock_ids_page.assert_called_once()
        assert mock_ids_page.call_args.kwargs["count"] == 20
        assert mock_match.call_count == 20

    def test_enrich_with_timeline_sets_flag(self):
        from datetime import datetime

        from app.db.models.match import Match
        from app.service.riot_client import RiotAPIClient

        client = RiotAPIClient()
        match = Match(
            match_id="TEST",
            creation_time=datetime.now(),
            champion="Ahri",
            win=True,
            duration=1800,
        )
        timeline = {
            "info": {
                "frames": [
                    {
                        "timestamp": 0,
                        "participantFrames": {
                            "1": {"xp": 0, "totalGold": 0, "minionsKilled": 0, "jungleMinionsKilled": 0},
                            "6": {"xp": 0, "totalGold": 0, "minionsKilled": 0, "jungleMinionsKilled": 0},
                        },
                        "events": [],
                    }
                ]
            }
        }
        client._enrich_with_timeline(match, timeline, participant_id=1, player_role="MID")
        assert match.timeline_enriched is True

    def test_enrich_with_timeline_sets_fullclear_time_for_jungle(self):
        from datetime import datetime

        from app.db.models.match import Match
        from app.service.riot_client import RiotAPIClient

        client = RiotAPIClient()
        match = Match(
            match_id="TEST",
            creation_time=datetime.now(),
            champion="LeeSin",
            win=True,
            duration=900,
            player_role="JUNGLE",
        )
        timeline = {
            "info": {
                "frames": [
                    {
                        "timestamp": 0,
                        "participantFrames": {
                            "1": {"level": 3, "minionsKilled": 10, "jungleMinionsKilled": 5},
                        },
                        "events": [],
                    },
                    {
                        "timestamp": 60000,
                        "participantFrames": {
                            "1": {"level": 3, "minionsKilled": 12, "jungleMinionsKilled": 8},
                        },
                        "events": [],
                    },
                    {
                        "timestamp": 120000,
                        "participantFrames": {
                            "1": {"level": 4, "minionsKilled": 15, "jungleMinionsKilled": 10},
                        },
                        "events": [],
                    },
                ]
            }
        }
        client._enrich_with_timeline(match, timeline, participant_id=1, player_role="JUNGLE")

        assert match.fullclear_time == 120

    @pytest.mark.asyncio
    async def test_fetch_until_known_stops_at_stored_id(self):
        from unittest.mock import AsyncMock, patch

        from app.db.models.player import Player
        from app.service.riot_client import RiotAPIClient

        player = Player(
            id=1,
            game_name="Test",
            tag_line="EUW",
            puuid="puuid-test",
            region="euw",
        )
        client = RiotAPIClient()
        session = AsyncMock()

        ids_pages = [["EUW1_NEW1", "EUW1_OLD"], ["EUW1_NEW2"]]
        mock_ids = AsyncMock(side_effect=ids_pages)

        def _match_payload(match_id: str, role: str = "JUNGLE"):
            return {
                "metadata": {"matchId": match_id},
                "info": {
                    "gameDuration": 1800,
                    "gameCreation": 1_700_000_000_000,
                    "participants": [
                        {
                            "puuid": "puuid-test",
                            "participantId": 1,
                            "teamId": 100,
                            "teamPosition": role,
                            "championName": "LeeSin",
                            "win": True,
                            "kills": 3,
                            "deaths": 2,
                            "assists": 5,
                            "visionScore": 20,
                            "totalDamageDealtToChampions": 12000,
                            "goldEarned": 11000,
                            "totalMinionsKilled": 50,
                            "neutralMinionsKilled": 100,
                            "perks": {"styles": []},
                        }
                    ],
                    "teams": [
                        {
                            "teamId": 100,
                            "objectives": {
                                "dragon": {"first": True},
                                "horde": {"kills": 0},
                                "riftHerald": {"kills": 0},
                            },
                        }
                    ],
                },
            }

        mock_match = AsyncMock(
            side_effect=lambda _s, mid: _match_payload(mid)
        )

        with patch.object(client, "_fetch_match_ids_page", mock_ids), patch.object(
            client, "_fetch_single_match", mock_match
        ):
            results = await client.fetch_matches_until_known(
                session=session,
                player=player,
                known_match_ids={"EUW1_OLD"},
                role_filter="JUNGLE",
                include_timeline=False,
                max_new=5,
            )

        assert len(results) == 1
        assert results[0].match_id == "EUW1_NEW1"
        mock_match.assert_called_once_with(session, "EUW1_NEW1")
