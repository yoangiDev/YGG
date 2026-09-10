"""Caché del dashboard en Redis.

Clave: versión del esquema de respuesta + snapshot_id. Se invalida cuando
cambian las partidas de un snapshot o sus textos. Si Redis falla, el dashboard
se calcula igual: la caché nunca es un punto de fallo.
"""

from collections.abc import Iterable

import structlog
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.observability import DASHBOARD_CACHE_REQUESTS
from app.core.redis import get_redis
from app.crud.participants import snapshot_ids_for_participants
from app.schemas.dashboard import SnapshotDashboardResponse

logger = structlog.get_logger(__name__)

# Súbelo al cambiar SnapshotDashboardResponse: las entradas antiguas dejan de leerse.
SCHEMA_VERSION = 2


def cache_key(snapshot_id: int) -> str:
    return f"dashboard:v{SCHEMA_VERSION}:{snapshot_id}"


async def get_cached_dashboard(snapshot_id: int) -> SnapshotDashboardResponse | None:
    try:
        raw = await get_redis().get(cache_key(snapshot_id))
    except RedisError as exc:
        logger.warning("dashboard_cache_unavailable", error=str(exc))
        return None
    if raw is None:
        DASHBOARD_CACHE_REQUESTS.labels(result="miss").inc()
        return None
    DASHBOARD_CACHE_REQUESTS.labels(result="hit").inc()
    return SnapshotDashboardResponse.model_validate_json(raw)


async def store_dashboard(dashboard: SnapshotDashboardResponse) -> None:
    try:
        await get_redis().set(
            cache_key(dashboard.snapshot_id),
            dashboard.model_dump_json(),
            ex=settings.dashboard_cache_ttl_seconds,
        )
    except RedisError as exc:
        logger.warning("dashboard_cache_unavailable", error=str(exc))


async def invalidate_dashboards(snapshot_ids: Iterable[int]) -> None:
    keys = [cache_key(snapshot_id) for snapshot_id in dict.fromkeys(snapshot_ids)]
    if not keys:
        return
    try:
        await get_redis().delete(*keys)
    except RedisError as exc:
        logger.warning("dashboard_cache_unavailable", error=str(exc))


async def invalidate_dashboards_for_participants(db: AsyncSession, participant_ids: Iterable[int]) -> None:
    """Una partida re-enriquecida puede estar en varios snapshots: se invalidan todos."""
    await invalidate_dashboards(await snapshot_ids_for_participants(db, participant_ids))
