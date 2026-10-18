"""Job state: Postgres as the source of truth, Redis for real time.

Each change is published on the `jobs:<id>` channel and stored in `jobs:<id>:state`,
so that an SSE client that connects (or reconnects) first receives the
current state and then the live updates.
"""

import asyncio
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

import structlog
from redis.exceptions import RedisError
from sqlalchemy import update
from sse_starlette.sse import ServerSentEvent

from app.core.redis import get_redis
from app.db.models.job import Job
from app.db.session import SessionLocal
from app.schemas.snapshot import SnapshotJobStatus

logger = structlog.get_logger(__name__)

TERMINAL_STATUSES = frozenset({"done", "error"})
STATE_TTL_SECONDS = 24 * 3600
SSE_RETRY_MS = 3000


def job_channel(job_id: str) -> str:
    return f"jobs:{job_id}"


def job_state_key(job_id: str) -> str:
    return f"jobs:{job_id}:state"


def job_status_from_row(job: Job) -> SnapshotJobStatus:
    return SnapshotJobStatus(
        job_id=job.job_id,
        status=job.status,
        progress=job.progress or 0,
        snapshot_id=job.snapshot_id,
        error=job.error,
        attempts=job.attempts or 0,
    )


async def publish_job_state(state: SnapshotJobStatus) -> None:
    payload = state.model_dump_json()
    try:
        redis = get_redis()
        await redis.set(job_state_key(state.job_id), payload, ex=STATE_TTL_SECONDS)
        await redis.publish(job_channel(state.job_id), payload)
    except RedisError as exc:
        # Without Redis the live progress is lost, but the job and its state in Postgres are not.
        logger.warning("job_state_publish_failed", job_id=state.job_id, error=str(exc))


async def update_job(job_id: str, **values: Any) -> SnapshotJobStatus | None:
    """Updates the job with its own session and publishes the resulting state."""
    async with SessionLocal() as session:
        job = await session.scalar(update(Job).where(Job.job_id == job_id).values(**values).returning(Job))
        await session.commit()
    if job is None:  # deleted in the meantime (e.g. the player was removed)
        return None
    state = job_status_from_row(job)
    await publish_job_state(state)
    return state


class JobProgress:
    """Adapts the core's synchronous progress callback to Redis and Postgres.

    Publishes to Redis at most every `publish_every` seconds and persists to
    Postgres every `persist_every`: enough for the progress bar without
    writing to the database for every downloaded match.
    """

    def __init__(self, state: SnapshotJobStatus, *, publish_every: float = 0.5, persist_every: float = 5.0) -> None:
        self._state = state
        self._publish_every = publish_every
        self._persist_every = persist_every
        self._last_publish = float("-inf")
        self._last_persist = time.monotonic()
        self._pending: asyncio.Task[None] | None = None

    def report(self, progress: int) -> None:
        now = time.monotonic()
        if now - self._last_publish < self._publish_every:
            return
        if self._pending is not None and not self._pending.done():
            return
        self._last_publish = now
        persist = now - self._last_persist >= self._persist_every
        if persist:
            self._last_persist = now
        self._pending = asyncio.get_running_loop().create_task(self._emit(max(0, min(progress, 99)), persist))

    async def _emit(self, progress: int, persist: bool) -> None:
        self._state = self._state.model_copy(update={"progress": progress})
        try:
            if persist:
                await update_job(self._state.job_id, progress=progress)
            else:
                await publish_job_state(self._state)
        except Exception as exc:  # progress is informational: it never brings the analysis down
            logger.warning("job_progress_failed", job_id=self._state.job_id, error=str(exc))

    async def drain(self) -> None:
        if self._pending is not None:
            await self._pending


def _to_event(state: SnapshotJobStatus) -> ServerSentEvent:
    event = state.status if state.status in TERMINAL_STATUSES else "progress"
    return ServerSentEvent(data=state.model_dump_json(), event=event, retry=SSE_RETRY_MS)


async def job_event_stream(
    job_id: str,
    initial: SnapshotJobStatus,
    is_disconnected: Callable[[], Awaitable[bool]],
    *,
    poll_timeout: float = 15.0,
) -> AsyncIterator[ServerSentEvent]:
    """SSE events of a job: current state and changes until it finishes or the client leaves."""
    redis = get_redis()
    pubsub = redis.pubsub()
    # Subscribe BEFORE reading the state: that way no change is lost between the two.
    await pubsub.subscribe(job_channel(job_id))
    try:
        cached = await redis.get(job_state_key(job_id))
        state = SnapshotJobStatus.model_validate_json(cached) if cached else initial
        if initial.status in TERMINAL_STATUSES:
            state = initial  # Postgres rules: a finished job doesn't go back
        yield _to_event(state)

        while state.status not in TERMINAL_STATUSES:
            if await is_disconnected():
                return
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=poll_timeout)
            if message is None:
                continue
            state = SnapshotJobStatus.model_validate_json(message["data"])
            yield _to_event(state)
    finally:
        await pubsub.unsubscribe(job_channel(job_id))
        await pubsub.aclose()
