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


async def test_a_user_links_several_accounts_up_to_a_limit(db, auth_headers, monkeypatch):
    """The main one and a smurf or two, each verified with its icon: up to MAX_ACCOUNTS, and the limit is stated before
    spending Riot calls."""
    from app.db.models.user import User
    from app.routers import players
    from tests.helpers import create_player

    user_id = client.get("/auth/me", headers=auth_headers).json()["id"]
    for _ in range(players.MAX_ACCOUNTS):
        await create_player(db, user=await db.get(User, user_id))
    assert len(client.get("/players/", headers=auth_headers).json()["items"]) == players.MAX_ACCOUNTS

    async def riot(*args, **kwargs):
        raise AssertionError("must not get as far as asking Riot")

    monkeypatch.setattr(players, "create_player", riot)
    r = client.post("/players/", headers=auth_headers, json={"game_name": "Other", "tag_line": "EUW", "region": "euw"})
    assert r.status_code == 409 and r.json()["detail"] == f"You can link up to {players.MAX_ACCOUNTS} accounts."



async def test_an_account_is_verified_with_the_profile_icon_asked(db, auth_headers, monkeypatch):
    """Linking is not enough: the requested icon must be put on in the client, and Riot has to see it set. Only
    whoever has the account can do it, and a LoL account is verified by a single YGG user."""
    from app.crud.player import verification_icon
    from app.db.models.user import User
    from app.routers import players
    from tests.helpers import create_player

    assert all(verification_icon(5) != 5 and 1 <= verification_icon(5) < 29 for _ in range(200))
    user_id = client.get("/auth/me", headers=auth_headers).json()["id"]
    mine = await create_player(db, user=await db.get(User, user_id))
    mine.verified_at, mine.verify_icon = None, 7
    await db.commit()
    icon = {"now": 3}

    async def current_icon(player):
        return icon["now"]

    monkeypatch.setattr(players, "current_icon", current_icon)
    body = client.get(f"/players/{mine.id}", headers=auth_headers).json()
    assert (body["verified"], body["verify_icon"]) == (False, 7)
    wrong = client.post(f"/players/{mine.id}/verify", headers=auth_headers)
    assert wrong.status_code == 409 and "isn't the one shown" in wrong.json()["detail"]

    icon["now"] = 7
    body = client.post(f"/players/{mine.id}/verify", headers=auth_headers).json()
    assert (body["verified"], body["verify_icon"], body["profile_icon_id"]) == (True, None, 7)

    # another user who linked the same account can no longer verify it, even if the icon matches
    other = await create_player(db, puuid=mine.puuid)
    other.verified_at, other.verify_icon = None, 7
    await db.commit()
    from app.auth.jwt import create_access_token  # the owner of `other` has no password: a direct token

    headers = {"Authorization": f"Bearer {create_access_token(other.user_id)}"}
    taken = client.post(f"/players/{other.id}/verify", headers=headers)
    assert taken.status_code == 409 and "another YGG user" in taken.json()["detail"]
