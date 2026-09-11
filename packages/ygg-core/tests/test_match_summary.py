from datetime import UTC, datetime

from factories import DURATION, GAME_CREATION_MS, MATCH_ID, make_match, puuid
from ygg_core.domain.match_summary import MatchSummary
from ygg_core.metrics.match_score import score_match
from ygg_core.riot.match_summary import parse_match_summary


def test_summarizes_both_teams_and_all_participants():
    summary = parse_match_summary(make_match())

    assert summary.match_id == MATCH_ID
    assert summary.creation_time == datetime.fromtimestamp(GAME_CREATION_MS / 1000 + DURATION, tz=UTC)
    assert [team.team_id for team in summary.teams] == [100, 200]
    assert [len(team.participants) for team in summary.teams] == [5, 5]
    blue, red = summary.teams
    assert (blue.win, red.win) == (True, False)
    # Objetivos del factory: 3 dragones, 4 larvas y 1 heraldo para el azul.
    assert (blue.dragons, blue.grubs, blue.heralds, blue.barons) == (3, 4, 1, 0)
    # Sin objetivo "champion" en el payload, las kills se suman desde los participantes.
    assert blue.kills == 20


def test_participant_build_and_stats():
    top = next(p for p in parse_match_summary(make_match()).participants() if p.puuid == puuid(1))

    assert (top.game_name, top.tag_line, top.champion, top.role) == ("Player01", "TEST", "Gnar", "TOP")
    assert (top.kills, top.deaths, top.assists, top.kda) == (3, 4, 4, 1.75)
    assert top.kill_participation == 35.0  # 7 de las 20 kills del equipo
    assert top.cs == 188
    assert top.damage_per_min == round(11_500 / (DURATION / 60), 1)
    assert top.items == (3031, 3006, 6672, 3036, 0, 0)
    assert (top.trinket, top.spells) == (3340, (4, 14))
    assert (top.keystone, top.secondary_tree) == (8112, 8300)


def test_ranks_players_with_one_mvp_and_one_ace():
    participants = parse_match_summary(make_match()).participants()

    assert all(0 <= p.score <= 100 for p in participants)
    assert sorted(p.placement for p in participants) == list(range(1, 11))
    mvp = [p for p in participants if p.badge == "MVP"]
    ace = [p for p in participants if p.badge == "ACE"]
    assert len(mvp) == 1 and mvp[0].win
    assert len(ace) == 1 and not ace[0].win
    assert min(p.placement for p in participants if p.win) == mvp[0].placement


def test_scores_are_recomputed_from_a_stored_summary():
    summary = parse_match_summary(make_match())
    stale = summary.to_dict()
    for team in stale["teams"]:
        for participant in team["participants"]:
            participant.update(score=0, placement=0, badge=None)

    assert score_match(MatchSummary.from_dict(stale)) == summary


def test_round_trips_through_json():
    summary = parse_match_summary(make_match())
    assert MatchSummary.from_dict(summary.to_dict()) == summary


def test_tolerates_missing_optional_fields():
    match = make_match(overrides={1: {"riotIdGameName": None, "summonerName": "OldName", "perks": {}}})
    top = next(p for p in parse_match_summary(match).participants() if p.puuid == puuid(1))
    assert (top.game_name, top.keystone, top.secondary_tree) == ("OldName", 0, 0)
