"""Data Dragon para la API: el cliente de ygg-core con caché en disco y el minimapa."""

import logging

from ygg_core.ddragon.client import DDRAGON_BASE, FALLBACK_VERSION, FileDDragonStore
from ygg_core.ddragon.client import DDragonClient as CoreDDragonClient
from ygg_core.riot.http import create_secure_session

logger = logging.getLogger(__name__)

__all__ = [
    "DDRAGON_BASE",
    "FALLBACK_VERSION",
    "DDragonClient",
    "get_ddragon_client",
    "get_item_data",
    "get_spell_data_by_key",
    "initialize_ddragon_data",
]


class DDragonClient(CoreDDragonClient):
    """Persiste los JSON en disco y descarga la imagen del minimapa que sirve la API."""

    def __init__(self, data_dir: str = "./data/ddragon"):
        self._files = FileDDragonStore(data_dir)
        super().__init__(self._files)

    async def initialize(self) -> None:
        await super().initialize()
        if self.version and not self._files.map_path(self.version).exists():
            await self._download_map(self.version)

    # ── Nombres que usan los routers ───────────────────────────────────────────

    def get_item_data(self, item_id: str):
        return self.get_item(item_id)

    def get_spell_data_by_key(self, key: str):
        return self.get_spell_by_key(key)

    def get_map_path(self) -> str | None:
        """Ruta local de la imagen del mapa, si ya está descargada."""
        if not self.version:
            return None
        path = self._files.map_path(self.version)
        return str(path) if path.exists() else None

    async def _download_map(self, version: str) -> None:
        url = self.map_image_url(version)
        try:
            async with create_secure_session() as session, session.get(url) as resp:
                if resp.status == 200:
                    self._files.save_map(version, await resp.read())
                else:
                    logger.error(f"Error downloading map image: HTTP {resp.status}")
        except Exception as e:
            logger.error(f"Error connecting to DDragon for map image: {e}")


# ── Singleton y helpers ────────────────────────────────────────────────────────

_ddragon_client: DDragonClient | None = None


async def get_ddragon_client() -> DDragonClient:
    global _ddragon_client
    if _ddragon_client is None:
        _ddragon_client = DDragonClient()
        await _ddragon_client.initialize()
    return _ddragon_client


async def initialize_ddragon_data():
    await get_ddragon_client()


def get_item_data(item_id: str):
    return _ddragon_client.get_item_data(item_id) if _ddragon_client else None


def get_spell_data_by_key(key: str):
    return _ddragon_client.get_spell_data_by_key(key) if _ddragon_client else None
