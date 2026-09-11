"""Estadísticas por campeón: suma historial y análisis sin contar dos veces una partida."""

from app.crud.participants import add_history_entries, link_snapshot, upsert_participants
from app.crud.player import champion_stats
from tests.helpers import create_player, create_snapshot, make_stats, unique


async def test_champion_stats_merge_history_and_snapshots(db):
    player = await create_player(db)
    snapshot = await create_snapshot(db, player)
    games = [
        make_stats(unique("EUW1"), player.puuid, champion="Ahri", win=True, kills=5, deaths=2, assists=7,
                   total_cs=180, duration=1800, damage=27_000, vision=30),
        make_stats(unique("EUW1"), player.puuid, champion="Ahri", win=False, kills=1, deaths=4, assists=3,
                   total_cs=240, duration=2400, damage=24_000, vision=20),
        make_stats(unique("EUW1"), player.puuid, champion="Syndra", win=True, kills=8, deaths=0, assists=2,
                   total_cs=200, duration=1200, damage=18_000, vision=10),
    ]
    ids = await upsert_participants(db, games)
    first, second, third = (ids[(g.match_id, g.puuid)] for g in games)
    await add_history_entries(db, player.id, [first, second])
    await link_snapshot(db, snapshot.id, [second, third])  # `second` está en los dos: cuenta una vez
    await db.commit()

    rows = await champion_stats(db, player.id)

    assert [(row["champion_name"], row["games"]) for row in rows] == [("Ahri", 2), ("Syndra", 1)]
    ahri, syndra = rows
    assert (ahri["wins"], ahri["losses"], float(ahri["win_rate"])) == (1, 1, 50.0)
    assert (float(ahri["kills"]), float(ahri["deaths"]), float(ahri["assists"])) == (3.0, 3.0, 5.0)
    assert float(ahri["kda"]) == round((5 + 7 + 1 + 3) / (2 + 4), 2)
    assert float(ahri["cs_per_min"]) == 6.0  # 420 CS en 70 minutos
    assert float(ahri["dmg_per_min"]) == 729  # 51 000 de daño en 70 minutos
    assert float(ahri["vision_score"]) == 25.0
    assert float(syndra["kda"]) == 10.0  # sin muertes: se divide entre 1

    assert len(await champion_stats(db, player.id, limit=1)) == 1


async def test_champion_stats_of_a_player_without_games(db):
    player = await create_player(db)
    assert await champion_stats(db, player.id) == []
