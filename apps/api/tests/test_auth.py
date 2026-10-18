from fastapi.testclient import TestClient

from main import app
from tests.helpers import unique

client = TestClient(app)


def _register(password: str = "password123", **overrides):
    name = unique("auth")
    payload = {"email": f"{name}@example.com", "username": name, "password": password, **overrides}
    return payload, client.post("/auth/register", json=payload)


class TestRoot:
    def test_root(self):
        response = client.get("/")
        assert response.status_code == 200
        assert response.json()["message"] == "YGG API"


class TestAuthRegister:
    def test_register_success(self):
        _, response = _register()
        assert response.status_code == 201
        body = response.json()
        assert body["access_token"]
        assert body["expires_in"] == 15 * 60

    def test_register_duplicate_email(self):
        payload, first = _register()
        assert first.status_code == 201
        response = client.post(
            "/auth/register",
            json={"email": payload["email"], "username": unique("other"), "password": "password123"},
        )
        assert response.status_code == 400

    def test_register_invalid_email(self):
        _, response = _register(email="not-an-email")
        assert response.status_code == 422

    def test_register_rejects_short_password(self):
        _, response = _register(password="short-pw")
        assert response.status_code == 422
        assert "at least 10 characters" in response.text

    def test_register_rejects_password_over_bcrypt_limit(self):
        _, response = _register(password="ñ" * 40)  # 80 bytes in UTF-8
        assert response.status_code == 422


class TestAuthLogin:
    def test_login_success(self):
        payload, _ = _register()
        response = client.post("/auth/login", json={"email": payload["email"], "password": payload["password"]})
        assert response.status_code == 200
        assert response.json()["access_token"]

    def test_login_wrong_password(self):
        payload, registered = _register()
        assert registered.status_code == 201
        response = client.post("/auth/login", json={"email": payload["email"], "password": "incorrect-password"})
        assert response.status_code == 401

    def test_login_nonexistent_user(self):
        response = client.post("/auth/login", json={"email": f"{unique('nobody')}@example.com", "password": "password"})
        assert response.status_code == 401


class TestCurrentUser:
    def test_me_requires_token(self):
        response = client.get("/auth/me")
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"

    def test_me_rejects_garbage_token(self):
        assert client.get("/auth/me", headers={"Authorization": "Bearer not-a-jwt"}).status_code == 401

    def test_me_returns_the_user(self, auth_headers):
        response = client.get("/auth/me", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["role"] == "user"


class TestDeleteAccount:
    def test_it_needs_the_password_and_then_deletes_everything_of_the_user(self):
        payload, response = _register()
        headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
        wrong = client.post("/auth/delete-account", json={"password": "not-it"}, headers=headers)
        assert (wrong.status_code, wrong.json()["detail"]) == (403, "Wrong password.")
        assert client.get("/auth/me", headers=headers).status_code == 200  # nothing was deleted

        assert client.post("/auth/delete-account", json={"password": payload["password"]}, headers=headers).status_code == 204
        assert client.get("/auth/me", headers=headers).status_code in (401, 404)
        assert client.post("/auth/login", json={"email": payload["email"], "password": payload["password"]}).status_code == 401
