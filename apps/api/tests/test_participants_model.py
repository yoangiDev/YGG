"""Modelo partida / participante y sus enlaces N:M."""

from datetime import datetime, timezone

from sqlalchemy import delete, func, select

from app.crud.participants import link_snapshot, replace_history, upsert_participants
from app.crud.snapshot import get_matches_by_snapshot
from app.db.models.match import Match
from app.db.models.participant import MatchParticipant
from app.db.models.player_history import PlayerHistoryEntry
from app.db.models.snapshot import Snapshot
from app.db.models.snapshot_participant import SnapshotParticipant
from tests.helpers import create_player, create_user, make_stats, unique


def _snapshot(db, player) -> Snapshot:
    snapshot = Snapshot(
        player_id=player.id,
        date_from=datetime(2025, 5, 1, tzinfo=timezone.utc),
        date_to=datetime(2025, 7, 1, tzinfo=timezone.utc),
    )
    db.add(snapshot)
    db.commit()
    return snapshot


def _count(db, stmt) -> int:
    return db.scalar(select(func.count()).select_from(stmt.subquery()))


class TestUpsert:
    def test_is_idempotent_and_updates_stats(self, db_session):
        match_id, puuid = unique("EUW1"), unique("puuid")
        first = upsert_participants(db_session, [make_stats(match_id, puuid, kills=5)])
        second = upsert_participants(db_session, [make_stats(match_id, puuid, kills=9)])
        db_session.commit()

        assert first == second
        row = db_session.get(MatchParticipant, first[(match_id, puuid)])
        db_session.refresh(row)
        assert (row.kills, row.duration) == (9, 1800)
        assert _count(db_session, select(Match).where(Match.match_id == match_id)) == 1

    def test_download_without_timeline_does_not_erase_timeline_metrics(self, db_session):
        match_id, puuid = unique("EUW1"), unique("puuid")
        ids = upsert_participants(db_session, [make_stats(match_id, puuid, gold_diff_14=420)])
        upsert_participants(db_session, [make_stats(match_id, puuid, gold_diff_14=0, timeline_enriched=False)])
        db_session.commit()

        row = db_session.get(MatchParticipant, ids[(match_id, puuid)])
        db_session.refresh(row)
        assert (row.gold_diff_14, row.timeline_enriched) == (420, True)

    def test_two_players_in_the_same_match_get_separate_rows(self, db_session):
        match_id = unique("EUW1")
        ids = upsert_participants(
            db_session,
            [
                make_stats(match_id, "puuid-top", champion="Gnar", player_role="TOP"),
                make_stats(match_id, "puuid-jungle", champion="LeeSin", player_role="JUNGLE"),
            ],
        )
        db_session.commit()

        assert len(set(ids.values())) == 2
        champions = db_session.scalars(
            select(MatchParticipant.champion).where(MatchParticipant.match_id == match_id).order_by(MatchParticipant.champion)
        ).all()
        assert champions == ["Gnar", "LeeSin"]
        assert _count(db_session, select(Match).where(Match.match_id == match_id)) == 1


class TestLinks:
    def test_linking_twice_does_not_duplicate(self, db_session):
        player = create_player(db_session)
        snapshot = _snapshot(db_session, player)
        ids = upsert_participants(db_session, [make_stats(unique("EUW1"), player.puuid)])
        link_snapshot(db_session, snapshot.id, ids.values())
        link_snapshot(db_session, snapshot.id, ids.values())
        db_session.commit()

        db_session.refresh(snapshot)
        assert snapshot.match_count == 1

    def test_deleting_a_snapshot_keeps_the_participant(self, db_session):
        player = create_player(db_session)
        snapshot = _snapshot(db_session, player)
        match_id = unique("EUW1")
        ids = upsert_participants(db_session, [make_stats(match_id, player.puuid)])
        link_snapshot(db_session, snapshot.id, ids.values())
        db_session.commit()

        db_session.delete(snapshot)
        db_session.commit()

        participant_id = ids[(match_id, player.puuid)]
        assert db_session.get(MatchParticipant, participant_id) is not None
        assert _count(db_session, select(SnapshotParticipant).where(SnapshotParticipant.match_participant_id == participant_id)) == 0

    def test_deleting_a_match_cascades_to_participants_and_links(self, db_session):
        player = create_player(db_session)
        snapshot = _snapshot(db_session, player)
        match_id = unique("EUW1")
        ids = upsert_participants(db_session, [make_stats(match_id, player.puuid)])
        link_snapshot(db_session, snapshot.id, ids.values())
        db_session.commit()

        db_session.execute(delete(Match).where(Match.match_id == match_id))
        db_session.commit()

        assert _count(db_session, select(MatchParticipant).where(MatchParticipant.match_id == match_id)) == 0
        assert _count(db_session, select(SnapshotParticipant).where(SnapshotParticipant.snapshot_id == snapshot.id)) == 0

    def test_replace_history_keeps_exactly_the_new_set(self, db_session):
        player = create_player(db_session)
        stats = [make_stats(unique("EUW1"), player.puuid) for _ in range(3)]
        ids = upsert_participants(db_session, stats)
        first, second, third = (ids[(s.match_id, s.puuid)] for s in stats)

        replace_history(db_session, player.id, [first, second])
        replace_history(db_session, player.id, [second, third])
        db_session.commit()

        stored = db_session.scalars(
            select(PlayerHistoryEntry.match_participant_id).where(PlayerHistoryEntry.player_id == player.id)
        ).all()
        assert set(stored) == {second, third}

    def test_snapshot_matches_are_scoped_to_the_owner(self, db_session):
        player = create_player(db_session)
        snapshot = _snapshot(db_session, player)
        ids = upsert_participants(db_session, [make_stats(unique("EUW1"), player.puuid)])
        link_snapshot(db_session, snapshot.id, ids.values())
        db_session.commit()

        assert len(get_matches_by_snapshot(db_session, snapshot.id, player.user_id)) == 1
        assert get_matches_by_snapshot(db_session, snapshot.id, create_user(db_session).id) == []
