"""Configuración de la aplicación, leída de variables de entorno (y `.env` en local).

Cada variable está documentada en `apps/api/.env.example`.
"""

from functools import cached_property
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"

    # ── Base de datos ──────────────────────────────────────────────────────────
    database_url: str
    db_pool_size: int = 5
    db_max_overflow: int = 10

    # ── Servicios externos ─────────────────────────────────────────────────────
    riot_api_key: str = ""
    redis_url: str = "redis://localhost:6379/0"
    supabase_url: str = ""
    supabase_service_key: str = ""

    # ── Auth ───────────────────────────────────────────────────────────────────
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # ── HTTP ───────────────────────────────────────────────────────────────────
    # Lista separada por comas. Nunca "*": es incompatible con allow_credentials.
    cors_origins: str = "http://localhost:5173"

    @cached_property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
