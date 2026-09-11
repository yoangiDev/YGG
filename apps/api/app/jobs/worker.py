"""Worker de ARQ que ejecuta los análisis fuera del proceso de la API (P3).

    arq app.jobs.worker.WorkerSettings

- Reintentos con backoff cuando Riot no está disponible.
- Heartbeat mientras el análisis corre.
- Recuperación de huérfanos al arrancar y cada minuto: un job en "processing"
  sin heartbeat reciente se marca como error (y se puede reintentar); uno en
  "queued" que lleva tiempo sin moverse se vuelve a encolar.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from arq import Retry, cron
from arq import func as arq_function
from sqlalchemy import func, or_, select, update
from ygg_core.riot.errors import RiotUnavailableError

import app.db.models  # noqa: F401  (registra los modelos ORM)
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.observability import init_sentry
from app.db.models.job import Job
from app.db.models.player import Player
from app.db.session import SessionLocal, engine
from app.jobs.progress import JobProgress, job_status_from_row, publish_job_state, update_job
from app.jobs.queue import ANALYSIS_FUNCTION, ArqJobQueue, JobQueue, arq_redis_settings
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
    """Ejecuta un análisis encolado. Devuelve el id del snapshot creado."""
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
        # Timeout o parada ordenada del worker: ARQ lo reintentará si quedan intentos.
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
    return snapshot_id


async def recover_orphaned_jobs(queue: JobQueue) -> tuple[list[str], list[str]]:
    """Marca como error los jobs sin heartbeat y reencola los que se quedaron en la cola."""
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
        # Si el job sigue en la cola de ARQ, el _job_id repetido hace que no se duplique.
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


async def _startup(ctx: dict[str, Any]) -> None:
    configure_logging()
    init_sentry()


async def _shutdown(ctx: dict[str, Any]) -> None:
    await engine.dispose()


class WorkerSettings:
    functions = [
        arq_function(run_analysis, name=ANALYSIS_FUNCTION, max_tries=MAX_TRIES, timeout=settings.job_timeout_seconds)
    ]
    cron_jobs = [cron(_recover_orphaned_jobs_cron, run_at_startup=True)]  # cada minuto
    on_startup = _startup
    on_shutdown = _shutdown
    redis_settings = arq_redis_settings()
    max_jobs = settings.worker_max_jobs
    job_timeout = settings.job_timeout_seconds
    keep_result = 0  # el resultado vive en Postgres; así un reintento puede reutilizar el _job_id
    health_check_interval = 30
