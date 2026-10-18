"""Data Dragon endpoints (they query Riot's real network)."""

import re

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_get_version():
    response = client.get("/ddragon/version")
    assert response.status_code == 200
    # The real version changes with every patch; we only check the format.
    assert re.fullmatch(r"\d+\.\d+\.\d+", response.json())


def test_get_all_items():
    response = client.get("/ddragon/items")
    assert response.status_code == 200
    assert len(response.json()) > 0


def test_get_all_spells():
    response = client.get("/ddragon/spells")
    assert response.status_code == 200
    assert len(response.json()) > 0


def test_get_all_runes():
    response = client.get("/ddragon/runes")
    assert response.status_code == 200
    assert len(response.json()) > 0
