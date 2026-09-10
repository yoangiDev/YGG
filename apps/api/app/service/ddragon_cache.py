import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class DDragonCache:
    """
    Responsable de la persistencia de datos de Data Dragon:
    - Disco: guarda y carga archivos JSON por versión.
    - RAM: mantiene los datos listos para consulta inmediata.
    """

    FILES = ["item.json", "runesReforged.json", "summoner.json"]

    def __init__(self, data_dir: str = "./data/ddragon"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.version: str | None = None
        self.items: dict = {}
        self.runes: list = []
        self.spells: dict = {}

    # ── Disco ──────────────────────────────────────────────────────────────────

    def is_cached(self, version: str, filename: str) -> bool:
        """Devuelve True si el archivo ya existe en disco para esa versión."""
        return self._get_path(version, filename).exists()

    def is_map_cached(self, version: str) -> bool:
        """Devuelve True si la imagen del mapa ya existe en disco para esa versión."""
        return (self.data_dir / f"{version}_map11.png").exists()

    def save(self, version: str, filename: str, data) -> None:
        """Persiste los datos en disco como JSON."""
        path = self._get_path(version, filename)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            logger.info(f"DDragonCache: guardado {path.name}")
        except Exception as e:
            logger.error(f"DDragonCache: error guardando {filename}: {e}")

    def save_map(self, version: str, data: bytes) -> None:
        """Persiste la imagen del mapa en disco como archivo binario."""
        path = self.data_dir / f"{version}_map11.png"
        try:
            with open(path, "wb") as f:
                f.write(data)
            logger.info(f"DDragonCache: guardado mapa {path.name}")
        except Exception as e:
            logger.error(f"DDragonCache: error guardando mapa: {e}")

    def get_map_path(self, version: str) -> Path:
        """Obtiene la ruta local del mapa guardado."""
        return self.data_dir / f"{version}_map11.png"

    def load(self, version: str, filename: str) -> bool:
        """
        Carga un archivo del disco a RAM.
        Devuelve True si tuvo éxito, False si el archivo no existe o hay error.
        """
        path = self._get_path(version, filename)
        if not path.exists():
            return False

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = json.load(f)
            self._store_in_ram(filename, content)
            self.version = version
            return True
        except Exception as e:
            logger.error(f"DDragonCache: error cargando {filename}: {e}")
            return False

    def load_all(self, version: str) -> bool:
        """
        Intenta cargar todos los archivos de una versión desde disco.
        Devuelve True solo si todos se cargaron correctamente.
        """
        return all(self.load(version, f) for f in self.FILES)

    # ── RAM ────────────────────────────────────────────────────────────────────

    def get_item(self, item_id: str):
        return self.items.get(str(item_id))

    def get_spell_by_key(self, key: str):
        for data in self.spells.values():
            if data.get("key") == str(key):
                return data
        return None

    # ── Privados ───────────────────────────────────────────────────────────────

    def _get_path(self, version: str, filename: str) -> Path:
        return self.data_dir / f"{version}_{filename}"

    def _store_in_ram(self, filename: str, content) -> None:
        """Clasifica el contenido y lo asigna al atributo RAM correcto."""
        if "item.json" in filename:
            self.items = content.get("data", {})
        elif "runesReforged.json" in filename:
            self.runes = content
        elif "summoner.json" in filename:
            self.spells = content.get("data", {})