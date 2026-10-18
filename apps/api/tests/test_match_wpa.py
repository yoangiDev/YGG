"""WPA timeline of a snapshot's matches."""

from app.crud.participants import link_snapshot, upsert_participants
from app.db.models.user import User
from tests.helpers import create_player, create_snapshot, make_stats, unique

EVENTS = [
    {"time": 312, "kind": "KILL", "target": "Renekton", "wp_before": 51.2, "wp_after": 55.9, "wpa": 2.35,
     "team_wpa": 4.7, "share": 0.5, "shared_with": 2,
     "drivers": [{"factor": "dead", "change": 1.0, "wpa": 2.9}, {"factor": "gold_k", "change": 506.0, "wpa": 1.8}],
     "bounty": 300, "shutdown": 0, "gold_lost": None},
    {"time": 845, "kind": "DEATH", "target": "Viego", "wp_before": 62.0, "wp_after": 58.8, "wpa": -3.2,
     "team_wpa": -3.2, "share": 1.0, "shared_with": 1, "drivers": [{"factor": "dead", "change": -1.0, "wpa": -3.2}],
     "bounty": 300, "shutdown": 450, "gold_lost": [220, 320]},
]


async def test_a_snapshot_match_serves_its_grade_and_timeline(client, auth_headers, db):
    me = client.get("/auth/me", headers=auth_headers).json()
    player = await create_player(db, user=await db.get(User, me["id"]))
    snapshot = await create_snapshot(db, player)
    game = make_stats(unique("EUW1"), player.puuid, wpa_events=EVENTS, wp_curve=[50.0, 55.9], wpa_total=-0.1, wpa_grade=69)
    ids = await upsert_participants(db, [game])
    await link_snapshot(db, snapshot.id, ids.values())
    await db.commit()

    listed = client.get(f"/matches/snapshot/{snapshot.id}", headers=auth_headers).json()["items"]
    assert (listed[0]["wpa_grade"], listed[0]["wpa_total"]) == (69, -0.1)
    timeline = client.get(f"/matches/snapshot/{snapshot.id}/{game.match_id}/wpa", headers=auth_headers).json()
    assert timeline == {"match_id": game.match_id, "wpa_total": -0.1, "wpa_grade": 69, "wp_curve": [50.0, 55.9], "events": EVENTS}


async def test_the_timeline_of_someone_elses_snapshot_is_not_found(client, auth_headers, db):
    player = await create_player(db)  # of another user
    snapshot = await create_snapshot(db, player)
    game = make_stats(unique("EUW1"), player.puuid)
    ids = await upsert_participants(db, [game])
    await link_snapshot(db, snapshot.id, ids.values())
    await db.commit()

    assert client.get(f"/matches/snapshot/{snapshot.id}/{game.match_id}/wpa", headers=auth_headers).status_code == 404
