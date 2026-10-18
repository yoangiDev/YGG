"""ARQ worker that runs the analyses outside the API process (P3).

    arq app.jobs.worker.WorkerSettings

- Retries with backoff when Riot is unavailable.
- Heartbeat while the analysis runs.
- Orphan recovery at startup and every minute: a job in "processing"
  without a recent heartbeat is marked as an error (and can be retried); one in
  "queued" that has not moved for a while is enqueued again.
"""

import asyncio
from functools import partial
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from arq import Retry, cron
from arq import func as arq_function
from arq.worker import run_worker
from sqlalchemy import func, or_, select, update
from ygg_core.riot.errors import RiotUnavailableError

import app.db.models  # noqa: F401  (registers the ORM models)
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.observability import init_sentry
from app.crud.player import refresh_player_rank
from app.db.models.job import Job
from app.db.models.player import Player
from app.db.models.snapshot import Snapshot
from app.db.session import SessionLocal, engine
from app.jobs.progress import JobProgress, job_status_from_row, publish_job_state, update_job
from app.jobs.queue import ANALYSIS_FUNCTION, ArqJobQueue, JobQueue, arq_redis_settings, get_job_queue
from app.service.elo import player_ids_due_for_elo
from app.service.premium import request_premium
from app.service.stats_runner import run_stats_extraction

logger = structlog.get_logger(__name__)

MAX_TRIES = 3
RETRY_BACKOFF_SECONDS = 30
INTERRUPTED_ERROR = "The analysis was interrupted before finishing. Retry it."


async def _heartbeat(job_id: str) -> None:
    while True:
        await asyncio.sleep(settings.job_heartbeat_seconds)
        try:
            async with SessionLocal() as session:
                await session.execute(update(Job).where(Job.job_id == job_id).values(heartbeat_at=func.now()))
                await session.commit()
        except Exception as exc:
            logger.warning("job_heartbeat_failed", job_id=job_id, error=str(exc))


async def run_analysis(ctx: dict[str, Any], job_id: str) -> int | None:
    """Runs a queued analysis. Returns the id of the created snapshot."""
    job_try = int(ctx.get("job_try", 1))
    structlog.contextvars.bind_contextvars(job_id=job_id, job_try=job_try)

    async with SessionLocal() as session:
        job = await session.get(Job, job_id)
    if job is None or job.status == "done":
        logger.info("job_skipped", reason="missing" if job is None else "already_done")
        return None

    state = await update_job(
        job_id,
        status="processing",
        attempts=Job.attempts + 1,
        started_at=func.now(),
        heartbeat_at=func.now(),
        finished_at=None,
        error=None,
        progress=0,
    )
    if state is None:
        return None

    progress = JobProgress(state)
    heartbeat = asyncio.create_task(_heartbeat(job_id))
    try:
        async with SessionLocal() as session:
            player = await session.get(Player, job.player_id) if job.player_id is not None else None
            if player is None or job.date_from is None or job.date_to is None:
                raise ValueError("The player or the period of this analysis no longer exists.")
            snapshot_id = await run_stats_extraction(
                session,
                player,
                job.date_from,
                job.date_to,
                job.description or "",
                on_progress=progress.report,
            )
    except RiotUnavailableError as exc:
        await progress.drain()
        if job_try < MAX_TRIES:
            logger.warning("job_retry_scheduled", error=str(exc))
            await update_job(job_id, status="queued", error=f"Riot API unavailable, retrying ({job_try}/{MAX_TRIES}).")
            raise Retry(defer=timedelta(seconds=RETRY_BACKOFF_SECONDS * job_try)) from exc
        await update_job(job_id, status="error", error=str(exc), finished_at=func.now())
        return None
    except asyncio.CancelledError:
        # Timeout or orderly worker shutdown: ARQ will retry it if attempts remain.
        await update_job(job_id, status="error", error=INTERRUPTED_ERROR, finished_at=func.now())
        raise
    except Exception as exc:
        logger.exception("job_failed")
        await progress.drain()
        await update_job(job_id, status="error", error=str(exc), finished_at=func.now())
        return None
    finally:
        heartbeat.cancel()

    await progress.drain()
    await update_job(
        job_id, status="done", progress=100, snapshot_id=snapshot_id, error=None, finished_at=func.now()
    )
    logger.info("job_done", snapshot_id=snapshot_id)
    if job.premium and snapshot_id is not None:
        await _request_premium(snapshot_id)
    return snapshot_id


