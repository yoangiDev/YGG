"""Season download by pages and the season's per-champion stats."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from ygg_core.riot.client import MATCH_IDS_PAGE_SIZE

from app.core.config import settings
from app.crud.participants import add_history_entries, upsert_participants
from app.db.models.user import User
from tests.helpers import create_player, make_stats, unique


def season_games(puuid: str, count: int, first: int = 0):
    prefix = unique("EUW1")
    return [
        make_stats(f"{prefix}_{i}", puuid, champion="Ahri" if i % 2 else "Zed", creation_time=settings.season_start + timedelta(days=i))
        for i in range(first, first + count)
    ]


@pytest.fixture
async def owned_player(client, auth_headers, db):
    me = client.get("/auth/me", headers=auth_headers).json()
    return await create_player(db, user=await db.get(User, me["id"]))


async def test_season_sync_pages_until_riot_runs_out(client, auth_headers, db, owned_player):
    pages = [season_games(owned_player.puuid, MATCH_IDS_PAGE_SIZE), season_games(owned_player.puuid, 7)]
    riot = MagicMock()
    riot.fetch_match_ids_page = AsyncMock(side_effect=[[g.match_id for g in page] for page in pages])
    riot.fetch_participants = AsyncMock(side_effect=pages)
    riot.fetch_match = AsyncMock(return_value=None)  # without the 10-player summary in this test

    with patch("app.service.match_history.riot_client", return_value=riot), patch(
        "app.service.match_history.create_secure_session"
    ), patch("app.service.match_history.invalidate_dashboards_for_participants", AsyncMock()):
        first = client.post(f"/players/{owned_player.id}/season-sync", headers=auth_headers).json()
        second = client.post(
            f"/players/{owned_player.id}/season-sync?offset={first['next_offset']}", headers=auth_headers
        ).json()

    assert (first["downloaded"], first["stored_games"], first["done"]) == (MATCH_IDS_PAGE_SIZE, MATCH_IDS_PAGE_SIZE, False)
    assert (second["downloaded"], second["stored_games"], second["done"]) == (7, MATCH_IDS_PAGE_SIZE + 7, True)
    # The second page continues where the first ended and only requests the season.
    starts = [call.args[4] for call in riot.fetch_match_ids_page.await_args_list]
    assert starts == [0, MATCH_IDS_PAGE_SIZE]
    assert {call.args[2] for call in riot.fetch_match_ids_page.await_args_list} == {int(settings.season_start.timestamp())}


async def test_a_page_with_remakes_does_not_end_the_sync(client, auth_headers, db, owned_player):
    """The cursor goes by Riot ids: a remake leaves no row and must not cut the download short."""
    games = season_games(owned_player.puuid, MATCH_IDS_PAGE_SIZE)
    riot = MagicMock()
    riot.fetch_match_ids_page = AsyncMock(return_value=[g.match_id for g in games])
    riot.fetch_participants = AsyncMock(return_value=games[:-3])  # 3 remakes: Riot lists them, they leave no row
    riot.fetch_match = AsyncMock(return_value=None)

    with patch("app.service.match_history.riot_client", return_value=riot), patch(
        "app.service.match_history.create_secure_session"
    ), patch("app.service.match_history.invalidate_dashboards_for_participants", AsyncMock()):
        page = client.post(f"/players/{owned_player.id}/season-sync", headers=auth_headers).json()

    assert (page["downloaded"], page["done"], page["next_offset"]) == (MATCH_IDS_PAGE_SIZE - 3, False, MATCH_IDS_PAGE_SIZE)


async def test_the_season_window_comes_from_the_configuration(client, auth_headers, db, owned_player, monkeypatch):
    """Season dates are set by hand: Riot changes them every year."""
    monkeypatch.setattr(settings, "season_start", datetime(2025, 5, 1, tzinfo=UTC))
    monkeypatch.setattr(settings, "season_end", datetime(2025, 9, 1, tzinfo=UTC))
    riot = MagicMock()
    riot.fetch_match_ids_page = AsyncMock(return_value=[])
    riot.fetch_participants = AsyncMock(return_value=[])
    riot.fetch_match = AsyncMock(return_value=None)

    with patch("app.service.match_history.riot_client", return_value=riot), patch(
        "app.service.match_history.create_secure_session"
    ):
        client.post(f"/players/{owned_player.id}/season-sync", headers=auth_headers)

    start_t, end_t = riot.fetch_match_ids_page.await_args.args[2:4]
    assert (start_t, end_t) == (int(settings.season_start.timestamp()), int(settings.season_end.timestamp()))


async def test_champion_stats_can_be_limited_to_the_season(client, auth_headers, db, owned_player):
    old = make_stats(unique("EUW1"), owned_player.puuid, champion="Garen", creation_time=settings.season_start - timedelta(days=5))
    ids = await upsert_participants(db, [old, *season_games(owned_player.puuid, 2)])
    await add_history_entries(db, owned_player.id, list(ids.values()))
    await db.commit()

    url = f"/matches/player/{owned_player.id}/champions"
    everything = client.get(url, headers=auth_headers).json()
    season = client.get(f"{url}?season=true", headers=auth_headers).json()

    assert "Garen" in {row["champion_name"] for row in everything}
    assert "Garen" not in {row["champion_name"] for row in season}
    assert sum(row["games"] for row in season) == 2
