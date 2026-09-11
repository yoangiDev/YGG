"""Data Dragon para la API: datos en Redis e imágenes servidas desde el CDN de Riot.

Antes los JSON y el minimapa se guardaban en ./data y se servían con
StaticFiles; en Render ese disco desaparece en cada deploy (P10).
"""

import json
import logging
import time
from typing import Any

from redis.exceptions import RedisError
from ygg_core.ddragon.client import DDRAGON_BASE, FALLBACK_VERSION
from ygg_core.ddragon.client import DDragonClient as CoreDDragonClient

from app.core.config import settings
from app.core.redis import get_redis

logger = logging.getLogger(__name__)

__all__ = ["DDRAGON_BASE", "FALLBACK_VERSION", "DDragonClient", "RedisDDragonStore", "get_ddragon_client"]


class RedisDDragonStore:
    TTL_SECONDS = 7 * 24 * 3600

    @staticmethod
    def _key(version: str, filename: str) -> str:
        return f"ddragon:{version}:{filename}"

    async def load(self, version: str, filename: str) -> Any | None:
        try:
            raw = await get_redis().get(self._key(version, filename))
        except RedisError as exc:
            logger.warning("DDragon cache unavailable: %s", exc)
            return None
        return json.loads(raw) if raw else None

    async def save(self, version: str, filename: str, data: Any) -> None:
        try:
            await get_redis().set(self._key(version, filename), json.dumps(data), ex=self.TTL_SECONDS)
        except RedisError as exc:
            logger.warning("DDragon cache unavailable: %s", exc)


class DDragonClient(CoreDDragonClient):
    def __init__(self) -> None:
        super().__init__(RedisDDragonStore())
        self.loaded_at = 0.0

    async def initialize(self) -> None:
        await super().initialize()
        self.loaded_at = time.monotonic()

    @property
    def is_stale(self) -> bool:
        """Riot publica parche cada dos semanas: se vuelve a mirar la versión cada pocas horas."""
        return time.monotonic() - self.loaded_at > settings.ddragon_refresh_hours * 3600


_client: DDragonClient | None = None


async def get_ddragon_client() -> DDragonClient:
    global _client
    if _client is None or _client.is_stale:
        client = DDragonClient()
        await client.initialize()
        _client = client
    return _client
