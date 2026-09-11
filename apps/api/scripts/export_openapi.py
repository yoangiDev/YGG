"""Exporta el esquema OpenAPI a apps/api/openapi.json.

Es la fuente de los tipos TypeScript del frontend (openapi-typescript), así
que va versionado; tests/test_openapi.py falla si se queda desactualizado.

    python scripts/export_openapi.py
"""

import json
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from main import app  # noqa: E402

OUTPUT = API_ROOT / "openapi.json"


def main() -> None:
    OUTPUT.write_text(json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"OpenAPI escrito en {OUTPUT} ({len(app.openapi()['paths'])} rutas)")


if __name__ == "__main__":
    main()
