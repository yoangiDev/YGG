"""Sesiones: access token corto + refresh token en cookie httpOnly con rotación (P5)."""

from datetime import UTC, datetime

import jwt
from fastapi.testclient import TestClient

from app.auth.jwt import create_access_token, decode_access_token
from app.core.config import settings
from main import app
from tests.helpers import unique

COOKIE = settings.refresh_cookie_name


def _new_session(password: str = "password123") -> tuple[TestClient, dict]:
    client = TestClient(app)
    name = unique("tok")
    payload = {"email": f"{name}@example.com", "username": name, "password": password}
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 201
    return client, payload


def _refresh_with(token: str):
    return TestClient(app).post("/auth/refresh", headers={"Cookie": f"{COOKIE}={token}"})


def test_register_sets_an_httponly_refresh_cookie_scoped_to_auth():
    client = TestClient(app)
    name = unique("tok")
    response = client.post(
        "/auth/register", json={"email": f"{name}@example.com", "username": name, "password": "password123"}
    )
    cookie = response.headers["set-cookie"].lower()
    assert f"{COOKIE}=" in cookie
    assert "httponly" in cookie
    assert "path=/auth" in cookie
    assert "samesite=lax" in cookie
    assert "refresh" not in response.json()  # el refresh token nunca va en el cuerpo


def test_refresh_rotates_the_cookie_and_issues_a_working_access_token():
    client, _ = _new_session()
    first = client.cookies.get(COOKIE)

    response = client.post("/auth/refresh")

    assert response.status_code == 200
    second = client.cookies.get(COOKIE)
    assert second and second != first
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {response.json()['access_token']}"})
    assert me.status_code == 200


def test_reusing_a_rotated_token_revokes_the_whole_session():
    client, _ = _new_session()
    stolen = client.cookies.get(COOKIE)
    assert client.post("/auth/refresh").status_code == 200
    legitimate = client.cookies.get(COOKIE)

    # Alguien presenta el token viejo: se detecta la reutilización…
    assert _refresh_with(stolen).status_code == 401
    # …y se revoca la familia, incluido el token vigente del usuario legítimo.
    assert _refresh_with(legitimate).status_code == 401


def test_refresh_without_cookie_is_rejected_and_clears_it():
    response = TestClient(app).post("/auth/refresh")
    assert response.status_code == 401
    assert f"{COOKIE}=" in response.headers.get("set-cookie", "")


def test_logout_revokes_the_refresh_token():
    client, _ = _new_session()
    token = client.cookies.get(COOKIE)
    assert client.post("/auth/logout").status_code == 204
    assert _refresh_with(token).status_code == 401


def test_password_change_enforces_policy_and_closes_other_sessions():
    client, payload = _new_session()
    other_device = client.cookies.get(COOKIE)
    access = client.post("/auth/login", json={"email": payload["email"], "password": payload["password"]}).json()
    headers = {"Authorization": f"Bearer {access['access_token']}"}

    too_short = client.patch(
        "/auth/me/password", json={"current_password": payload["password"], "new_password": "short"}, headers=headers
    )
    assert too_short.status_code == 422

    changed = client.patch(
        "/auth/me/password",
        json={"current_password": payload["password"], "new_password": "a-much-better-password"},
        headers=headers,
    )
    assert changed.status_code == 204
    assert _refresh_with(other_device).status_code == 401
    assert client.post("/auth/refresh").status_code == 200  # la sesión actual sigue viva
    login = TestClient(app).post(
        "/auth/login", json={"email": payload["email"], "password": "a-much-better-password"}
    )
    assert login.status_code == 200


def test_access_token_claims():
    now = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)
    token = create_access_token(42, now=now)
    claims = jwt.decode(
        token, settings.secret_key, algorithms=[settings.algorithm], options={"verify_exp": False}
    )
    assert (claims["sub"], claims["type"]) == ("42", "access")
    assert claims["exp"] - claims["iat"] == settings.access_token_expire_minutes * 60


def test_tokens_of_another_type_or_signature_are_rejected():
    now = datetime.now(UTC)
    wrong_type = jwt.encode(
        {"sub": "1", "type": "refresh", "iat": now, "exp": now.timestamp() + 60},
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    wrong_key = jwt.encode(
        {"sub": "1", "type": "access", "iat": now, "exp": now.timestamp() + 60},
        "otra-clave-de-firma-que-no-es-la-nuestra-en-absoluto",
        algorithm=settings.algorithm,
    )
    assert decode_access_token(wrong_type) is None
    assert decode_access_token(wrong_key) is None
