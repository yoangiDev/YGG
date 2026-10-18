"""Lobby average elo: current rank of the 10 players, cached per player."""

from unittest.mock import AsyncMock, MagicMock, patch

from ygg_core.domain.participant import RankInfo

from app.service.lobby_rank import from_ladder_points, ladder_points
from tests.test_match_details import fake_riot, match_payload, owned_match  # noqa: F401  (fixture)


def test_ladder_points_round_trip():
    assert ladder_points(RankInfo("GOLD", "II", 45, 0, 0)) == 3 * 400 + 200 + 45
    assert ladder_points(RankInfo("GRANDMASTER", "I", 700, 0, 0)) == 3500
    assert from_ladder_points(3 * 400 + 200 + 45) == ("GOLD", "II", 45)
    assert from_ladder_points(3500) == ("MASTER", "I", 700)  # without the region's cutoffs


def test_apex_average_takes_its_tier_from_the_region_cutoffs():
    cutoffs = (500, 900)  # grandmaster, challenger
    assert from_ladder_points(3200, cutoffs) == ("MASTER", "I", 400)
    assert from_ladder_points(3300, cutoffs) == ("GRANDMASTER", "I", 500)
    assert from_ladder_points(3750, cutoffs) == ("CHALLENGER", "I", 950)


async def test_lobby_is_computed_once_and_then_served_as_it_was(client, auth_headers, owned_match):  # noqa: F811
    player, match_id = owned_match
    with patch("app.service.match_details.riot_client", return_value=fake_riot(match_payload(match_id, player.puuid))), patch(
        "app.service.match_details.create_secure_session"
    ):
        client.get(f"/matches/{match_id}/details", headers=auth_headers)

    # Five in Diamond II 50 LP (2650), four in Diamond IV 50 LP (2450) and one unranked.
    def rank_of(_session, puuid, **_):
        pid = 3 if puuid == player.puuid else int(puuid.split("-")[1])
        if pid == 10:
            return None
        return RankInfo("DIAMOND", "II" if pid <= 5 else "IV", 50, 10, 10)

    riot = MagicMock()
    riot.fetch_rank = AsyncMock(side_effect=rank_of)
    with patch("app.service.lobby_rank.riot_client", return_value=riot), patch("app.service.lobby_rank.create_secure_session"):
        first = client.get(f"/matches/{match_id}/lobby-rank", headers=auth_headers).json()
        calls = riot.fetch_rank.await_count
        second = client.get(f"/matches/{match_id}/lobby-rank", headers=auth_headers).json()

    # (5 × 2650 + 4 × 2450) / 9 = 2561 → Diamond III 61 LP
    players = {p["puuid"]: p for p in first.pop("players")}
    assert first == {"tier": "DIAMOND", "division": "III", "lp": 61, "ranked_players": 9}
    assert players[player.puuid] == {"puuid": player.puuid, "tier": "DIAMOND", "division": "II", "lp": 50}
    unranked = f"other-10-{match_id}"
    assert players[unranked] == {"puuid": unranked, "tier": None, "division": None, "lp": None}
    # The second time it comes out stored as is, without requesting any rank again.
    assert second == {**first, "players": second["players"]} and len(second["players"]) == 10
    assert (calls, riot.fetch_rank.await_count) == (10, 10)


def test_lobby_rank_of_other_users_matches_is_not_available(client, auth_headers):
    assert client.get("/matches/EUW1_1/lobby-rank", headers=auth_headers).status_code == 404
