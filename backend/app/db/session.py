from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Lee las variables del .env automáticamente."""
    database_url: str
    riot_api_key: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    supabase_url: str = ""
    supabase_service_key: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()

# ── Motor de conexión ──────────────────────────────────────────────────────────
engine = create_engine(
    settings.database_url,
    pool_size=5,           # Conexiones simultáneas (equivale a tu DB_POOL_SIZE)
    max_overflow=10,       # Conexiones extra si el pool está lleno
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