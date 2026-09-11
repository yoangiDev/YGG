"""Modelo partida / participante y sus enlaces N:M."""

from sqlalchemy import delete, func, select

from app.crud.participants import link_snapshot, replace_history, upsert_participants
from app.crud.snapshot import get_matches_by_snapshot
from app.db.models.match import Match
from app.db.models.participant import MatchParticipant
from app.db.models.player_history import PlayerHistoryEntry
from app.db.models.snapshot_participant import SnapshotParticipant
from tests.helpers import create_player, create_snapshot, create_user, make_stats, unique


async def _count(db, stmt) -> int:
    return await db.scalar(select(func.count()).select_from(stmt.subquery()))


async def _row(db, participant_id: int) -> MatchParticipant:
    return await db.get(MatchParticipant, participant_id, populate_existing=True)


class TestUpsert:
    async def test_is_idempotent_and_updates_stats(self, db):
        match_id, puuid = unique("EUW1"), unique("puuid")
        first = await upsert_participants(db, [make_stats(match_id, puuid, kills=5)])
        second = await upsert_participants(db, [make_stats(match_id, puuid, kills=9)])
        await db.commit()

        assert first == second
        row = await _row(db, first[(match_id, puuid)])
        assert (row.kills, row.duration) == (9, 1800)
        assert await _count(db, select(Match).where(Match.match_id == match_id)) == 1

    async def test_download_without_timeline_does_not_erase_timeline_metrics(self, db):
        match_id, puuid = unique("EUW1"), unique("puuid")
        ids = await upsert_participants(db, [make_stats(match_id, puuid, gold_diff_14=420)])
        await upsert_participants(db, [make_stats(match_id, puuid, gold_diff_14=0, timeline_enriched=False)])
        await db.commit()

        row = await _row(db, ids[(match_id, puuid)])
        assert (row.gold_diff_14, row.timeline_enriched) == (420, True)

    async def test_two_players_in_the_same_match_get_separate_rows(self, db):
        match_id = unique("EUW1")
        ids = await upsert_participants(
            db,
            [
                make_stats(match_id, "puuid-top", champion="Gnar", player_role="TOP"),
                make_stats(match_id, "puuid-jungle", champion="LeeSin", player_role="JUNGLE"),
            ],
        )
        await db.commit()

        assert len(set(ids.values())) == 2
        champions = (
            await db.scalars(
                select(MatchParticipant.champion)
                .where(MatchParticipant.match_id == match_id)
                .order_by(MatchParticipant.champion)
            )
        ).all()
        assert champions == ["Gnar", "LeeSin"]
        assert await _count(db, select(Match).where(Match.match_id == match_id)) == 1


class TestLinks:
    async def test_linking_twice_does_not_duplicate(self, db):
        player = await create_player(db)
        snapshot = await create_snapshot(db, player)
        ids = await upsert_participants(db, [make_stats(unique("EUW1"), player.puuid)])
        await link_snapshot(db, snapshot.id, ids.values())
        await link_snapshot(db, snapshot.id, ids.values())
        await db.commit()

        await db.refresh(snapshot)
        assert snapshot.match_count == 1

    async def test_deleting_a_snapshot_keeps_the_participant(self, db):
        player = await create_player(db)
        snapshot = await create_snapshot(db, player)
        match_id = unique("EUW1")
        ids = await upsert_participants(db, [make_stats(match_id, player.puuid)])
        await link_snapshot(db, snapshot.id, ids.values())
        await db.commit()

        await db.delete(snapshot)
        await db.commit()

        participant_id = ids[(match_id, player.puuid)]
        assert await _row(db, participant_id) is not None
        links = select(SnapshotParticipant).where(SnapshotParticipant.match_participant_id == participant_id)
        assert await _count(db, links) == 0

    async def test_deleting_a_match_cascades_to_participants_and_links(self, db):
        player = await create_player(db)
        snapshot = await create_snapshot(db, player)
        match_id = unique("EUW1")
        ids = await upsert_participants(db, [make_stats(match_id, player.puuid)])
        await link_snapshot(db, snapshot.id, ids.values())
        await db.commit()

        await db.execute(delete(Match).where(Match.match_id == match_id))
        await db.commit()

        assert await _count(db, select(MatchParticipant).where(MatchParticipant.match_id == match_id)) == 0
        assert await _count(db, select(SnapshotParticipant).where(SnapshotParticipant.snapshot_id == snapshot.id)) == 0

    async def test_replace_history_keeps_exactly_the_new_set(self, db):
        player = await create_player(db)
        stats = [make_stats(unique("EUW1"), player.puuid) for _ in range(3)]
        ids = await upsert_participants(db, stats)
        first, second, third = (ids[(s.match_id, s.puuid)] for s in stats)

        await replace_history(db, player.id, [first, second])
        await replace_history(db, player.id, [second, third])
        await db.commit()

        stored = (
            await db.scalars(
                select(PlayerHistoryEntry.match_participant_id).where(PlayerHistoryEntry.player_id == player.id)
            )
        ).all()
        assert set(stored) == {second, third}

    async def test_snapshot_matches_are_scoped_to_the_owner(self, db):
        player = await create_player(db)
        snapshot = await create_snapshot(db, player)
        ids = await upsert_participants(db, [make_stats(unique("EUW1"), player.puuid)])
        await link_snapshot(db, snapshot.id, ids.values())
        await db.commit()

        assert len(await get_matches_by_snapshot(db, snapshot.id, player.user_id)) == 1
        stranger = await create_user(db)
        assert await get_matches_by_snapshot(db, snapshot.id, stranger.id) == []
