from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


class TestPlayersAuth:
    def test_list_players_requires_auth(self):
        assert client.get("/players/").status_code == 401

    def test_get_player_requires_auth(self):
        assert client.get("/players/1").status_code == 401


class TestPlayersCRUD:
    def test_list_players_is_an_empty_page_for_a_new_user(self, auth_headers):
        response = client.get("/players/", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == {"items": [], "total": 0, "limit": 50, "offset": 0}

    def test_pagination_parameters_are_validated(self, auth_headers):
        assert client.get("/players/?limit=0", headers=auth_headers).status_code == 422
        assert client.get("/players/?limit=500", headers=auth_headers).status_code == 422

    def test_get_player_not_found(self, auth_headers):
        assert client.get("/players/99999", headers=auth_headers).status_code == 404

    def test_summary_not_found(self, auth_headers):
        assert client.get("/players/99999/summary", headers=auth_headers).status_code == 404

    def test_update_player_not_found(self, auth_headers):
        response = client.put(
            "/players/99999",
            headers=auth_headers,
            json={"game_name": "Test", "tag_line": "NA1", "role": "TOP", "nickname": "", "notes": ""},
        )
        assert response.status_code == 404

    def test_delete_player_not_found(self, auth_headers):
        assert client.delete("/players/99999", headers=auth_headers).status_code == 404

    def test_refresh_player_not_found(self, auth_headers):
        assert client.post("/players/99999/refresh", headers=auth_headers).status_code == 404
