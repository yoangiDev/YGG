"""La cuenta sembrada debe poder recorrerse entera con DEMO_MODE activo y sin Riot API."""

from sqlalchemy import func, select

from app.core.config import settings
from app.db.models.player import Player
from app.db.models.snapshot import Snapshot
from app.service.demo_seed import DEMO_PLAYERS, seed_demo
from tests.helpers import unique

PASSWORD = "demo-password-for-tests"


async def test_seed_is_idempotent(db):
    email = f"{unique('demo')}@example.com"

    first = await seed_demo(db, email=email, password=PASSWORD)
    second = await seed_demo(db, email=email, password=PASSWORD)

    assert first.user_id == second.user_id
    assert second.players == len(DEMO_PLAYERS)
    players = await db.scalar(select(func.count()).select_from(Player).where(Player.user_id == second.user_id))
    snapshots = await db.scalar(
        select(func.count()).select_from(Snapshot).join(Player).where(Player.user_id == second.user_id)
    )
    assert players == len(DEMO_PLAYERS)
    assert snapshots == second.snapshots


async def test_seeded_demo_works_end_to_end_in_demo_mode(db, client, monkeypatch):
    email = f"{unique('demo')}@example.com"
    await seed_demo(db, email=email, password=PASSWORD)
    monkeypatch.setattr(settings, "demo_mode", True)

    login = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    players = client.get("/players/", headers=headers).json()
    assert players["total"] == len(DEMO_PLAYERS)
    mid = next(p for p in players["items"] if p["game_name"] == "Demo Mid")

    snapshots = client.get(f"/snapshots/player/{mid['id']}", headers=headers).json()["items"]
    assert sorted(s["match_count"] for s in snapshots) == [22, 26]
    latest = max(snapshots, key=lambda s: s["date_to"])

    dashboard = client.get(f"/snapshots/{latest['id']}/dashboard", headers=headers)
    assert dashboard.status_code == 200
    body = dashboard.json()
    assert body["games_played"] == 26
    assert body["role_averages"]
    assert body["radar_data"]["axes"]
    assert sum(body["deaths_by_phase"].values()) > 0

    matches = client.get(f"/matches/snapshot/{latest['id']}?limit=5", headers=headers).json()
    assert matches["total"] == 26
    assert matches["items"][0]["death_events_normalized"]

    # Lecturas que normalmente pueden llamar a Riot: en la demo salen de la base de datos.
    history = client.get(f"/matches/player/{mid['id']}?limit=10", headers=headers)
    assert history.status_code == 200
    assert len(history.json()) == 10
    assert client.get(f"/players/{mid['id']}/summary", headers=headers).json()
    assert client.get("/league/cutoffs?region=EUW", headers=headers).status_code == 200

    # Y nada se puede modificar.
    create = client.post(
        "/snapshots/",
        json={"player_id": mid["id"], "date_from": 1, "date_to": 2, "description": ""},
        headers=headers,
    )
    assert create.status_code == 403
