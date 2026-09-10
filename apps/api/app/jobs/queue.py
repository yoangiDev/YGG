"""Encolado de análisis. La API solo encola; el trabajo lo hace el worker."""

import asyncio
from typing import Protocol

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.core.config import settings

ANALYSIS_FUNCTION = "run_analysis"


class JobQueue(Protocol):
    async def enqueue_analysis(self, job_id: str) -> None: ...


def arq_redis_settings() -> RedisSettings:
    if settings.redis_url.startswith("memory://"):
        return RedisSettings()
    return RedisSettings.from_dsn(settings.redis_url)


class ArqJobQueue:
    def __init__(self, pool: ArqRedis | None = None) -> None:
        self._pool = pool
        self._owns_pool = pool is None
        self._loop: asyncio.AbstractEventLoop | None = None

    async def _get_pool(self) -> ArqRedis:
        if not self._owns_pool and self._pool is not None:
            return self._pool
        loop = asyncio.get_running_loop()
        if self._pool is None or self._loop is not loop:
            self._pool = await create_pool(arq_redis_settings())
            self._loop = loop
        return self._pool

    async def enqueue_analysis(self, job_id: str) -> None:
        pool = await self._get_pool()
        # _job_id hace el encolado idempotente: si ya está en la cola, ARQ no lo duplica.
        await pool.enqueue_job(ANALYSIS_FUNCTION, job_id, _job_id=f"analysis:{job_id}")


class InlineJobQueue:
    """Sin worker: ejecuta el análisis en el propio proceso. Solo para desarrollo.

    Tiene el mismo problema que la Fase 4 resuelve (un reinicio lo pierde), pero
    el heartbeat y la recuperación de huérfanos siguen funcionando.
    """

    def __init__(self) -> None:
        self._tasks: set[asyncio.Task[int | None]] = set()

    async def enqueue_analysis(self, job_id: str) -> None:
        from app.jobs.worker import run_analysis

        task = asyncio.create_task(run_analysis({"job_try": 1}, job_id))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)


_arq_queue = ArqJobQueue()
_inline_queue = InlineJobQueue()


def get_job_queue() -> JobQueue:
    """Dependencia de FastAPI (los tests la sustituyen por una cola falsa)."""
    if settings.job_backend == "inline" or settings.redis_url.startswith("memory://"):
        return _inline_queue
    return _arq_queue
