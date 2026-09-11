"""Cliente Redis compartido: caché, rate limiting y cola de trabajos."""

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
    """Cliente del event loop actual.

    En producción hay un único loop y un único cliente. En los tests cada caso
    (y cada petición de TestClient) puede correr en su propio loop, y las
    conexiones de redis-py no se pueden compartir entre loops.
    """
    global _client, _client_loop
    loop = asyncio.get_running_loop()
    if _client is None or _client_loop is not loop:
        _client, _client_loop = _create_client(), loop
    return _client
