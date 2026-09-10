"""Configuración de la aplicación, leída de variables de entorno (y `.env` en local).

Cada variable está documentada en `apps/api/.env.example`.
"""

from functools import cached_property
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import make_url


def to_async_database_url(url: str) -> str:
    """postgresql://… → postgresql+asyncpg://…, traduciendo `sslmode` al `ssl` de asyncpg."""
    parsed = make_url(url)
    query = dict(parsed.query)
    sslmode = query.pop("sslmode", None)
    if sslmode:
        query["ssl"] = sslmode
    return parsed.set(drivername="postgresql+asyncpg", query=query).render_as_string(hide_password=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"

    # ── Base de datos ──────────────────────────────────────────────────────────
    database_url: str
    db_pool_size: int = 5
    db_max_overflow: int = 10

    # ── Servicios externos ─────────────────────────────────────────────────────
    riot_api_key: str = ""
    # "memory://" usa un Redis en memoria (desarrollo y tests sin Redis instalado).
    redis_url: str = "redis://localhost:6379/0"
    supabase_url: str = ""
    supabase_service_key: str = ""

    # ── Auth ───────────────────────────────────────────────────────────────────
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 14
    refresh_cookie_name: str = "ygg_refresh"
    # Sin definir: cookies Secure solo en producción (en local se sirve por http).
    cookie_secure: bool | None = None

    # ── HTTP ───────────────────────────────────────────────────────────────────
    # Lista separada por comas. Nunca "*": es incompatible con allow_credentials.
    cors_origins: str = "http://localhost:5173"
    # Confiar en X-Forwarded-For solo detrás de un proxy propio.
    trust_proxy_headers: bool = False

    # ── Rate limiting ──────────────────────────────────────────────────────────
    rate_limit_enabled: bool = True
    rate_limit_global_per_minute: int = 300
    rate_limit_login_per_minute: int = 10
    rate_limit_login_per_email_per_hour: int = 30
    rate_limit_register_per_hour: int = 10
    rate_limit_refresh_per_minute: int = 30
    rate_limit_snapshots_per_hour: int = 20

    # ── Caché ──────────────────────────────────────────────────────────────────
    dashboard_cache_ttl_seconds: int = 24 * 3600
    ddragon_refresh_hours: int = 6

    # ── Observabilidad ─────────────────────────────────────────────────────────
    log_level: str = "INFO"
    # Sin definir: JSON fuera de desarrollo.
    log_json: bool | None = None
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.0

    @model_validator(mode="after")
    def _require_strong_secret_in_production(self) -> "Settings":
        # HS256 con menos de 32 bytes de clave es atacable por fuerza bruta (RFC 7518 §3.2).
        if self.environment == "production" and len(self.secret_key.encode("utf-8")) < 32:
            raise ValueError("SECRET_KEY must be at least 32 bytes long in production.")
        return self

    @cached_property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @cached_property
    def async_database_url(self) -> str:
        return to_async_database_url(self.database_url)

    @property
    def secure_cookies(self) -> bool:
        return self.cookie_secure if self.cookie_secure is not None else self.environment == "production"

    @property
    def json_logs(self) -> bool:
        return self.log_json if self.log_json is not None else self.environment != "development"


settings = Settings()
