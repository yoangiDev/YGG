"""Bringing up to date the matches stored with an earlier timeline version."""

from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import select
from ygg_core.domain.participant import TIMELINE_VERSION

from app.crud.participants import upsert_participants
from app.db.models.participant import MatchParticipant
from app.service.timeline_refresh import MAX_CONSECUTIVE_FAILURES, refresh_outdated_timelines
from tests.helpers import make_stats, unique


def _riot(fetch_participant):
    client = MagicMock()
    client.fetch_participant = AsyncMock(side_effect=fetch_participant)
    return client, patch("app.service.timeline_refresh.riot_client", return_value=client)


async def test_outdated_rows_are_recomputed_and_current_ones_are_left_alone(db):
    puuid, outdated, current, demo = unique("puuid"), unique("EUW1"), unique("EUW1"), f"DEMO_{unique('MID')}"
    await upsert_participants(
        db,
        [
            make_stats(outdated, puuid, timeline_version=1),
            make_stats(current, puuid),
            make_stats(demo, puuid, timeline_version=1),  # the demo doesn't exist in Riot
        ],
    )
    await db.commit()

    async def fresh(_session, match_id, player_puuid):
        return make_stats(match_id, player_puuid, turret_plates=3, lane_visits=[{"lane": "TOP", "takedowns": 1}])

    client, riot = _riot(fresh)
    with riot, patch("app.service.timeline_refresh.create_secure_session"):
        updated = await refresh_outdated_timelines(db, puuid=puuid)

    assert updated == 1
    client.fetch_participant.assert_awaited_once()
    assert client.fetch_participant.await_args.args[1:] == (outdated, puuid)
    rows = {row.match_id: row for row in await db.scalars(select(MatchParticipant).where(MatchParticipant.puuid == puuid))}
    assert (rows[outdated].timeline_version, rows[outdated].turret_plates, rows[outdated].lane_visits[0]["lane"]) == (
        TIMELINE_VERSION,
        3,
        "TOP",
    )
    assert rows[current].turret_plates == 0


async def test_stops_when_riot_does_not_answer(db):
    puuid = unique("puuid")
    rows = [make_stats(unique("EUW1"), puuid, timeline_version=1) for _ in range(MAX_CONSECUTIVE_FAILURES + 2)]
    await upsert_participants(db, rows)
    await db.commit()

    client, riot = _riot(lambda *_: None)
    with riot, patch("app.service.timeline_refresh.create_secure_session"):
        updated = await refresh_outdated_timelines(db, puuid=puuid)

    assert updated == 0
    assert client.fetch_participant.await_count == MAX_CONSECUTIVE_FAILURES
