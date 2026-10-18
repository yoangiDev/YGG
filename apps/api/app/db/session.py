"""Async engine and sessions (SQLAlchemy 2.0 + asyncpg).

With the synchronous engine every query blocked the event loop that also
serves the concurrent Riot downloads (P7).
"""

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings

__all__ = ["SessionLocal", "engine", "get_db"]


def _engine_options() -> dict[str, Any]:
    if settings.environment == "test":
        # Each test (and each TestClient request) runs in its own event loop:
        # asyncpg connections can't be reused between loops.
        return {"poolclass": NullPool}
    return {
        "pool_size": settings.db_pool_size,
        "max_overflow": settings.db_max_overflow,
        "pool_pre_ping": True,
    }


engine = create_async_engine(settings.async_database_url, **_engine_options())

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    """One session per request. Injected with `db: AsyncSession = Depends(get_db)`."""
    async with SessionLocal() as session:
        yield session
