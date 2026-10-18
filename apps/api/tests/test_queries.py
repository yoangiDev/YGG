"""The hand-written SQL computes the same as ygg-core's formulas."""

from app.crud.participants import upsert_participants
from app.crud.player import role_summary
from tests.helpers import create_player, make_stats, unique


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
