"""Regression of bug P1.

Before, `match_data.match_id` was unique and the row stored the stats of the
first player analysed. If another registered player was in the same
match, their snapshot reused that row and showed the first one's champion, KDA and
differentials.
"""

from unittest.mock import MagicMock, patch

from sqlalchemy import func, select

from app.crud.participants import participants_for_snapshot
from app.db.models.participant import MatchParticipant
from app.db.models.player import RoleEnum
from app.db.models.snapshot import Snapshot
from app.service.dashboard import build_snapshot_dashboard
from app.service.stats_runner import run_stats_extraction
from tests.helpers import create_player, make_stats, unique


class FakeRiotClient:
    """Returns for each player their stats in a single shared match."""

    def __init__(self, match_id, stats_by_puuid):
        self.match_id = match_id
        self.stats_by_puuid = stats_by_puuid
        self.known_by_puuid = {}

    async def fetch_match_ids(self, session, puuid, start_t, end_t, max_matches=None):
        return [self.match_id]

    async def fetch_participants(self, session, player, **kwargs):
        self.known_by_puuid[player.puuid] = dict(kwargs.get("known") or {})
        return [self.stats_by_puuid[player.puuid]]


async def _analyse(db, fake, *players) -> list[int]:
    with patch("app.service.stats_runner.riot_client", return_value=fake), patch(
        "app.service.stats_runner.create_secure_session", MagicMock()
    ):
        return [await run_stats_extraction(db, player, 1_748_000_000, 1_749_000_000) for player in players]


async def test_each_player_sees_their_own_stats_in_a_shared_match(db):
    match_id = unique("EUW1")
    top = await create_player(db, role=RoleEnum.TOP)
    jungle = await create_player(db, role=RoleEnum.JUNGLE)
    fake = FakeRiotClient(
        match_id,
        {
            top.puuid: make_stats(match_id, top.puuid, champion="Gnar", player_role="TOP", kills=3, gold_diff_14=-350),
            jungle.puuid: make_stats(match_id, jungle.puuid, champion="LeeSin", player_role="JUNGLE", kills=8, gold_diff_14=420),
        },
    )

    top_snapshot, jungle_snapshot = await _analyse(db, fake, top, jungle)

    # The second analysis does not receive the first player's row as a cache.
    assert fake.known_by_puuid[jungle.puuid] == {}

    [top_row] = await participants_for_snapshot(db, top_snapshot)
    [jungle_row] = await participants_for_snapshot(db, jungle_snapshot)
    assert (top_row.champion, top_row.kills, top_row.gold_diff_14) == ("Gnar", 3, -350)
    assert (jungle_row.champion, jungle_row.kills, jungle_row.gold_diff_14) == ("LeeSin", 8, 420)
    assert top_row.match_id == jungle_row.match_id
    count = select(func.count()).select_from(MatchParticipant).where(MatchParticipant.match_id == match_id)
    assert await db.scalar(count) == 2

    top_dashboard = await build_snapshot_dashboard(db, await db.get(Snapshot, top_snapshot, populate_existing=True))
    jungle_dashboard = await build_snapshot_dashboard(db, await db.get(Snapshot, jungle_snapshot, populate_existing=True))

    assert (top_dashboard.active_role, [c.champion_name for c in top_dashboard.played_champions]) == ("TOP", ["Gnar"])
    assert (jungle_dashboard.active_role, [c.champion_name for c in jungle_dashboard.played_champions]) == (
        "JUNGLE",
        ["LeeSin"],
    )


async def test_a_player_reuses_their_own_cached_row(db):
    match_id = unique("EUW1")
    player = await create_player(db, role=RoleEnum.MID)
    fake = FakeRiotClient(match_id, {player.puuid: make_stats(match_id, player.puuid)})

    await _analyse(db, fake, player)
    await _analyse(db, fake, player)

    assert set(fake.known_by_puuid[player.puuid]) == {match_id}
