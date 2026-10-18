from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from factories import blank_stats, make_match, make_timeline, puuid
from ygg_core.domain.participant import TIMELINE_VERSION, PlayerRef, RankInfo
from ygg_core.riot.client import RiotAPIClient, cached_participant_usable
from ygg_core.riot.errors import RiotNotFoundError, RiotUnavailableError
from ygg_core.riot.rate_limiter import RiotRateLimiter

JUNGLER = PlayerRef(puuid(2), "Test", "EUW")
PRE_S26 = datetime(2025, 6, 1, tzinfo=UTC)


def _client(**kwargs) -> RiotAPIClient:
    return RiotAPIClient(
        "RGAPI-test", "euw", limiter=RiotRateLimiter(per_second=1000, per_two_minutes=1000), **kwargs
    )


class DictCache:
    def __init__(self):
        self.data = {}

    def get_payload(self, kind, match_id):
        return self.data.get((kind, match_id))

    def put_payload(self, kind, match_id, payload):
        self.data[(kind, match_id)] = payload


class FakeResponse:
    def __init__(self, status, payload=None, headers=None):
        self.status = status
        self._payload = payload
        self.headers = headers or {}

    async def json(self):
        return self._payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class FakeSession:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = 0

    def get(self, url, headers=None):
        self.calls += 1
        return self.responses.pop(0)


def test_requires_api_key():
    with pytest.raises(ValueError):
        RiotAPIClient("")


class TestFetchParticipants:
    async def test_skips_riot_for_enriched_known_matches(self):
        client = _client()
        session = AsyncMock()
        cached = blank_stats(
            match_id="EUW1_CACHED", creation_time=PRE_S26, puuid=JUNGLER.puuid,
            player_role="JUNGLE", timeline_enriched=True, timeline_version=TIMELINE_VERSION,
        )
        with patch.object(client, "fetch_match", AsyncMock(return_value=make_match("EUW1_NEW"))) as fetch_match, \
             patch.object(client, "fetch_timeline", AsyncMock(return_value={"info": {"frames": []}})) as fetch_timeline:
            results = await client.fetch_participants(
                session, JUNGLER, known={"EUW1_CACHED": cached}, match_ids=["EUW1_CACHED", "EUW1_NEW"]
            )

        fetch_match.assert_called_once_with(session, "EUW1_NEW")
        fetch_timeline.assert_called_once_with(session, "EUW1_NEW")
        assert cached in results
        assert {r.match_id for r in results} == {"EUW1_CACHED", "EUW1_NEW"}

    async def test_skips_timeline_for_wrong_role(self):
        client = _client()
        with patch.object(client, "fetch_match", AsyncMock(return_value=make_match())) as fetch_match, \
             patch.object(client, "fetch_timeline", AsyncMock()) as fetch_timeline:
            results = await client.fetch_participants(
                AsyncMock(), JUNGLER, role_filter="MID", match_ids=["EUW1_7000000001"]
            )
        fetch_match.assert_called_once()
        fetch_timeline.assert_not_called()
        assert results == []

    async def test_max_matches_limits_scheduled_fetches(self):
        client = _client()
        ids = [f"EUW1_{i}" for i in range(100)]
        with patch.object(client, "fetch_match_ids_page", AsyncMock(return_value=ids)) as page, \
             patch.object(client, "fetch_match", AsyncMock(return_value=None)) as fetch_match:
            await client.fetch_participants(AsyncMock(), JUNGLER, max_matches=20, include_timeline=False)
        page.assert_called_once()
        assert page.call_args.kwargs["count"] == 20
        assert fetch_match.call_count == 20

    async def test_progress_is_reported(self):
        client = _client()
        progress = []
        with patch.object(client, "fetch_match", AsyncMock(return_value=make_match())), \
             patch.object(client, "fetch_timeline", AsyncMock(return_value=make_timeline())):
            results = await client.fetch_participants(
                AsyncMock(), JUNGLER, match_ids=["EUW1_7000000001"],
                on_progress=lambda done, total: progress.append((done, total)),
            )
        assert progress == [(1, 1)]
        assert results[0].fullclear_time == 300


