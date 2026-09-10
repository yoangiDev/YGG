"""Rate limiting con Redis: ventana deslizante sobre un sorted set.

El limitador de ygg-core protege a Riot de nosotros; este protege la API de
clientes abusivos (P6). Si Redis no responde se deja pasar la petición y se
registra: preferimos degradar la protección a tumbar la API.
"""

import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import structlog
from fastapi import HTTPException, Request, Response, status
from redis.asyncio import Redis
from redis.exceptions import RedisError
from starlette.requests import HTTPConnection

from app.core.config import settings
from app.core.redis import get_redis

logger = structlog.get_logger(__name__)

TOO_MANY_REQUESTS = "Too many requests, try again later."


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    retry_after: int  # segundos; 0 si se permite


async def hit(redis: Redis, key: str, limit: int, window_seconds: int) -> RateLimitResult:
    """Registra un intento y dice si cabe en los últimos `window_seconds`."""
    now = time.time()
    member = f"{now}:{uuid.uuid4().hex}"
    async with redis.pipeline(transaction=True) as pipe:
        pipe.zremrangebyscore(key, 0, now - window_seconds)
        pipe.zadd(key, {member: now})
        pipe.zcard(key)
        pipe.zrange(key, 0, 0, withscores=True)
        pipe.expire(key, window_seconds)
        _, _, count, oldest, _ = await pipe.execute()

    if count > limit:
        await redis.zrem(key, member)  # un intento rechazado no ocupa hueco
        oldest_score = oldest[0][1] if oldest else now
        retry_after = max(1, int(oldest_score + window_seconds - now) + 1)
        return RateLimitResult(False, limit, 0, retry_after)
    return RateLimitResult(True, limit, limit - count, 0)


def client_ip(connection: HTTPConnection) -> str:
    if settings.trust_proxy_headers:
        forwarded = connection.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return connection.client.host if connection.client else "unknown"


async def check(scope: str, identifier: str, limit: int, window_seconds: int) -> RateLimitResult | None:
    """None si el rate limiting está desactivado o Redis no responde."""
    if not settings.rate_limit_enabled:
        return None
    try:
        return await hit(get_redis(), f"ratelimit:{scope}:{identifier}", limit, window_seconds)
    except RedisError as exc:
        logger.warning("rate_limit_unavailable", scope=scope, error=str(exc))
        return None


async def enforce(
    scope: str,
    identifier: str,
    limit: int,
    window_seconds: int,
    response: Response | None = None,
) -> None:
    result = await check(scope, identifier, limit, window_seconds)
    if result is None:
        return
    if response is not None:
        response.headers["X-RateLimit-Limit"] = str(result.limit)
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
    if not result.allowed:
        logger.info("rate_limited", scope=scope)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=TOO_MANY_REQUESTS,
            headers={"Retry-After": str(result.retry_after)},
        )


def rate_limit(
    scope: str, limit_setting: str, window_seconds: int
) -> Callable[[Request, Response], Awaitable[None]]:
    """Dependencia de FastAPI limitada por IP. El límite se lee de `settings` en cada petición."""

    async def dependency(request: Request, response: Response) -> None:
        await enforce(scope, client_ip(request), getattr(settings, limit_setting), window_seconds, response)

    return dependency
