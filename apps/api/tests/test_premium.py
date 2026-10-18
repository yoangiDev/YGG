"""Replay analysis: who can request it, since when, and that it puts together the replays you keep uploading."""

from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update

from app.core.config import settings
from app.db.models.job import Job
from app.db.models.premium_analysis import PremiumAnalysis
from app.db.models.snapshot import Snapshot
from app.db.models.user import User
from app.jobs.queue import get_job_queue
from app.jobs.worker import run_analysis
from app.service import premium
from main import app
from app.crud.participants import link_snapshot, upsert_participants
from app.db.models.game_analysis import GameAnalysis
from tests.helpers import create_player, create_snapshot, make_stats, unique

client = TestClient(app)

SINCE = int(settings.premium_since.timestamp())
COVERED = {"date_from": SINCE + 86_400, "date_to": SINCE + 10 * 86_400}


class FakeQueue:
    def __init__(self):
        self.analyses: list[str] = []

    async def enqueue_analysis(self, job_id: str) -> None:
        self.analyses.append(job_id)


@pytest.fixture
def queue():
    fake = FakeQueue()
    app.dependency_overrides[get_job_queue] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_job_queue, None)


async def _user(db, role: str = "user"):
    name = unique("premium")
    token = client.post(
        "/auth/register", json={"email": f"{name}@example.com", "username": name, "password": "password123"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    user_id = client.get("/auth/me", headers=headers).json()["id"]
    await db.execute(update(User).where(User.id == user_id).values(role=role))
    await db.commit()
    player = await create_player(db, user=await db.get(User, user_id))
    return headers, player


async def _covered_snapshot(db, player) -> Snapshot:
    snapshot = await create_snapshot(db, player)
    snapshot.date_from = datetime.fromtimestamp(COVERED["date_from"], UTC)
    snapshot.date_to = datetime.fromtimestamp(COVERED["date_to"], UTC)
    await db.commit()
    return snapshot


async def test_only_premium_accounts_can_ask_for_a_premium_snapshot(db, queue):
    headers, player = await _user(db)
    response = client.post("/snapshots/", json={"player_id": player.id, "premium": True, **COVERED}, headers=headers)
    assert (response.status_code, response.json()["detail"]) == (403, "premium_required")
    assert queue.analyses == []


async def test_a_premium_snapshot_cannot_start_before_coverage(db, queue):
    headers, player = await _user(db, "premium")
    body = {"player_id": player.id, "premium": True, "date_from": SINCE - 86_400, "date_to": SINCE + 86_400}
    assert client.post("/snapshots/", json=body, headers=headers).status_code == 400
    # without premium, the same period is valid: the limit applies only to the replay analysis
    assert client.post("/snapshots/", json={**body, "premium": False}, headers=headers).status_code == 202


async def test_a_premium_snapshot_keeps_its_flag_on_the_job(db, queue):
    headers, player = await _user(db, "premium")
    response = client.post("/snapshots/", json={"player_id": player.id, "premium": True, **COVERED}, headers=headers)
    assert response.status_code == 202
    job = await db.get(Job, response.json()["job_id"])
    assert job is not None and job.premium


async def test_coverage_says_since_when(db):
    headers, _player = await _user(db)
    assert client.get("/snapshots/premium/coverage", headers=headers).json() == {"since": SINCE}


async def test_reading_or_starting_a_premium_analysis_needs_premium(db, queue):
    headers, player = await _user(db)
    snapshot = await _covered_snapshot(db, player)
    assert client.get(f"/snapshots/{snapshot.id}/premium", headers=headers).status_code == 403
    assert client.post(f"/snapshots/{snapshot.id}/premium", headers=headers).status_code == 403


async def test_the_premium_analysis_waits_for_its_replays_and_joins_them(db, queue, monkeypatch):
    """Since 16.20: the snapshot's matches stay requested until you upload their replays; those already analysed aren't
    requested again, and when none is left pending the result is put together, with the ones that failed in `missing`."""
    monkeypatch.setattr(premium.replays, "summarize", lambda games, tier: {"games": len(games)})

    async def review(summary, games):
        return {"text": "ok"}

    monkeypatch.setattr(premium, "write_review", review)
    headers, player = await _user(db, "premium")
    snapshot = await _covered_snapshot(db, player)
    done, asked = unique("EUW1"), unique("EUW1")
    ids = await upsert_participants(db, [make_stats(done, player.puuid), make_stats(asked, player.puuid)])
    await link_snapshot(db, snapshot.id, ids.values())
    db.add(GameAnalysis(user_id=player.user_id, match_id=done, status="done",
                        result={"games": [{"match_id": done, "champion": "Ahri"}]}))
    await db.commit()
    url = f"/snapshots/{snapshot.id}/premium"
    assert client.get(url, headers=headers).status_code == 404

    started = client.post(url, headers=headers).json()
    assert (started["status"], started["progress"]) == ("processing", 45)
    assert [(w["match_id"], w["champion"]) for w in started["waiting"]] == [(asked, "Ahri")]

    # its replay can't be downloaded (from an earlier patch): it finishes with what there is
    body = client.post(f"{url}/skip", headers=headers).json()
    assert (body["status"], body["progress"], body["review"]) == ("done", 100, {"text": "ok"})
    assert body["result"]["summary"] == {"games": 1}
    assert [g["match_id"] for g in body["result"]["games"]] == [done] and body["result"]["games"][0]["played_at"]
    assert body["result"]["missing"] == {asked: "Its replay wasn't uploaded."}

    # again: the one that failed is requested again
    again = client.post(url, headers=headers).json()
    assert (again["status"], [w["match_id"] for w in again["waiting"]]) == ("processing", [asked])


async def test_the_worker_starts_the_premium_analysis_when_the_snapshot_is_done(db, queue):
    _headers, player = await _user(db, "premium")
    snapshot = await _covered_snapshot(db, player)
    job = Job(job_id=unique("job"), user_id=player.user_id, player_id=player.id, status="queued", premium=True, **COVERED)
    db.add(job)
    await db.commit()

    async def extraction(*_args, **_kwargs):
        return snapshot.id

    with patch("app.jobs.worker.run_stats_extraction", extraction), patch("app.jobs.worker.get_job_queue", lambda: queue):
        assert await run_analysis({"job_try": 1}, job.job_id) == snapshot.id

    analysis = await db.get(PremiumAnalysis, snapshot.id, populate_existing=True)
    # the test snapshot has no matches: it is attempted, and says why it doesn't come out
    assert analysis is not None and (analysis.status, analysis.error) == ("error", "This snapshot has no games to analyse.")
