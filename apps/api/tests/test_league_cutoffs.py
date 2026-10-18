"""Grandmaster and Challenger LP cutoffs over the complete apex ladder."""

from unittest.mock import AsyncMock, MagicMock, patch

from app.service.league_service import fetch_cutoffs_from_riot


def _league(prefix: str, lps: list[int]) -> list[dict]:
    return [{"puuid": f"{prefix}-{i}", "leaguePoints": lp} for i, lp in enumerate(lps)]


async def test_masters_above_the_lowest_grandmasters_move_the_cutoff():
    leagues = {
        "challengerleagues": _league("c", [2400] * 300),
        "grandmasterleagues": _league("g", [1900] * 690 + [1500] * 10),  # the last 10 will drop
        "masterleagues": _league("m", [1707] * 10 + [900] * 50),
    }
    client = MagicMock()
    client.fetch_league_entries = AsyncMock(side_effect=lambda _session, league: leagues[league])

    with patch("app.service.league_service.riot_client", return_value=client), patch(
        "app.service.league_service.create_secure_session"
    ):
        grandmaster, challenger = await fetch_cutoffs_from_riot("euw")

    # Position 1000: the 10 masters with 1707 LP get ahead of the grandmasters with 1500.
    assert (grandmaster, challenger) == (1707, 2400)
