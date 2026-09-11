"""El SQL escrito a mano calcula lo mismo que las fórmulas de ygg-core."""

from ygg_core.metrics.radar import average, match_cs_min, match_kda

from app.crud.participants import link_snapshot, upsert_participants
from app.crud.player import role_summary
from app.crud.snapshot import snapshot_summary
from tests.helpers import create_player, create_snapshot, make_stats, unique

GAMES = [
    dict(kills=5, deaths=2, assists=7, total_cs=188, duration=1800, win=True, first_dragon=True),
    dict(kills=2, deaths=1, assists=3, total_cs=250, duration=2100, win=False, herald=True),
    dict(kills=4, deaths=4, assists=4, total_cs=300, duration=1500, win=True, void_grubs=True),
]


async def test_snapshot_summary_matches_core_formulas(db):
    player = await create_player(db)
    snapshot = await create_snapshot(db, player)
    stats = [make_stats(unique("EUW1"), player.puuid, **game) for game in GAMES]
    ids = await upsert_participants(db, stats)
    await link_snapshot(db, snapshot.id, ids.values())
    await db.commit()

    summary = await snapshot_summary(db, snapshot.id)

    assert summary["games_played"] == 3
    assert float(summary["avg_kda"]) == average(stats, match_kda) == 4.33
    assert float(summary["avg_cs_per_min"]) == average(stats, match_cs_min) == 8.47
    assert float(summary["winrate"]) == 66.7
    assert (summary["first_dragons"], summary["heralds"], summary["void_grubs"]) == (1, 1, 1)


async def test_snapshot_summary_of_an_empty_snapshot(db):
    snapshot = await create_snapshot(db, await create_player(db))
    summary = await snapshot_summary(db, snapshot.id)
    assert (summary["games_played"], float(summary["avg_kda"])) == (0, 0.0)


async def test_player_role_summary(db):
    player = await create_player(db)
    await upsert_participants(
        db,
        [
            make_stats(unique("EUW1"), player.puuid, player_role="MID", kills=6, deaths=2, assists=0),
            make_stats(unique("EUW1"), player.puuid, player_role="MID", kills=2, deaths=2, assists=2, win=False),
            make_stats(unique("EUW1"), player.puuid, player_role="TOP", gold_diff_14=-100),
        ],
    )
    await db.commit()

    rows = await role_summary(db, player.puuid)

    assert [(row["role"], row["games"]) for row in rows] == [("MID", 2), ("TOP", 1)]
    mid = rows[0]
    assert (float(mid["win_rate"]), float(mid["kda"]), float(mid["gold_diff_14"])) == (50.0, 2.5, 150.0)
