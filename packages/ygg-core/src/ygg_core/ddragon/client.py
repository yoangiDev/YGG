"""Data Dragon: datos estáticos de objetos, runas y hechizos, con almacenamiento intercambiable."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

import aiohttp

from ygg_core.riot.http import create_secure_session

logger = logging.getLogger(__name__)

DDRAGON_BASE = "https://ddragon.leagueoflegends.com"
VERSIONS_URL = f"{DDRAGON_BASE}/api/versions.json"
FALLBACK_VERSION = "16.10.1"
DATA_FILES: tuple[str, ...] = ("item.json", "runesReforged.json", "summoner.json")


class DDragonStore(Protocol):
    def load(self, version: str, filename: str) -> Any | None: ...

    def save(self, version: str, filename: str, data: Any) -> None: ...


class MemoryDDragonStore:
    def __init__(self) -> None:
        self._data: dict[tuple[str, str], Any] = {}

    def load(self, version: str, filename: str) -> Any | None:
        return self._data.get((version, filename))

    def save(self, version: str, filename: str, data: Any) -> None:
        self._data[(version, filename)] = data


class FileDDragonStore:
    """JSON por versión en disco (y la imagen del minimapa)."""

    def __init__(self, data_dir: str | Path) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, version: str, filename: str) -> Path:
        return self.data_dir / f"{version}_{filename}"

    def load(self, version: str, filename: str) -> Any | None:
        path = self._path(version, filename)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("DDragon store: error loading %s: %s", path.name, exc)
            return None

    def save(self, version: str, filename: str, data: Any) -> None:
        path = self._path(version, filename)
        try:
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        except OSError as exc:
            logger.error("DDragon store: error saving %s: %s", path.name, exc)

    def map_path(self, version: str) -> Path:
        return self.data_dir / f"{version}_map11.png"

    def save_map(self, version: str, data: bytes) -> None:
        self.map_path(version).write_bytes(data)


class DDragonClient:
    def __init__(
        self,
        store: DDragonStore | None = None,
        *,
        session_factory: Callable[[], aiohttp.ClientSession] = create_secure_session,
        language: str = "en_US",
    ) -> None:
        self.store: DDragonStore = store or MemoryDDragonStore()
        self._session_factory = session_factory
        self.language = language
        self.version: str | None = None
        self.items: dict[str, Any] = {}
        self.runes: list[dict[str, Any]] = []
        self.spells: dict[str, Any] = {}

    async def initialize(self) -> None:
        """Carga la última versión: del almacén si está completa, de Data Dragon si no."""
        version = await self.fetch_latest_version()
        if self._load_all(version):
            logger.info("DDragon %s loaded from store.", version)
        else:
            await self._download_all(version)
            logger.info("DDragon %s downloaded.", version)
        self.version = version

    async def fetch_latest_version(self) -> str:
        try:
            async with self._session_factory() as session, session.get(VERSIONS_URL) as response:
                if response.status != 200:
                    raise ConnectionError(f"HTTP {response.status}")
                versions = await response.json()
                return str(versions[0])
        except Exception as exc:  # sin red se sirve la versión de respaldo
            logger.warning("Could not fetch DDragon version: %s. Using %s.", exc, FALLBACK_VERSION)
            return FALLBACK_VERSION

    def _load_all(self, version: str) -> bool:
        loaded = {name: self.store.load(version, name) for name in DATA_FILES}
        if any(content is None for content in loaded.values()):
            return False
        for name, content in loaded.items():
            self._apply(name, content)
        return True

    async def _download_all(self, version: str) -> None:
        async with self._session_factory() as session:
            for name in DATA_FILES:
                url = f"{DDRAGON_BASE}/cdn/{version}/data/{self.language}/{name}"
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.error("Error downloading %s: HTTP %s", name, response.status)
                        continue
                    content = await response.json()
                self.store.save(version, name, content)
                self._apply(name, content)

    def _apply(self, filename: str, content: Any) -> None:
        if filename == "item.json":
            self.items = content.get("data", {})
        elif filename == "runesReforged.json":
            self.runes = content
        elif filename == "summoner.json":
            self.spells = content.get("data", {})

    # ── Consultas ──────────────────────────────────────────────────────────────

    def get_item(self, item_id: str | int) -> dict[str, Any] | None:
        item: dict[str, Any] | None = self.items.get(str(item_id))
        return item

    def get_spell_by_key(self, key: str | int) -> dict[str, Any] | None:
        for spell in self.spells.values():
            if spell.get("key") == str(key):
                found: dict[str, Any] = spell
                return found
        return None

    def find_rune(self, rune_id: int) -> dict[str, Any] | None:
        """Busca un árbol de runas o una runa concreta dentro de sus slots."""
        target = str(rune_id)
        for tree in self.runes:
            if str(tree.get("id")) == target:
                return tree
            for slot in tree.get("slots", []):
                for rune in slot.get("runes", []):
                    if str(rune.get("id")) == target:
                        found: dict[str, Any] = rune
                        return found
        return None

    # ── URLs del CDN ───────────────────────────────────────────────────────────

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
    def profile_icon_url(version: str, icon_id: int) -> str:
        return f"{DDRAGON_BASE}/cdn/{version}/img/profileicon/{icon_id}.png"

    @staticmethod
    def rune_icon_url(version: str, icon_path: str) -> str:
        if icon_path.startswith("perk-images"):
            return f"{DDRAGON_BASE}/cdn/img/{icon_path}"
        return f"{DDRAGON_BASE}/cdn/{version}/img/{icon_path}"
