"""Daily elo tracking: one point per day for each verified account, without having to turn it on."""

from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from ygg_core.domain.participant import RankInfo

from app.db.models.user import User
from app.service.elo import player_ids_due_for_elo
from tests.helpers import create_player


@contextmanager
def riot_rank(*ranks):
    client = MagicMock()
    client.fetch_rank = AsyncMock(side_effect=ranks)
    client.fetch_summoner = AsyncMock(return_value=None)
    with patch("app.crud.player.riot_client", return_value=client), patch("app.crud.player.create_secure_session"):
        yield client


@pytest.fixture
async def owned_player(client, auth_headers, db):
    me = client.get("/auth/me", headers=auth_headers).json()
    return await create_player(db, user=await db.get(User, me["id"]))


async def test_a_verified_account_stores_one_point_per_day_without_asking(client, auth_headers, db, owned_player):
    url = f"/players/{owned_player.id}"
    assert client.get(f"{url}/elo", headers=auth_headers).json() == []
    assert owned_player.id in await player_ids_due_for_elo(db)  # verified: tracked automatically

    with riot_rank(RankInfo("DIAMOND", "II", 40, 100, 90), RankInfo("DIAMOND", "I", 12, 102, 90)):
        client.post(f"{url}/refresh", headers=auth_headers)
        client.post(f"{url}/refresh", headers=auth_headers)  # the same day: replaces the point

    points = client.get(f"{url}/elo", headers=auth_headers).json()
    assert [(p["tier"], p["division"], p["lp"], p["wins"]) for p in points] == [("DIAMOND", "I", 12, 102)]
    assert owned_player.id not in await player_ids_due_for_elo(db)  # it already has today's


async def test_an_unverified_account_is_not_tracked(client, auth_headers, db, owned_player):
    owned_player.verified_at = None
    await db.commit()
    assert owned_player.id not in await player_ids_due_for_elo(db)
    with riot_rank(RankInfo("DIAMOND", "II", 40, 100, 90)):
        client.post(f"/players/{owned_player.id}/refresh", headers=auth_headers)
    assert client.get(f"/players/{owned_player.id}/elo", headers=auth_headers).json() == []


def test_elo_of_other_users_players_is_not_available(client, auth_headers):
    assert client.get("/players/999999/elo", headers=auth_headers).status_code == 404
