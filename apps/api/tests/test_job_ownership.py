"""Regresión del bug P2: el estado de un job solo lo ve quien lo lanzó."""

from fastapi.testclient import TestClient

from app.db.models.job import Job
from main import app
from tests.helpers import unique

client = TestClient(app)


def _register() -> tuple[dict[str, str], int]:
    name = unique("jobs")
    token = client.post(
        "/auth/register",
        json={"email": f"{name}@example.com", "username": name, "password": "password123"},
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    return headers, client.get("/auth/me", headers=headers).json()["id"]


def test_job_status_is_only_visible_to_its_owner(db_session):
    owner_headers, owner_id = _register()
    stranger_headers, _ = _register()
    job_id = unique("job")
    db_session.add(Job(job_id=job_id, user_id=owner_id, status="processing", progress=40))
    db_session.commit()

    assert client.get(f"/snapshots/jobs/{job_id}", headers=stranger_headers).status_code == 404

    response = client.get(f"/snapshots/jobs/{job_id}", headers=owner_headers)
    assert response.status_code == 200
    assert response.json()["progress"] == 40


def test_jobs_without_owner_are_not_exposed(db_session):
    headers, _ = _register()
    job_id = unique("legacy-job")
    db_session.add(Job(job_id=job_id, status="done", progress=100))
    db_session.commit()

    assert client.get(f"/snapshots/jobs/{job_id}", headers=headers).status_code == 404
