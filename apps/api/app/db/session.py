"""Motor y sesiones asíncronas (SQLAlchemy 2.0 + asyncpg).

Con el motor síncrono cada consulta bloqueaba el event loop que también
atiende las descargas concurrentes de Riot (P7).
"""

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings

__all__ = ["SessionLocal", "engine", "get_db"]


def _engine_options() -> dict[str, Any]:
    if settings.environment == "test":
        # Cada test (y cada petición de TestClient) corre en su propio event loop:
        # las conexiones de asyncpg no se pueden reutilizar entre loops.
        return {"poolclass": NullPool}
    return {
        "pool_size": settings.db_pool_size,
        "max_overflow": settings.db_max_overflow,
        "pool_pre_ping": True,
    }


engine = create_async_engine(settings.async_database_url, **_engine_options())

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    """Una sesión por petición. Se inyecta con `db: AsyncSession = Depends(get_db)`."""
    async with SessionLocal() as session:
        yield session
