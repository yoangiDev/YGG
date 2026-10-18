"""Dashboard cache in Redis (P9)."""

from unittest.mock import AsyncMock, MagicMock, patch

from ygg_core.metrics.benchmarks import target

from app.crud.participants import link_snapshot, upsert_participants
from app.crud.player import update_player
from app.crud.snapshot import update_snapshot_notes
from app.db.models.player import RoleEnum
from app.db.models.snapshot import Snapshot
from app.schemas.player import PlayerUpdate, Role
from app.schemas.snapshot import SnapshotNotesUpdate
from app.service.dashboard import get_snapshot_dashboard
from app.service.dashboard_cache import get_cached_dashboard, invalidate_dashboards_for_participants
from tests.helpers import create_player, create_snapshot, make_stats, unique


async def _add_matches(db, snapshot, player, *champions) -> list[int]:
    ids = await upsert_participants(db, [make_stats(unique("EUW1"), player.puuid, champion=c) for c in champions])
    await link_snapshot(db, snapshot.id, ids.values())
    await db.commit()
    return list(ids.values())


async def _snapshot_with(db, *champions):
    player = await create_player(db, role=RoleEnum.MID)
    snapshot = await create_snapshot(db, player)
    await _add_matches(db, snapshot, player, *champions)
    return player, snapshot


async def test_dashboard_is_cached_and_invalidated_when_its_matches_change(db):
    player, snapshot = await _snapshot_with(db, "Ahri")

    first = await get_snapshot_dashboard(db, snapshot)
    assert await get_cached_dashboard(snapshot.id) == first

    new_ids = await _add_matches(db, snapshot, player, "Zed")
    await invalidate_dashboards_for_participants(db, new_ids)
    assert await get_cached_dashboard(snapshot.id) is None

    second = await get_snapshot_dashboard(db, snapshot)
    assert (first.games_played, second.games_played) == (1, 2)
    assert {c.champion_name for c in second.played_champions} == {"Ahri", "Zed"}


async def test_cached_dashboard_does_not_touch_the_database(db):
    _, snapshot = await _snapshot_with(db, "Ahri")
    await get_snapshot_dashboard(db, snapshot)

    with patch("app.service.dashboard.participants_for_snapshot", AsyncMock(side_effect=AssertionError("no DB"))):
        cached = await get_snapshot_dashboard(db, snapshot)
    assert cached.games_played == 1


def _riot_with(participants):
    client = MagicMock()
    client.get_puuid = AsyncMock(return_value="compare-puuid")
    client.fetch_participants = AsyncMock(return_value=participants)
    return client, patch("app.service.dashboard.riot_client", return_value=client)


async def test_comparison_uses_the_snapshot_period_and_its_game_count_up_to_the_limit(db):
    _, snapshot = await _snapshot_with(db, "Ahri", "Zed")
    client, riot = _riot_with([make_stats(unique("KR"), "compare-puuid", champion="Azir")])

    with riot, patch("app.service.dashboard.create_secure_session"):
        dashboard = await get_snapshot_dashboard(db, snapshot, "Faker", "KR1", "kr")
        same_sample = client.fetch_participants.await_args.kwargs
        with patch("app.service.dashboard.COMPARE_MAX_MATCHES", 1):
            await get_snapshot_dashboard(db, snapshot, "Faker", "KR1", "kr")
        capped = client.fetch_participants.await_args.kwargs

    period = (int(snapshot.date_from.timestamp()), int(snapshot.date_to.timestamp()))
    assert (same_sample["start_t"], same_sample["end_t"], same_sample["max_matches"]) == (*period, 2)
    assert capped["max_matches"] == 1
    assert list(dashboard.radar_data.pro_datasets) == ["Faker#KR1"]


async def test_comparison_without_games_in_the_period_is_left_out(db):
    _, snapshot = await _snapshot_with(db, "Ahri")
    _, riot = _riot_with([])

    with riot, patch("app.service.dashboard.create_secure_session"):
        dashboard = await get_snapshot_dashboard(db, snapshot, "Faker", "KR1", "kr")

    assert dashboard.radar_data.pro_datasets == {}


async def test_changing_the_target_rank_invalidates_and_rescales_the_dashboard(db):
    player, snapshot = await _snapshot_with(db, "Ahri")
    first = await get_snapshot_dashboard(db, snapshot)

    await update_player(db, player, PlayerUpdate(game_name=player.game_name, tag_line="EUW", role=Role.MID, target_rank="EMERALD"))
    assert await get_cached_dashboard(snapshot.id) is None

    snapshot = await db.get(Snapshot, snapshot.id, populate_existing=True)
    second = await get_snapshot_dashboard(db, snapshot)
    cs = lambda dashboard: next(m.threshold for m in dashboard.role_averages if m.key == "cs_min")  # noqa: E731
    assert (first.target_rank, second.target_rank) == ("CHALLENGER", "EMERALD")
    # The target is the measured 65th percentile of each league: better than two out of three matches.
    goal = lambda rank: round(target(rank, "MID", "cs_per_min"), 2)  # noqa: E731
    assert (cs(first), cs(second)) == (goal("CHALLENGER"), goal("EMERALD"))
    assert cs(first) > cs(second)


async def test_editing_notes_invalidates_the_cache(db):
    _, snapshot = await _snapshot_with(db, "Ahri")
    await get_snapshot_dashboard(db, snapshot)

    await update_snapshot_notes(db, snapshot, SnapshotNotesUpdate(notes="Review vision"))

    assert await get_cached_dashboard(snapshot.id) is None
