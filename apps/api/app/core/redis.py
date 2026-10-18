"""Shared Redis client: cache, rate limiting and job queue."""

import asyncio

from redis.asyncio import Redis

from app.core.config import settings

_client: Redis | None = None
_client_loop: asyncio.AbstractEventLoop | None = None
_fake_server = None


def _create_client() -> Redis:
    if settings.redis_url.startswith("memory://"):
        import fakeredis

        global _fake_server
        if _fake_server is None:
            _fake_server = fakeredis.FakeServer()
        return fakeredis.FakeAsyncRedis(server=_fake_server, decode_responses=True)
    return Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_timeout=2,
        socket_connect_timeout=2,
        health_check_interval=30,
    )


def get_redis() -> Redis:
    """Client for the current event loop.

    In production there is a single loop and a single client. In the tests each case
    (and each TestClient request) may run in its own loop, and redis-py
    connections can't be shared between loops.
    """
    global _client, _client_loop
    loop = asyncio.get_running_loop()
    if _client is None or _client_loop is not loop:
        _client, _client_loop = _create_client(), loop
    return _client
