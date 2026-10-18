"""Paginated history: follows Riot, reuses what is stored and accumulates pages."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.crud.participants import add_history_entries, upsert_participants
from app.db.models.user import User
from app.service.match_history import fetch_history_page, get_history_from_cache, is_history_fresh
from tests.helpers import create_player, make_stats, unique
from tests.test_match_details import match_payload

NEWEST = datetime(2025, 6, 1, 12, tzinfo=timezone.utc)


def history(puuid: str, count: int):
    """`count` matches from the most recent to the oldest."""
    prefix = unique("EUW1")
    return [make_stats(f"{prefix}_{i}", puuid, creation_time=NEWEST - timedelta(hours=i)) for i in range(count)]


@contextmanager
def fake_riot(client: MagicMock):
    with patch("app.service.match_history.riot_client", return_value=client), patch(
        "app.service.match_history.create_secure_session"
    ), patch("app.service.match_history.invalidate_dashboards_for_participants", AsyncMock()):
        yield


def riot_client(ids_pages, participant_pages, fetch_match=None, fetch_timeline=None) -> MagicMock:
    client = MagicMock()
    client.fetch_match_ids_page = AsyncMock(side_effect=ids_pages)
    client.fetch_participants = AsyncMock(side_effect=participant_pages)
    client.fetch_match = fetch_match or AsyncMock(return_value=None)
    client.fetch_timeline = fetch_timeline or AsyncMock(return_value=None)
    return client


def timeline_payload() -> dict:
    """30 minutes even in gold; at 4:50 the followed player (participant 3) kills participant 8 alone."""
    frames = [
        {"timestamp": m * 60_000, "events": [],
         "participantFrames": {str(pid): {"totalGold": 500 + 400 * m, "xp": 300 * m, "level": 1 + m // 2} for pid in range(1, 11)}}
        for m in range(31)
    ]
    frames[4]["events"] = [
        {"type": "CHAMPION_KILL", "timestamp": 290_000, "killerId": 3, "victimId": 8, "assistingParticipantIds": [], "bounty": 300},
    ]
    return {"info": {"frames": frames}}


class TestFetchHistoryPage:
    async def test_first_page_reuses_stored_matches_and_marks_history_fresh(self, db):
        player = await create_player(db)
        games = history(player.puuid, 3)
        await upsert_participants(db, [games[0]])
        await db.commit()
        client = riot_client([[g.match_id for g in games]], [games[1:]])

        with fake_riot(client):
            rows, listed = await fetch_history_page(db, player, offset=0, limit=3)

        assert [r.match_id for r in rows] == [g.match_id for g in games]
        assert listed == 3  # the ids Riot gave, even if some were already stored
        # Only the missing ones are downloaded.
        assert client.fetch_participants.await_args.kwargs["match_ids"] == [games[1].match_id, games[2].match_id]
        assert is_history_fresh(player)

    async def test_next_pages_accumulate_without_dropping_earlier_ones(self, db):
        player = await create_player(db)
        games = history(player.puuid, 5)
        ids = [g.match_id for g in games]
        client = riot_client([ids[:3], ids[3:]], [games[:3], games[3:]])

        with fake_riot(client):
            await fetch_history_page(db, player, offset=0, limit=3)
            player.match_history_cached_at = None
            second, _ = await fetch_history_page(db, player, offset=3, limit=3)

        assert [r.match_id for r in second] == ids[3:]
        assert client.fetch_match_ids_page.await_args.args[4] == 3  # start index in Riot
        assert player.match_history_cached_at is None  # only the first page renews the cache
        assert [r.match_id for r in await get_history_from_cache(db, player.id, limit=10)] == ids
        assert [r.match_id for r in await get_history_from_cache(db, player.id, limit=10, offset=3)] == ids[3:]

    async def test_past_the_end_of_the_history_returns_nothing(self, db):
        player = await create_player(db)
        client = riot_client([[]], [])

        with fake_riot(client):
            assert await fetch_history_page(db, player, offset=40, limit=10) == ([], 0)

        client.fetch_participants.assert_not_awaited()


@pytest.fixture
async def owned_player(client, auth_headers, db):
    me = client.get("/auth/me", headers=auth_headers).json()
    return await create_player(db, user=await db.get(User, me["id"]))


class TestHistoryEndpoint:
    async def test_rows_carry_the_score_and_badge_of_the_stored_summary(self, client, auth_headers, db, owned_player):
        games = history(owned_player.puuid, 2)
        payloads = {g.match_id: match_payload(g.match_id, owned_player.puuid) for g in games}
        fetch_match = AsyncMock(side_effect=lambda session, match_id: payloads[match_id] if match_id == games[0].match_id else None)
        riot = riot_client([[g.match_id for g in games]], [games], fetch_match)

        with fake_riot(riot):
            rows = client.get(f"/matches/player/{owned_player.id}?sync=true", headers=auth_headers).json()
        with patch("app.service.match_details.riot_client") as factory:
            details = client.get(f"/matches/{games[0].match_id}/details", headers=auth_headers).json()

        factory.assert_not_called()  # the summary was stored with the history
        tracked = next(p for team in details["teams"] for p in team["participants"] if p["puuid"] == owned_player.puuid)
        assert {k: rows[0][k] for k in ("score", "placement", "badge")} == {k: tracked[k] for k in ("score", "placement", "badge")}
        assert (rows[1]["score"], rows[1]["badge"]) == (None, None)  # Riot didn't return it: no summary


    async def test_with_the_timeline_the_score_is_the_timeline_grade(self, client, auth_headers, db, owned_player):
        """With the timeline, the grade that predicts the analysis one (ygg_core.metrics.timeline_grade) rules, not the stats one."""
        from ygg_core.metrics.timeline_grade import timeline_grades

        games = history(owned_player.puuid, 1)
        payload = match_payload(games[0].match_id, owned_player.puuid)
        riot = riot_client([[games[0].match_id]], [games], AsyncMock(return_value=payload), AsyncMock(return_value=timeline_payload()))

        with fake_riot(riot):
            rows = client.get(f"/matches/player/{owned_player.id}?sync=true", headers=auth_headers).json()

        assert rows[0]["score"] == timeline_grades(payload, timeline_payload())[owned_player.puuid]
        assert rows[0]["badge"] == "MVP" and rows[0]["placement"] in (1, 2)
        assert riot.fetch_participants.await_args.kwargs["include_timeline"] is True

    async def test_a_fresh_history_with_fewer_games_than_asked_goes_to_riot(self, client, auth_headers, db, owned_player):
        """Fresh is not complete: the card downloads 20 and the snapshot dialog requests 100 (the day sessions)."""
        from datetime import UTC, datetime
        from sqlalchemy import update

        from app.db.models.player import Player

        games = history(owned_player.puuid, 2)
        ids = await upsert_participants(db, games)
        await add_history_entries(db, owned_player.id, list(ids.values()))
        await db.execute(update(Player).where(Player.id == owned_player.id).values(match_history_cached_at=datetime.now(UTC)))
        await db.commit()

        riot = AsyncMock(return_value=(games, 2))
        with patch("app.routers.matches.fetch_history_page", riot):
            assert len(client.get(f"/matches/player/{owned_player.id}?limit=2", headers=auth_headers).json()) == 2
            riot.assert_not_awaited()  # it has the ones requested: it comes from the cache
            client.get(f"/matches/player/{owned_player.id}?limit=100", headers=auth_headers)
        riot.assert_awaited_once()

    async def test_serves_the_stored_page_when_riot_fails(self, client, auth_headers, db, owned_player):
        games = history(owned_player.puuid, 4)
        ids = await upsert_participants(db, games)
        await add_history_entries(db, owned_player.id, list(ids.values()))
        await db.commit()

        with patch("app.routers.matches.fetch_history_page", AsyncMock(side_effect=RuntimeError("Riot down"))):
            response = client.get(f"/matches/player/{owned_player.id}?offset=2&limit=10", headers=auth_headers)
            beyond = client.get(f"/matches/player/{owned_player.id}?offset=50&limit=10", headers=auth_headers)

        assert response.status_code == 200
        assert [m["match_id"] for m in response.json()] == [g.match_id for g in games[2:]]
        assert beyond.status_code == 503

    async def test_champion_stats_require_ownership(self, client, auth_headers, owned_player):
        assert client.get(f"/matches/player/{owned_player.id}/champions", headers=auth_headers).json() == []
        assert client.get("/matches/player/999999/champions", headers=auth_headers).status_code == 404
        assert client.get(f"/matches/player/{owned_player.id}/champions?limit=0", headers=auth_headers).status_code == 422
