"""Traducción entre el dominio de ygg-core y los modelos ORM de la API."""

from datetime import datetime, timezone

from ygg_core.domain.participant import RankInfo, SummonerInfo

from app.db.models.match import Match
from app.db.models.participant import MatchParticipant
from app.db.models.player import Player
from app.service.riot import (
    apply_rank,
    apply_summoner,
    copy_timeline_fields,
    match_row,
    participant_from_row,
    participant_row,
    player_ref,
)
from tests.helpers import make_stats


def _row_for(stats) -> MatchParticipant:
    row = MatchParticipant(**participant_row(stats))
    row.match = Match(**match_row(stats))
    return row


def test_participant_survives_roundtrip_through_orm():
    original = make_stats("EUW1_1", "p1", participant_id=3, team_id=200, game_version="16.10.1", quest_completion_time=600)
    assert participant_from_row(_row_for(original)) == original


def test_null_columns_take_domain_defaults():
    row = MatchParticipant(match_id="EUW1_2", puuid="p", creation_time=datetime.now(timezone.utc), champion="Zed", win=False)
    row.match = Match(match_id="EUW1_2", creation_time=row.creation_time, duration=1500)
    stats = participant_from_row(row)
    assert (stats.kills, stats.death_events, stats.player_role) == (0, [], "UNKNOWN")
    assert (stats.duration, stats.queue_id, stats.game_version) == (1500, 420, "")
    assert stats.fullclear_time is None


def test_copy_timeline_fields_refreshes_existing_row():
    row = _row_for(make_stats("EUW1_3", "p", timeline_enriched=False, gold_diff_14=0))
    copy_timeline_fields(row, make_stats("EUW1_3", "p", gold_diff_14=321, fullclear_time=290))
    assert (row.gold_diff_14, row.fullclear_time, row.timeline_enriched) == (321, 290, True)


def test_rank_and_summoner_are_applied_to_player():
    player = Player(game_name="Faker", tag_line="KR1", puuid="p", region="kr")
    assert apply_rank(player, None) is False
    assert apply_rank(player, RankInfo("CHALLENGER", "I", 1500, 300, 200)) is True
    apply_summoner(player, SummonerInfo(29))
    assert (player.tier, player.lp, player.wins, player.profile_icon_id) == ("CHALLENGER", 1500, 300, 29)
    assert player_ref(player).label == "Faker#KR1"
