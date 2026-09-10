"""Análisis fuera del proceso de la API (P3): cola, worker, recuperación y SSE."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from arq import Retry
from fastapi.testclient import TestClient
from sqlalchemy import update
from ygg_core.riot.errors import RiotUnavailableError

from app.core.redis import get_redis
from app.db.models.job import Job
from app.db.models.user import User
from app.jobs.progress import job_channel, job_event_stream, publish_job_state
from app.jobs.queue import get_job_queue
from app.jobs.worker import INTERRUPTED_ERROR, recover_orphaned_jobs, run_analysis
from app.schemas.snapshot import SnapshotJobStatus
from main import app
from tests.helpers import create_player, create_snapshot, unique

client = TestClient(app)

PERIOD = {"date_from": 1_748_000_000, "date_to": 1_749_000_000}


class FakeQueue:
    def __init__(self):
        self.enqueued: list[str] = []

    async def enqueue_analysis(self, job_id: str) -> None:
        self.enqueued.append(job_id)


@pytest.fixture
def queue():
    fake = FakeQueue()
    app.dependency_overrides[get_job_queue] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_job_queue, None)


def _register() -> tuple[dict[str, str], int]:
    name = unique("jobs")
    token = client.post(
        "/auth/register", json={"email": f"{name}@example.com", "username": name, "password": "password123"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    return headers, client.get("/auth/me", headers=headers).json()["id"]


async def _user_with_player(db):
    headers, user_id = _register()
    player = await create_player(db, user=await db.get(User, user_id))
    return headers, player


async def _job(db, player, **overrides) -> Job:
    job = Job(job_id=unique("job"), user_id=player.user_id, player_id=player.id, status="queued", **PERIOD)
    for field, value in overrides.items():
        setattr(job, field, value)
    db.add(job)
    await db.commit()
    return job


async def _reload(db, job_id: str) -> Job:
    return await db.get(Job, job_id, populate_existing=True)


# ── API ────────────────────────────────────────────────────────────────────────

async def test_creating_a_snapshot_only_enqueues_a_job(db, queue):
    headers, player = await _user_with_player(db)

    response = client.post("/snapshots/", json={"player_id": player.id, **PERIOD}, headers=headers)

    assert response.status_code == 202
    job_id = response.json()["job_id"]
    assert queue.enqueued == [job_id]
    job = await _reload(db, job_id)
    assert (job.status, job.player_id, job.date_from, job.date_to) == ("queued", player.id, *PERIOD.values())


async def test_the_same_request_reuses_the_active_job(db, queue):
    headers, player = await _user_with_player(db)
    body = {"player_id": player.id, **PERIOD}

    first = client.post("/snapshots/", json=body, headers=headers).json()
    second = client.post("/snapshots/", json=body, headers=headers).json()

    assert first["job_id"] == second["job_id"]
    assert queue.enqueued == [first["job_id"]]


async def test_only_failed_jobs_can_be_retried(db, queue):
    headers, player = await _user_with_player(db)
    failed = await _job(db, player, status="error", error="boom", date_from=1, date_to=2)
    running = await _job(db, player, status="processing", date_from=3, date_to=4)

    response = client.post(f"/snapshots/jobs/{failed.job_id}/retry", headers=headers)

    assert response.status_code == 202
    assert (response.json()["status"], response.json()["error"]) == ("queued", None)
    assert queue.enqueued == [failed.job_id]
    assert client.post(f"/snapshots/jobs/{running.job_id}/retry", headers=headers).status_code == 409


async def test_stream_of_a_finished_job_sends_its_state_and_closes(db):
    headers, player = await _user_with_player(db)
    job = await _job(db, player, status="done", progress=100, snapshot_id=42)

    with client.stream("GET", f"/snapshots/jobs/{job.job_id}/stream", headers=headers) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join(response.iter_text())

    assert "event: done" in body
    assert '"snapshot_id":42' in body


async def test_stream_is_only_available_to_the_owner(db):
    _, player = await _user_with_player(db)
    job = await _job(db, player)
    stranger_headers, _ = _register()
    assert client.get(f"/snapshots/jobs/{job.job_id}/stream", headers=stranger_headers).status_code == 404


# ── Worker ─────────────────────────────────────────────────────────────────────

async def test_worker_runs_the_analysis_and_publishes_progress(db):
    player = await create_player(db)
    job = await _job(db, player)
    snapshot = await create_snapshot(db, player)
    pubsub = get_redis().pubsub()
    await pubsub.subscribe(job_channel(job.job_id))

    async def fake_extraction(session, analysed, date_from, date_to, description, on_progress=None):
        assert (analysed.id, date_from, date_to) == (player.id, *PERIOD.values())
        on_progress(40)
        await asyncio.sleep(0.05)
        return snapshot.id

    with patch("app.jobs.worker.run_stats_extraction", fake_extraction):
        assert await run_analysis({"job_try": 1}, job.job_id) == snapshot.id

    row = await _reload(db, job.job_id)
    assert (row.status, row.progress, row.snapshot_id, row.attempts) == ("done", 100, snapshot.id, 1)
    assert row.started_at is not None and row.finished_at is not None

    # get_message devuelve None también al leer la confirmación de suscripción:
    # se lee hasta ver el estado final, con un plazo máximo.
    published = []
    deadline = asyncio.get_running_loop().time() + 2
    while not published or published[-1]["status"] != "done":
        assert asyncio.get_running_loop().time() < deadline, published
        message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)
        if message is not None:
            published.append(json.loads(message["data"]))
    await pubsub.aclose()

    assert published[0]["status"] == "processing"
    assert any(state["progress"] == 40 for state in published)
    assert (published[-1]["progress"], published[-1]["snapshot_id"]) == (100, snapshot.id)


async def test_worker_records_failures(db):
    job = await _job(db, await create_player(db))
    failing = AsyncMock(side_effect=ValueError("No matches found for the selected period and role."))

    with patch("app.jobs.worker.run_stats_extraction", failing):
        assert await run_analysis({"job_try": 1}, job.job_id) is None

    row = await _reload(db, job.job_id)
    assert (row.status, row.error) == ("error", "No matches found for the selected period and role.")


async def test_riot_outages_are_retried_with_backoff_until_the_last_try(db):
    job = await _job(db, await create_player(db))
    outage = AsyncMock(side_effect=RiotUnavailableError("Riot API rate limit exceeded."))

    with patch("app.jobs.worker.run_stats_extraction", outage):
        with pytest.raises(Retry):
            await run_analysis({"job_try": 1}, job.job_id)
        assert (await _reload(db, job.job_id)).status == "queued"

        assert await run_analysis({"job_try": 3}, job.job_id) is None
    row = await _reload(db, job.job_id)
    assert (row.status, row.attempts) == ("error", 2)


async def test_orphaned_jobs_are_failed_and_lost_queued_jobs_requeued(db):
    stale = datetime.now(UTC) - timedelta(minutes=5)
    orphan = await _job(db, await create_player(db), status="processing", heartbeat_at=stale)
    alive = await _job(db, await create_player(db), status="processing", heartbeat_at=datetime.now(UTC))
    lost = await _job(db, await create_player(db))
    await db.execute(update(Job).where(Job.job_id == lost.job_id).values(updated_at=stale))
    await db.commit()
    fake = FakeQueue()

    failed, requeued = await recover_orphaned_jobs(fake)

    assert orphan.job_id in failed and alive.job_id not in failed
    assert lost.job_id in requeued and fake.enqueued.count(lost.job_id) == 1
    assert ((await _reload(db, orphan.job_id)).status, (await _reload(db, orphan.job_id)).error) == (
        "error",
        INTERRUPTED_ERROR,
    )
    assert (await _reload(db, alive.job_id)).status == "processing"


# ── SSE ────────────────────────────────────────────────────────────────────────

async def test_event_stream_sends_current_state_then_live_updates_until_done():
    job_id = unique("job")
    initial = SnapshotJobStatus(job_id=job_id, status="queued")
    events = []

    async def consume():
        async for event in job_event_stream(job_id, initial, AsyncMock(return_value=False), poll_timeout=0.1):
            events.append(event)

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.1)  # el cliente ya está suscrito
    await publish_job_state(initial.model_copy(update={"status": "processing", "progress": 50}))
    await publish_job_state(initial.model_copy(update={"status": "done", "progress": 100, "snapshot_id": 7}))
    await asyncio.wait_for(task, timeout=2)

    assert [(e.event, json.loads(e.data)["progress"]) for e in events] == [
        ("progress", 0),
        ("progress", 50),
        ("done", 100),
    ]


async def test_reconnecting_client_gets_the_latest_state_first():
    job_id = unique("job")
    await publish_job_state(SnapshotJobStatus(job_id=job_id, status="processing", progress=70))
    disconnect_after_first = AsyncMock(return_value=True)

    events = [
        event
        async for event in job_event_stream(
            job_id, SnapshotJobStatus(job_id=job_id, status="queued"), disconnect_after_first, poll_timeout=0.1
        )
    ]

    assert [json.loads(e.data)["progress"] for e in events] == [70]
