"""Traducción entre el dominio de ygg-core y los modelos ORM de la API."""

from dataclasses import fields
from datetime import datetime, timezone

from ygg_core.domain.participant import ParticipantStats, RankInfo, SummonerInfo

from app.db.models.match import Match
from app.db.models.player import Player
from app.service.riot import (
    apply_rank,
    apply_summoner,
    copy_timeline_fields,
    match_to_participant,
    participant_to_match,
    player_ref,
)

# Aún no existen como columnas en la tabla ancha match_data (llegan en la Fase 2).
NOT_PERSISTED = {"puuid", "participant_id", "team_id", "queue_id", "game_version"}


def _stats(**overrides) -> ParticipantStats:
    values = dict(
        match_id="EUW1_1",
        creation_time=datetime(2026, 5, 1, tzinfo=timezone.utc),
        duration=1800,
        champion="Ahri",
        player_role="MID",
        kills=7,
        death_events=[{"x": 1, "y": 2, "time": 300, "assistingParticipantIds": []}],
        quest_completion_time=600,
        timeline_enriched=True,
    )
    values.update(overrides)
    return ParticipantStats(**values)


def test_participant_survives_roundtrip_through_orm():
    original = _stats()
    back = match_to_participant(participant_to_match(original))
    for f in fields(ParticipantStats):
        if f.name not in NOT_PERSISTED:
            assert getattr(back, f.name) == getattr(original, f.name), f.name


def test_null_columns_take_domain_defaults():
    row = Match(match_id="EUW1_2", creation_time=datetime.now(timezone.utc), champion="Zed", win=False, duration=1500)
    stats = match_to_participant(row)
    assert (stats.kills, stats.death_events, stats.player_role) == (0, [], "UNKNOWN")
    assert stats.fullclear_time is None


def test_copy_timeline_fields_refreshes_existing_row():
    row = participant_to_match(_stats(timeline_enriched=False, gold_diff_14=0))
    copy_timeline_fields(row, _stats(gold_diff_14=321, fullclear_time=290))
    assert (row.gold_diff_14, row.fullclear_time, row.timeline_enriched) == (321, 290, True)


def test_rank_and_summoner_are_applied_to_player():
    player = Player(game_name="Faker", tag_line="KR1", puuid="p", region="kr")
    assert apply_rank(player, None) is False
    assert apply_rank(player, RankInfo("CHALLENGER", "I", 1500, 300, 200)) is True
    apply_summoner(player, SummonerInfo(29))
    assert (player.tier, player.lp, player.wins, player.profile_icon_id) == ("CHALLENGER", 1500, 300, 29)
    assert player_ref(player).label == "Faker#KR1"
