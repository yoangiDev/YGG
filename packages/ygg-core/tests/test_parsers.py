from datetime import UTC, datetime

from factories import DURATION, GAME_CREATION_MS, MATCH_ID, make_match, make_timeline, puuid
from ygg_core.riot.parsers import (
    parse_participant,
    player_role_in_match,
    role_bound_item_for,
)


def test_committed_fixtures_match_generator(match_payload, timeline_payload):
    assert match_payload == make_match()
    assert timeline_payload == make_timeline()


def test_parses_participant_stats(match_payload):
    stats = parse_participant(match_payload, puuid(1))

    assert stats is not None
    assert stats.match_id == MATCH_ID
    assert stats.creation_time == datetime.fromtimestamp(GAME_CREATION_MS / 1000 + DURATION, tz=UTC)
    assert stats.duration == DURATION
    assert stats.queue_id == 420
    assert stats.game_version == "16.10.712.3456"
    assert (stats.puuid, stats.participant_id, stats.team_id) == (puuid(1), 1, 100)
    assert (stats.player_role, stats.champion, stats.win) == ("TOP", "Gnar", True)
    assert (stats.kills, stats.deaths, stats.assists) == (3, 4, 4)
    # Equipo azul: 20 kills, 72 500 de daño y 51 000 de oro.
    assert stats.kill_participation == 35.0
    assert stats.damage_share == 15.9
    assert stats.gold_share == 18.4
    assert stats.total_cs == 188
    assert (stats.primary_rune, stats.secondary_tree) == (8112, 8300)
    assert (stats.first_dragon, stats.void_grubs, stats.herald) == (True, True, True)
    assert stats.role_bound_item == 1220
    assert stats.timeline_enriched is False


def test_remake_is_discarded():
    assert parse_participant(make_match(duration=200), puuid(1)) is None


def test_role_filter():
    match = make_match()
    assert parse_participant(match, puuid(1), "JUNGLE") is None
    assert parse_participant(match, puuid(1), "top") is not None
    assert parse_participant(match, puuid(4), "ADC") is not None


def test_unknown_player_returns_none():
    assert parse_participant(make_match(), "puuid-desconocido") is None


def test_champion_name_is_normalized_for_data_dragon():
    match = make_match(overrides={1: {"championName": "FiddleSticks"}})
    stats = parse_participant(match, puuid(1))
    assert stats is not None and stats.champion == "Fiddlesticks"


def test_two_players_in_the_same_match_get_their_own_stats():
    """Precursor en el core del bug P1: cada jugador tiene sus propias estadísticas."""
    match = make_match()
    top = parse_participant(match, puuid(1))
    jungle = parse_participant(match, puuid(2))

    assert top is not None and jungle is not None
    assert top.match_id == jungle.match_id
    assert (top.champion, top.player_role, top.kills) == ("Gnar", "TOP", 3)
    assert (jungle.champion, jungle.player_role, jungle.kills) == ("LeeSin", "JUNGLE", 4)


def test_match_helpers():
    match = make_match()
    assert player_role_in_match(match, puuid(3)) == "MID"
    assert player_role_in_match(match, "nadie") == "UNKNOWN"
    assert role_bound_item_for(match, puuid(4)) == 3006
    assert role_bound_item_for(match, "nadie") is None
