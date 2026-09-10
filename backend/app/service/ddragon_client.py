import logging
from app.service.ddragon_cache import DDragonCache
from app.service.http_client import create_secure_session

logger = logging.getLogger(__name__)

DDRAGON_BASE = "https://ddragon.leagueoflegends.com"
VERSIONS_URL = f"{DDRAGON_BASE}/api/versions.json"
FALLBACK_VERSION = "16.10.1"


class DDragonClient:
    """
    Responsable de obtener datos de Data Dragon:
    - Consulta la versión más reciente.
    - Descarga los JSONs si no están en caché.
    - Delega la persistencia (disco + RAM) en DDragonCache.
    """

    def __init__(self, data_dir: str = "./data/ddragon"):
        self._cache = DDragonCache(data_dir)

    # ── Propiedades que delegan en la caché ────────────────────────────────────

    @property
    def version(self) -> str | None:
        return self._cache.version

    @property
    def items(self) -> dict:
        return self._cache.items

    @property
    def runes(self) -> list:
        return self._cache.runes

    @property
    def spells(self) -> dict:
        return self._cache.spells

    # ── Inicialización ─────────────────────────────────────────────────────────

    async def initialize(self) -> None:
        """
        Carga los datos de Data Dragon en RAM.
        Si ya están en disco los lee directamente; si no, los descarga primero.
        """
        version = await self._fetch_latest_version()

        # Si todos los archivos ya están en disco, solo los cargamos en RAM
        if self._cache.load_all(version):
            logger.info(f"DDragon {version} loaded from local cache.")
            # Asegurar que la imagen del mapa también esté descargada localmente
            if not self._cache.is_map_cached(version):
                await self._download_map(version)
            return

        # Si falta alguno, descargamos todos y los guardamos
        await self._download_all(version)
        logger.info(f"DDragon {version} downloaded and loaded into RAM.")

    # ── Getters públicos ───────────────────────────────────────────────────────

    def get_item_data(self, item_id: str):
        return self._cache.get_item(item_id)

    def get_spell_data_by_key(self, key: str):
        return self._cache.get_spell_by_key(key)

    def get_map_path(self) -> str | None:
        """Obtiene la ruta local de la imagen del mapa si existe."""
        if not self.version:
            return None
        path = self._cache.get_map_path(self.version)
        return str(path) if path.exists() else None

    # ── URLs estáticas ─────────────────────────────────────────────────────────

    @staticmethod
    def map_image_url(version: str) -> str:
        return f"{DDRAGON_BASE}/cdn/{version}/img/map/map11.png"

    @staticmethod
    def champion_icon_url(version: str, champion_name: str) -> str:
        return f"{DDRAGON_BASE}/cdn/{version}/img/champion/{champion_name}.png"

    @staticmethod
    def item_icon_url(version: str, item_id: int) -> str:
        return f"{DDRAGON_BASE}/cdn/{version}/img/item/{item_id}.png"

    @staticmethod
    def rune_icon_url(version: str, icon_path: str) -> str:
        if icon_path.startswith("perk-images"):
            return f"{DDRAGON_BASE}/cdn/img/{icon_path}"
        return f"{DDRAGON_BASE}/cdn/{version}/img/{icon_path}"

    # ── Privados ───────────────────────────────────────────────────────────────

    async def _fetch_latest_version(self) -> str:
        """Obtiene la versión más reciente de DDragon. Usa fallback si falla."""
        try:
            async with create_secure_session() as session:
                async with session.get(VERSIONS_URL) as response:
                    if response.status != 200:
                        raise ConnectionError(f"HTTP {response.status}")
                    versions = await response.json()
                    return versions[0]
        except Exception as e:
            logger.warning(f"Could not fetch DDragon version: {e}. Using {FALLBACK_VERSION}.")
            return FALLBACK_VERSION

    async def _download_all(self, version: str) -> None:
        """Descarga todos los JSONs de DDragon y los persiste en disco y RAM."""
        async with create_secure_session() as session:
            for filename in DDragonCache.FILES:
                url = f"{DDRAGON_BASE}/cdn/{version}/data/en_US/{filename}"
                logger.info(f"Descargando {filename} desde DDragon...")
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self._cache.save(version, filename, data)
                        self._cache.load(version, filename)
                    else:
                        logger.error(f"Error downloading {filename}: HTTP {resp.status}")

        # Descargar también el mapa
        await self._download_map(version)

    async def _download_map(self, version: str) -> None:
        """Descarga la imagen del mapa de Summoner's Rift (map11.png) desde DDragon y la guarda."""
        url = self.map_image_url(version)
        logger.info(f"Descargando imagen del mapa (map11.png) desde DDragon...")
        try:
            async with create_secure_session() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        self._cache.save_map(version, data)
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