async def _request_premium(snapshot_id: int) -> None:
    """The snapshot was requested with the replay analysis: its matches are left waiting for their replay. If it fails, the snapshot
    is still fine and the analysis can be launched by hand from its page (POST /snapshots/{id}/premium)."""
    try:
        async with SessionLocal() as session:
            snapshot = await session.get(Snapshot, snapshot_id)
            if snapshot is not None:
                await request_premium(session, snapshot)
    except Exception as exc:
        logger.warning("premium_enqueue_failed", snapshot_id=snapshot_id, error=str(exc))


async def recover_orphaned_jobs(queue: JobQueue) -> tuple[list[str], list[str]]:
    """Marks as errors the jobs without a heartbeat and re-enqueues those left in the queue."""
    cutoff = datetime.now(UTC) - timedelta(seconds=settings.job_stale_after_seconds)
    async with SessionLocal() as session:
        orphaned = list(
            await session.scalars(
                update(Job)
                .where(
                    Job.status == "processing",
                    or_(Job.heartbeat_at.is_(None), Job.heartbeat_at < cutoff),
                )
                .values(status="error", error=INTERRUPTED_ERROR, finished_at=func.now())
                .returning(Job)
            )
        )
        stuck = list(await session.scalars(select(Job).where(Job.status == "queued", Job.updated_at < cutoff)))
        await session.commit()

    for job in orphaned:
        await publish_job_state(job_status_from_row(job))
    for job in stuck:
        # If the job is still in the ARQ queue, the repeated _job_id makes sure it isn't duplicated.
        await queue.enqueue_analysis(job.job_id)

    if orphaned or stuck:
        logger.warning(
            "jobs_recovered",
            orphaned=[job.job_id for job in orphaned],
            requeued=[job.job_id for job in stuck],
        )
    return [job.job_id for job in orphaned], [job.job_id for job in stuck]


async def _recover_orphaned_jobs_cron(ctx: dict[str, Any]) -> None:
    await recover_orphaned_jobs(ArqJobQueue(pool=ctx["redis"]))


RIOT_PUUID_LEN = 78


async def track_elo(ctx: dict[str, Any]) -> None:
    """Every hour: today's point for the players with elo tracking who don't have it yet."""
    async with SessionLocal() as session:
        for player_id in await player_ids_due_for_elo(session):
            player = await session.get(Player, player_id)
            if player is None or len(player.puuid) != RIOT_PUUID_LEN:  # those from the tests don't exist in Riot
                continue
            try:
                await refresh_player_rank(session, player)
            except Exception as exc:  # it is retried the next hour
                await session.rollback()
                logger.warning("elo_check_failed", player_id=player_id, error=str(exc))


async def inline_crons() -> None:
    """Without an ARQ worker (inline queue, which is what the single Render instance uses): its two crons, in the process
    itself. Every minute, the jobs orphaned by a restart; every hour, the elo. What fails is retried on the
    next round, as the cron did."""
    minute = 0
    while True:
        try:
            await recover_orphaned_jobs(get_job_queue())
            if minute % 60 == 0:
                await track_elo({})
        except Exception:
            logger.exception("inline_cron_failed")
        minute += 1
        await asyncio.sleep(60)


async def _startup(ctx: dict[str, Any]) -> None:
    configure_logging()
    init_sentry()


async def _shutdown(ctx: dict[str, Any]) -> None:
    await engine.dispose()


class WorkerSettings:
    functions = [
        arq_function(run_analysis, name=ANALYSIS_FUNCTION, max_tries=MAX_TRIES, timeout=settings.job_timeout_seconds)
    ]
    cron_jobs = [
        cron(_recover_orphaned_jobs_cron, run_at_startup=True),  # every minute
        cron(track_elo, minute={5}, run_at_startup=True),  # every hour
    ]
    on_startup = _startup
    on_shutdown = _shutdown
    redis_settings = arq_redis_settings()
    max_jobs = settings.worker_max_jobs
    job_timeout = settings.job_timeout_seconds
    keep_result = 0  # the result lives in Postgres; this way a retry can reuse the _job_id
    health_check_interval = 30


# What infra/dev.ps1 starts with watchfiles, which restarts it when the code changes: arq's --watch reloads with
# SIGUSR1, which doesn't exist on Windows, and the worker crashed instead of reloading
main = partial(run_worker, WorkerSettings)
