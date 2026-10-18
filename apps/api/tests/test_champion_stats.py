"""Per-champion stats: adds up history and analysis without counting a match twice."""

from app.crud.participants import add_history_entries, link_snapshot, upsert_participants
from app.crud.player import champion_stats
from app.schemas.match import PlayerChampionStats
from tests.helpers import create_player, create_snapshot, make_stats, unique


async def test_champion_stats_merge_history_and_snapshots(db):
    player = await create_player(db)
    snapshot = await create_snapshot(db, player)
    games = [
        make_stats(unique("EUW1"), player.puuid, champion="Ahri", win=True, kills=5, deaths=2, assists=7,
                   total_cs=180, duration=1800, damage=27_000, vision=30),
        make_stats(unique("EUW1"), player.puuid, champion="Ahri", win=False, kills=1, deaths=4, assists=3,
                   total_cs=240, duration=2400, damage=24_000, vision=20),        make_stats(unique("EUW1"), player.puuid, champion="Syndra", win=True, kills=8, deaths=0, assists=2,
                   total_cs=200, duration=1200, damage=18_000, vision=10),
    ]
    ids = await upsert_participants(db, games)
    first, second, third = (ids[(g.match_id, g.puuid)] for g in games)
    await add_history_entries(db, player.id, [first, second])
    await link_snapshot(db, snapshot.id, [second, third])  # `second` is in both: counts once
    await db.commit()

    rows = await champion_stats(db, player.id)

    assert [(row["champion_name"], row["games"]) for row in rows] == [("Ahri", 2), ("Syndra", 1)]
    ahri, syndra = rows
    stats = PlayerChampionStats.model_validate(dict(ahri))
    # Against Challenger mid matches (their role with Ahri): 6.0 CS/min is weak and 729 damage/min, normal
    # (the typical match is around 778; the target, the 65th percentile, higher). The KDA of 2.67 doesn't reach 3: grey.
    assert (stats.role, stats.cs_status, stats.dmg_status, stats.kda_status) == ("MID", "bad", "normal", "bad")
    assert (ahri["wins"], ahri["losses"], float(ahri["win_rate"])) == (1, 1, 50.0)
    assert (float(ahri["kills"]), float(ahri["deaths"]), float(ahri["assists"])) == (3.0, 3.0, 5.0)
    assert float(ahri["kda"]) == round((5 + 7 + 1 + 3) / (2 + 4), 2)
    assert float(ahri["cs_per_min"]) == 6.0  # 420 CS in 70 minutes
    assert float(ahri["dmg_per_min"]) == 729  # 51,000 damage in 70 minutes
    assert float(ahri["vision_score"]) == 25.0
    assert float(syndra["kda"]) == 10.0  # no deaths: divided by 1

    assert len(await champion_stats(db, player.id, limit=1)) == 1


async def test_champion_stats_of_a_player_without_games(db):
    player = await create_player(db)
    assert await champion_stats(db, player.id) == []
