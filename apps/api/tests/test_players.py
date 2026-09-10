import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


class TestPlayersAuth:
    def test_list_players_requires_auth(self):
        response = client.get("/players/")
        assert response.status_code == 403

    def test_get_player_requires_auth(self):
        response = client.get("/players/1")
        assert response.status_code == 403


class TestPlayersCRUD:
    def test_list_players_returns_empty_for_new_user(self, auth_headers):
        response = client.get("/players/", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_get_player_not_found(self, auth_headers):
        response = client.get("/players/99999", headers=auth_headers)
        assert response.status_code == 404

    def test_update_player_not_found(self, auth_headers):
        response = client.put(
            "/players/99999",
            headers=auth_headers,
            json={"game_name": "Test", "tag_line": "NA1", "role": "TOP", "nickname": "", "notes": ""}
        )
        assert response.status_code == 404

    def test_delete_player_not_found(self, auth_headers):
        response = client.delete("/players/99999", headers=auth_headers)
        assert response.status_code == 404

    def test_refresh_player_not_found(self, auth_headers):
        response = client.post("/players/99999/refresh", headers=auth_headers)
        assert response.status_code == 404
