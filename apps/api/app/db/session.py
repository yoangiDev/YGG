from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

__all__ = ["engine", "SessionLocal", "get_db", "settings"]

# ── Motor de conexión ──────────────────────────────────────────────────────────
engine = create_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=True,    # Verifica que la conexión sigue viva antes de usarla
    echo=False,            # Cambiar a True para ver el SQL generado en desarrollo
)

# ── Fábrica de sesiones ────────────────────────────────────────────────────────
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


# ── Dependencia para FastAPI ───────────────────────────────────────────────────
def get_db():
    """
    Generador que abre una sesión por request y la cierra al terminar.
    Se inyecta en los routers con: db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
