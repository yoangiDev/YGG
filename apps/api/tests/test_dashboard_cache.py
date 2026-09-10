"""Caché del dashboard en Redis (P9)."""

from unittest.mock import AsyncMock, MagicMock, patch

from app.crud.snapshot import persist_participants_to_snapshot, update_snapshot_notes
from app.db.models.player import RoleEnum
from app.schemas.snapshot import SnapshotNotesUpdate
from app.service.dashboard import get_snapshot_dashboard
from app.service.dashboard_cache import get_cached_dashboard
from tests.helpers import create_player, create_snapshot, make_stats, unique


def _ddragon():
    ddragon = MagicMock(version="16.10.1")
    ddragon.champion_icon_url.side_effect = lambda version, champion: f"{champion}.png"
    return patch("app.service.dashboard.get_ddragon_client", AsyncMock(return_value=ddragon))


async def _snapshot_with(db, *champions):
    player = await create_player(db, role=RoleEnum.MID)
    snapshot = await create_snapshot(db, player)
    await persist_participants_to_snapshot(
        db, snapshot, [make_stats(unique("EUW1"), player.puuid, champion=c) for c in champions]
    )
    return player, snapshot


async def test_dashboard_is_cached_and_invalidated_when_matches_are_added(db):
    player, snapshot = await _snapshot_with(db, "Ahri")

    with _ddragon():
        first = await get_snapshot_dashboard(db, snapshot)
        assert await get_cached_dashboard(snapshot.id) == first

        await persist_participants_to_snapshot(db, snapshot, [make_stats(unique("EUW1"), player.puuid, champion="Zed")])
        assert await get_cached_dashboard(snapshot.id) is None

        second = await get_snapshot_dashboard(db, snapshot)

    assert (first.games_played, second.games_played) == (1, 2)
    assert {c.champion_name for c in second.played_champions} == {"Ahri", "Zed"}


async def test_cached_dashboard_does_not_touch_the_database(db):
    _, snapshot = await _snapshot_with(db, "Ahri")
    with _ddragon():
        await get_snapshot_dashboard(db, snapshot)

    with patch("app.service.dashboard.participants_for_snapshot", AsyncMock(side_effect=AssertionError("sin BD"))):
        cached = await get_snapshot_dashboard(db, snapshot)
    assert cached.games_played == 1


async def test_editing_notes_invalidates_the_cache(db):
    _, snapshot = await _snapshot_with(db, "Ahri")
    with _ddragon():
        await get_snapshot_dashboard(db, snapshot)

    await update_snapshot_notes(db, snapshot, SnapshotNotesUpdate(notes="Revisar visión"))

    assert await get_cached_dashboard(snapshot.id) is None
