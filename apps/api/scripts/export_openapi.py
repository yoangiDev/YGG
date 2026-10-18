"""Exports the OpenAPI schema to apps/api/openapi.json.

It is the source of the frontend's TypeScript types (openapi-typescript), so
it is versioned; tests/test_openapi.py fails if it falls out of date.

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
    print(f"OpenAPI written to {OUTPUT} ({len(app.openapi()['paths'])} paths)")


if __name__ == "__main__":
    main()
