"""Health checks.

- /health/live: el proceso responde (liveness). No toca dependencias.
- /health: la API puede atender tráfico (readiness). Falla con 503 si Postgres
  o Redis no responden, en vez de devolver una constante (P15).
"""

import asyncio

import structlog
from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.core.redis import get_redis
from app.db.session import engine
from app.schemas.system import CheckStatus, HealthResponse

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["health"])

CHECK_TIMEOUT_SECONDS = 2.0


async def check_database() -> CheckStatus:
    try:
        async with asyncio.timeout(CHECK_TIMEOUT_SECONDS), engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:
        logger.error("health_check_failed", dependency="database", error=str(exc))
        return "error"
    return "ok"


async def check_redis() -> CheckStatus:
    try:
        async with asyncio.timeout(CHECK_TIMEOUT_SECONDS):
            await get_redis().ping()
    except Exception as exc:
        logger.error("health_check_failed", dependency="redis", error=str(exc))
        return "error"
    return "ok"


@router.get("/health/live", response_model=HealthResponse)
async def liveness():
    return HealthResponse(status="ok", checks={})


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={503: {"model": HealthResponse, "description": "A dependency is down"}},
)
async def readiness(response: Response):
    database, redis = await asyncio.gather(check_database(), check_redis())
    checks: dict[str, CheckStatus] = {"database": database, "redis": redis}
    healthy = all(result == "ok" for result in checks.values())
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(status="ok" if healthy else "error", checks=checks)