class TestCachedParticipantUsable:
    def test_never_reuses_another_players_row(self):
        row = blank_stats(creation_time=PRE_S26, puuid=puuid(1), timeline_enriched=True, timeline_version=TIMELINE_VERSION)
        assert cached_participant_usable(row, "ALL", puuid(1)) is True
        assert cached_participant_usable(row, "ALL", puuid(2)) is False

    def test_s26_rows_need_quest_data(self):
        row = blank_stats(timeline_enriched=True, timeline_version=TIMELINE_VERSION)
        assert cached_participant_usable(row, "ALL") is False
        row.quest_completion_time = 600
        assert cached_participant_usable(row, "ALL") is True

    def test_role_must_match_filter(self):
        row = blank_stats(creation_time=PRE_S26, player_role="MID", timeline_enriched=True, timeline_version=TIMELINE_VERSION)
        assert cached_participant_usable(row, "MID") is True
        assert cached_participant_usable(row, "TOP") is False

    def test_not_enriched_is_not_usable(self):
        assert cached_participant_usable(blank_stats(creation_time=PRE_S26), "ALL") is False

    def test_rows_from_an_older_timeline_version_are_downloaded_again(self):
        row = blank_stats(creation_time=PRE_S26, timeline_enriched=True, timeline_version=TIMELINE_VERSION - 1)
        assert cached_participant_usable(row, "ALL") is False


class TestRequests:
    async def test_raw_cache_avoids_http(self):
        cache = DictCache()
        cache.put_payload("match", "EUW1_X", {"metadata": {"matchId": "EUW1_X"}})
        client = _client(raw_cache=cache)
        with patch.object(client, "_riot_get", AsyncMock()) as riot_get:
            assert await client.fetch_match(AsyncMock(), "EUW1_X") == {"metadata": {"matchId": "EUW1_X"}}
        riot_get.assert_not_called()

    async def test_downloaded_payloads_are_cached(self):
        cache = DictCache()
        client = _client(raw_cache=cache)
        timeline = make_timeline()
        with patch.object(client, "_riot_get", AsyncMock(return_value=(200, timeline))):
            await client.fetch_timeline(AsyncMock(), "EUW1_7000000001")
        assert cache.get_payload("timeline", "EUW1_7000000001") == timeline

    async def test_fetch_participant_parses_and_enriches(self):
        client = _client()
        with patch.object(client, "fetch_match", AsyncMock(return_value=make_match())), \
             patch.object(client, "fetch_timeline", AsyncMock(return_value=make_timeline())):
            stats = await client.fetch_participant(AsyncMock(), "EUW1_7000000001", puuid(1))
        assert stats is not None and stats.gold_diff_14 == -350 and stats.timeline_enriched

    async def test_get_puuid_not_found(self):
        client = _client()
        with patch.object(client, "_riot_get", AsyncMock(return_value=(404, None))), \
             pytest.raises(RiotNotFoundError):
            await client.get_puuid(AsyncMock(), "Nobody", "EUW")

    async def test_fetch_rank_picks_solo_queue(self):
        client = _client()
        entries = [
            {"queueType": "RANKED_FLEX_SR", "tier": "GOLD", "rank": "I", "leaguePoints": 1, "wins": 1, "losses": 1},
            {"queueType": "RANKED_SOLO_5x5", "tier": "DIAMOND", "rank": "II", "leaguePoints": 42, "wins": 10, "losses": 8},
        ]
        with patch.object(client, "_riot_get", AsyncMock(return_value=(200, entries))):
            assert await client.fetch_rank(AsyncMock(), "p") == RankInfo("DIAMOND", "II", 42, 10, 8)

    async def test_fetch_rank_raise_on_error_only_for_transient_failures(self):
        client = _client()
        for status, raises in ((429, True), (503, True), (400, False)):
            with patch.object(client, "_riot_get", AsyncMock(return_value=(status, None))):
                assert await client.fetch_rank(AsyncMock(), "p") is None
                if raises:
                    with pytest.raises(RiotUnavailableError):
                        await client.fetch_rank(AsyncMock(), "p", raise_on_error=True)
                else:
                    assert await client.fetch_rank(AsyncMock(), "p", raise_on_error=True) is None

    async def test_fetch_summoner_404_means_wrong_region(self):
        client = _client()
        with patch.object(client, "_riot_get", AsyncMock(return_value=(404, None))), \
             pytest.raises(RiotNotFoundError):
            await client.fetch_summoner(AsyncMock(), "p")

    async def test_429_pauses_globally_and_retries(self):
        limiter = RiotRateLimiter(per_second=1000, per_two_minutes=1000)
        client = RiotAPIClient("RGAPI-test", limiter=limiter)
        session = FakeSession(
            FakeResponse(429, headers={"Retry-After": "0.05"}),
            FakeResponse(200, payload={"ok": True}),
        )
        status, data = await client._riot_get(session, "https://example.test")
        assert (status, data) == (200, {"ok": True})
        assert session.calls == 2
        assert limiter._paused_until > 0

    async def test_non_retryable_status_returns_immediately(self):
        client = _client()
        session = FakeSession(FakeResponse(403))
        assert await client._riot_get(session, "https://example.test") == (403, None)
        assert session.calls == 1
