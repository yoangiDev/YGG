import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


class TestHealth:
    def test_root(self):
        response = client.get("/")
        assert response.status_code == 200
        assert response.json()["message"] == "YGG API"

    def test_health(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


class TestAuthRegister:
    def test_register_success(self):
        import uuid
        unique = str(uuid.uuid4())[:8]
        response = client.post(
            "/auth/register",
            json={
                "email": f"test_{unique}@example.com",
                "username": f"user_{unique}",
                "password": "password123"
            }
        )
        assert response.status_code == 201
        assert "access_token" in response.json()

    def test_register_duplicate_email(self):
        import uuid
        unique = str(uuid.uuid4())[:8]
        email = f"dup_{unique}@example.com"
        # Usernames únicos por ejecución: con valores fijos el test dependía
        # del estado que dejaron ejecuciones anteriores en la misma base.
        first = client.post(
            "/auth/register",
            json={"email": email, "username": f"dup1_{unique}", "password": "pass123"}
        )
        assert first.status_code == 201
        response = client.post(
            "/auth/register",
            json={"email": email, "username": f"dup2_{unique}", "password": "pass123"}
        )
        assert response.status_code == 400

    def test_register_invalid_email(self):
        response = client.post(
            "/auth/register",
            json={"email": "not-an-email", "username": "user", "password": "pass123"}
        )
        assert response.status_code == 422


class TestAuthLogin:
    def test_login_success(self):
        import uuid
        unique = str(uuid.uuid4())[:8]
        email = f"login_{unique}@example.com"
        password = "password123"
        
        # Register first
        client.post(
            "/auth/register",
            json={"email": email, "username": f"user_{unique}", "password": password}
        )
        
        # Login
        response = client.post(
            "/auth/login",
            json={"email": email, "password": password}
        )
        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_login_wrong_password(self):
        import uuid
        unique = str(uuid.uuid4())[:8]
        email = f"wrongpass_{unique}@example.com"
        
        registered = client.post(
            "/auth/register",
            json={"email": email, "username": f"wrongpass_{unique}", "password": "correct"}
        )
        assert registered.status_code == 201
        response = client.post(
            "/auth/login",
            json={"email": email, "password": "incorrect"}
        )
        assert response.status_code == 401

    def test_login_nonexistent_user(self):
        response = client.post(
            "/auth/login",
            json={"email": "nouser@example.com", "password": "password"}
        )
        assert response.status_code == 401