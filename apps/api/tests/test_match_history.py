"""Historial por páginas: sigue a Riot, reutiliza lo guardado y acumula páginas."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.crud.participants import add_history_entries, upsert_participants
from app.db.models.user import User
from app.service.match_history import fetch_history_page, get_history_from_cache, is_history_fresh
from tests.helpers import create_player, make_stats, unique

NEWEST = datetime(2025, 6, 1, 12, tzinfo=timezone.utc)


def history(puuid: str, count: int):
    """`count` partidas de la más reciente a la más antigua."""
    prefix = unique("EUW1")
    return [make_stats(f"{prefix}_{i}", puuid, creation_time=NEWEST - timedelta(hours=i)) for i in range(count)]


@contextmanager
def fake_riot(client: MagicMock):
    with patch("app.service.match_history.riot_client", return_value=client), patch(
        "app.service.match_history.create_secure_session"
    ), patch("app.service.match_history.invalidate_dashboards_for_participants", AsyncMock()):
        yield


def riot_client(ids_pages, participant_pages) -> MagicMock:
    client = MagicMock()
    client.fetch_match_ids_page = AsyncMock(side_effect=ids_pages)
    client.fetch_participants = AsyncMock(side_effect=participant_pages)
    return client


class TestFetchHistoryPage:
    async def test_first_page_reuses_stored_matches_and_marks_history_fresh(self, db):
        player = await create_player(db)
        games = history(player.puuid, 3)
        await upsert_participants(db, [games[0]])
        await db.commit()
        client = riot_client([[g.match_id for g in games]], [games[1:]])

        with fake_riot(client):
            rows = await fetch_history_page(db, player, offset=0, limit=3)

        assert [r.match_id for r in rows] == [g.match_id for g in games]
        # Solo se descargan las que faltaban.
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
            second = await fetch_history_page(db, player, offset=3, limit=3)

        assert [r.match_id for r in second] == ids[3:]
        assert client.fetch_match_ids_page.await_args.args[4] == 3  # índice de inicio en Riot
        assert player.match_history_cached_at is None  # solo la primera página renueva la caché
        assert [r.match_id for r in await get_history_from_cache(db, player.id, limit=10)] == ids
        assert [r.match_id for r in await get_history_from_cache(db, player.id, limit=10, offset=3)] == ids[3:]

    async def test_past_the_end_of_the_history_returns_nothing(self, db):
        player = await create_player(db)
        client = riot_client([[]], [])

        with fake_riot(client):
            assert await fetch_history_page(db, player, offset=40, limit=10) == []

        client.fetch_participants.assert_not_awaited()


@pytest.fixture
async def owned_player(client, auth_headers, db):
    me = client.get("/auth/me", headers=auth_headers).json()
    return await create_player(db, user=await db.get(User, me["id"]))


class TestHistoryEndpoint:
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
