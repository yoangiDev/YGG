"""DEMO_MODE: la demo pública es de solo lectura y nunca gasta cuota de la Riot API."""

import pytest

from app.core.config import settings
from app.core.middleware import DEMO_READ_ONLY, demo_blocks

ORIGIN = "http://localhost:5173"


@pytest.mark.parametrize(
    ("method", "path", "query", "blocked"),
    [
        ("GET", "/players/", b"", False),
        ("GET", "/snapshots/1/dashboard", b"", False),
        ("OPTIONS", "/players/", b"", False),
        ("POST", "/auth/login", b"", False),
        ("POST", "/auth/refresh", b"", False),
        ("POST", "/auth/logout/", b"", False),
        ("POST", "/auth/register", b"", True),
        ("POST", "/players/", b"", True),
        ("PUT", "/players/1", b"", True),
        ("DELETE", "/players/1", b"", True),
        ("PATCH", "/snapshots/1/notes", b"", True),
        ("POST", "/snapshots/", b"", True),
        ("GET", "/matches/player/1", b"limit=10&sync=true", True),
        ("GET", "/matches/player/1", b"live=1", True),
        ("GET", "/matches/player/1", b"sync=false", False),
        ("GET", "/league/cutoffs", b"region=EUW&refresh=true", True),
        ("GET", "/snapshots/1/dashboard", b"compare_game_name=Faker&compare_tag_line=KR1", True),
        ("GET", "/snapshots/1/dashboard", b"compare_game_name=", False),
    ],
)
def test_demo_blocks(method, path, query, blocked):
    assert demo_blocks(method, path, query) is blocked


@pytest.fixture
def demo(monkeypatch):
    monkeypatch.setattr(settings, "demo_mode", True)


def test_writes_are_rejected_with_a_cors_readable_403(client, demo):
    response = client.post(
        "/auth/register",
        json={"email": "new@example.com", "username": "newcomer", "password": "long-enough-password"},
        headers={"Origin": ORIGIN},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": DEMO_READ_ONLY}
    # Dentro de CORS: el navegador puede leer el motivo y enseñarlo.
    assert response.headers["access-control-allow-origin"] == ORIGIN


def test_riot_calls_are_rejected_before_authentication(client, demo):
    assert client.get("/league/cutoffs?region=EUW&refresh=true").status_code == 403


def test_reads_and_sign_in_keep_working(client, demo):
    assert client.get("/health/live").status_code == 200
    response = client.post("/auth/login", json={"email": "nobody@example.com", "password": "wrong-password"})
    assert response.status_code == 401


def test_demo_mode_is_off_by_default(client):
    # Llega a la validación de la ruta: el middleware no interviene.
    assert client.post("/auth/register", json={}).status_code == 422
