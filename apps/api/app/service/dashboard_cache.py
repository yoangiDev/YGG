"""Dashboard cache in Redis.

Key: response schema version + snapshot_id. It is invalidated when
a snapshot's matches or texts change. If Redis fails, the dashboard
is computed anyway: the cache is never a point of failure.
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

# Bump it when changing SnapshotDashboardResponse or how it is computed: old entries stop being read.
# v3: radar with the period's KDA and deaths anchored to the Challenger average.
# v4: radar Dmg/Gold as damage % ÷ gold %.
# v5: deaths in two phases, four trends with a Challenger reference and per-champion stats.
# v6: each role's own trends (ganks, objective setup, roams, vision, gold).
# v7: cleared enemy camps read from the right Riot field.
# v8: without deaths_by_phase or icon_url, which the frontend didn't use.
SCHEMA_VERSION = 9


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
    """A re-enriched match can be in several snapshots: all of them are invalidated."""
    await invalidate_dashboards(await snapshot_ids_for_participants(db, participant_ids))
