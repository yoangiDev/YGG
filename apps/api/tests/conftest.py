import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.session import SessionLocal
from main import app
from tests.helpers import unique


@pytest.fixture(autouse=True)
def _rate_limits_off(monkeypatch):
    """Todos los tests comparten IP ("testclient"): los límites solo se activan donde se prueban."""
    monkeypatch.setattr(settings, "rate_limit_enabled", False)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
async def db():
    async with SessionLocal() as session:
        yield session


@pytest.fixture
def auth_token(client):
    name = unique("pytest")
    response = client.post(
        "/auth/register",
        json={"email": f"{name}@example.com", "username": name, "password": "password123"},
    )
    return response.json()["access_token"]


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}
