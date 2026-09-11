"""Detalle de partida: se pide a Riot una vez, se guarda y solo lo ven los dueños del jugador."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import update

from app.core.config import settings
from app.crud.participants import upsert_participants
from app.db.models.match_detail import MatchDetail
from app.db.models.user import User
from tests.helpers import create_player, make_stats, unique

POSITIONS = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]


def match_payload(match_id: str, tracked_puuid: str) -> dict:
    participants = [
        {
            "participantId": pid,
            "puuid": tracked_puuid if pid == 3 else f"other-{pid}",
            "riotIdGameName": f"Player{pid}",
            "riotIdTagline": "EUW",
            "teamId": 100 if pid <= 5 else 200,
            "teamPosition": POSITIONS[(pid - 1) % 5],
            "championName": "Ahri",
            "champLevel": 15,
            "win": pid <= 5,
            "kills": pid,
            "deaths": 3,
            "assists": 5,
            "totalMinionsKilled": 150,
            "neutralMinionsKilled": 10,
            "goldEarned": 10_000 + pid * 100,
            "totalDamageDealtToChampions": 15_000 + pid * 500,
            "visionScore": 20,
            "summoner1Id": 4,
            "summoner2Id": 14,
            **{f"item{slot}": 3000 + slot for slot in range(7)},
        }
        for pid in range(1, 11)
    ]
    return {
        "metadata": {"matchId": match_id},
        "info": {
            "gameCreation": 1_780_000_000_000,
            "gameDuration": 1800,
            "queueId": 420,
            "gameVersion": "16.10.1",
            "participants": participants,
            "teams": [
                {"teamId": 100, "win": True, "objectives": {"tower": {"kills": 8}, "dragon": {"kills": 3}}},
                {"teamId": 200, "win": False, "objectives": {"tower": {"kills": 2}}},
            ],
        },
    }


@pytest.fixture
async def owned_match(client, auth_headers, db):
    me = client.get("/auth/me", headers=auth_headers).json()
    player = await create_player(db, user=await db.get(User, me["id"]))
    match_id = unique("EUW1")
    await upsert_participants(db, [make_stats(match_id, player.puuid)])
    await db.commit()
    return player, match_id


def fake_riot(payload):
    riot = MagicMock()
    riot.fetch_match = AsyncMock(return_value=payload)
    return riot


async def test_details_are_fetched_once_and_then_served_from_the_database(client, auth_headers, owned_match):
    player, match_id = owned_match
    riot = fake_riot(match_payload(match_id, player.puuid))

    with patch("app.service.match_details.riot_client", return_value=riot) as factory, patch(
        "app.service.match_details.create_secure_session"
    ):
        first = client.get(f"/matches/{match_id}/details", headers=auth_headers)
        second = client.get(f"/matches/{match_id}/details", headers=auth_headers)

    assert first.status_code == 200
    body = first.json()
    assert [len(team["participants"]) for team in body["teams"]] == [5, 5]
    assert (body["teams"][0]["towers"], body["teams"][0]["dragons"]) == (8, 3)
    tracked = next(p for team in body["teams"] for p in team["participants"] if p["puuid"] == player.puuid)
    assert (tracked["game_name"], tracked["role"], tracked["items"]) == ("Player3", "MID", [3000, 3001, 3002, 3003, 3004, 3005])
    assert sorted(p["badge"] for team in body["teams"] for p in team["participants"] if p["badge"]) == ["ACE", "MVP"]

    assert second.json() == body
    riot.fetch_match.assert_awaited_once()
    factory.assert_called_once_with("euw1")  # la región sale del prefijo del match id


async def test_stored_details_are_scored_again_when_read(client, auth_headers, owned_match, db):
    """Cambiar las referencias Challenger no obliga a volver a pedir la partida a Riot."""
    player, match_id = owned_match
    with patch("app.service.match_details.riot_client", return_value=fake_riot(match_payload(match_id, player.puuid))), patch(
        "app.service.match_details.create_secure_session"
    ):
        body = client.get(f"/matches/{match_id}/details", headers=auth_headers).json()

    stale = (await db.get(MatchDetail, match_id)).summary
    for team in stale["teams"]:
        for participant in team["participants"]:
            participant.update(score=0, placement=0, badge=None)
    await db.execute(update(MatchDetail).where(MatchDetail.match_id == match_id).values(summary=stale))
    await db.commit()

    with patch("app.service.match_details.riot_client") as factory:
        again = client.get(f"/matches/{match_id}/details", headers=auth_headers)

    assert again.json() == body
    factory.assert_not_called()


async def test_matches_of_other_users_are_not_available(client, auth_headers, db):
    stranger = await create_player(db)
    match_id = unique("EUW1")
    await upsert_participants(db, [make_stats(match_id, stranger.puuid)])
    await db.commit()

    with patch("app.service.match_details.riot_client") as factory:
        response = client.get(f"/matches/{match_id}/details", headers=auth_headers)

    assert response.status_code == 404
    factory.assert_not_called()


async def test_riot_failure_is_reported_as_unavailable(client, auth_headers, owned_match):
    _, match_id = owned_match
    with patch("app.service.match_details.riot_client", return_value=fake_riot(None)), patch(
        "app.service.match_details.create_secure_session"
    ):
        response = client.get(f"/matches/{match_id}/details", headers=auth_headers)
    assert response.status_code == 503


async def test_demo_mode_never_calls_riot(client, auth_headers, owned_match, monkeypatch):
    _, match_id = owned_match
    monkeypatch.setattr(settings, "demo_mode", True)
    with patch("app.service.match_details.riot_client") as factory:
        response = client.get(f"/matches/{match_id}/details", headers=auth_headers)
    assert response.status_code == 404
    factory.assert_not_called()


def test_rejects_malformed_match_ids(client, auth_headers):
    assert client.get("/matches/not-a-match/details", headers=auth_headers).status_code == 422
