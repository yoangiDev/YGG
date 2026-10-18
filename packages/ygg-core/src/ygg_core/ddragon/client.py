"""Data Dragon: static data for items, runes and spells, with swappable storage."""

from __future__ import annotations

import asyncio
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
    """Where the JSON files are kept per version. Async so that it can be backed by Redis."""

    async def load(self, version: str, filename: str) -> Any | None: ...

    async def save(self, version: str, filename: str, data: Any) -> None: ...


class MemoryDDragonStore:
    def __init__(self) -> None:
        self._data: dict[tuple[str, str], Any] = {}

    async def load(self, version: str, filename: str) -> Any | None:
        return self._data.get((version, filename))

    async def save(self, version: str, filename: str, data: Any) -> None:
        self._data[(version, filename)] = data


class FileDDragonStore:
    """JSON per version on disk. Useful for the CLI; in a container the disk is ephemeral."""

    def __init__(self, data_dir: str | Path) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, version: str, filename: str) -> Path:
        return self.data_dir / f"{version}_{filename}"

    def _read(self, path: Path) -> Any | None:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("DDragon store: error loading %s: %s", path.name, exc)
            return None

    def _write(self, path: Path, data: Any) -> None:
        try:
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        except OSError as exc:
            logger.error("DDragon store: error saving %s: %s", path.name, exc)

    async def load(self, version: str, filename: str) -> Any | None:
        return await asyncio.to_thread(self._read, self._path(version, filename))

    async def save(self, version: str, filename: str, data: Any) -> None:
        await asyncio.to_thread(self._write, self._path(version, filename), data)


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
        """Load the latest version: from the store if it is complete, from Data Dragon if not."""
        version = await self.fetch_latest_version()
        if await self._load_all(version):
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
        except Exception as exc:  # without a network the fallback version is served
            logger.warning("Could not fetch DDragon version: %s. Using %s.", exc, FALLBACK_VERSION)
            return FALLBACK_VERSION

    async def _load_all(self, version: str) -> bool:
        loaded = {name: await self.store.load(version, name) for name in DATA_FILES}
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
                await self.store.save(version, name, content)
                self._apply(name, content)

    def _apply(self, filename: str, content: Any) -> None:
        if filename == "item.json":
            self.items = content.get("data", {})
        elif filename == "runesReforged.json":
            self.runes = content
        elif filename == "summoner.json":
            self.spells = content.get("data", {})
