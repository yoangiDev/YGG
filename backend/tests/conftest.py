import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import text
from main import app
from app.db.session import SessionLocal


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db_session() -> Session:
    """Create a test database session with automatic rollback."""
    db = SessionLocal()
    try:
        yield db
    finally:
        # Rollback any uncommitted changes
        db.rollback()
        db.close()


@pytest.fixture
def auth_token(client):
    import uuid
    unique = str(uuid.uuid4())[:8]
    client.post(
        "/auth/register",
        json={"email": f"pytest_{unique}@example.com", "username": f"user_{unique}", "password": "password123"}
    )
    response = client.post(
        "/auth/login",
        json={"email": f"pytest_{unique}@example.com", "password": "password123"}
    )
    return response.json()["access_token"]


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}
