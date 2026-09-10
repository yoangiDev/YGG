"""Siembra la cuenta de la demo pública. Es idempotente: se puede relanzar.

    DEMO_PASSWORD=... python scripts/seed_demo.py        # desde apps/api
    DEMO_EMAIL=otra@cuenta.dev DEMO_PASSWORD=... python scripts/seed_demo.py

Usa DATABASE_URL como el resto de la API. Recrea los jugadores de la cuenta demo
y no toca a ningún otro usuario. Pensado para una base de datos de demo con la
API arrancada con DEMO_MODE=true (ver docs/deploy.md).
"""

import asyncio
import os
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

import app.db.models  # noqa: E402, F401  (registra todos los modelos ORM)
from app.db.session import SessionLocal, engine  # noqa: E402
from app.service.demo_seed import seed_demo  # noqa: E402


async def main() -> int:
    password = os.environ.get("DEMO_PASSWORD", "")
    if not password:
        print("Set DEMO_PASSWORD (at least 10 characters).", file=sys.stderr)
        return 2
    email = os.environ.get("DEMO_EMAIL", "demo@ygg.gg")

    try:
        async with SessionLocal() as db:
            result = await seed_demo(db, email=email, password=password)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        await engine.dispose()

    print(
        f"Demo ready: {email} with {result.players} players, "
        f"{result.snapshots} snapshots and {result.matches} matches."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
