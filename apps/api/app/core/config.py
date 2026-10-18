"""Application configuration, read from environment variables (and `.env` locally).

Each variable is documented in `apps/api/.env.example`.
"""

from datetime import UTC, datetime
from functools import cached_property
from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import make_url


_ANCESTORS = Path(__file__).resolve().parents
# The folder that holds YGG and lol-replay-decoder. In the Docker image (/app/app/core/config.py) there aren't that many
# levels: without the bound, importing the configuration failed with IndexError and the API didn't start.
_PROJECTS = _ANCESTORS[5] if len(_ANCESTORS) > 5 else _ANCESTORS[-1]


def to_async_database_url(url: str) -> str:
    """postgresql://… → postgresql+asyncpg://…, translating `sslmode` to asyncpg's `ssl`."""
    parsed = make_url(url)
    query = dict(parsed.query)
    sslmode = query.pop("sslmode", None)
    if sslmode:
        query["ssl"] = sslmode
    return parsed.set(drivername="postgresql+asyncpg", query=query).render_as_string(hide_password=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"

    # ── Database ───────────────────────────────────────────────────────────────
    database_url: str
    db_pool_size: int = 5
    db_max_overflow: int = 10

    # ── External services ──────────────────────────────────────────────────────
    riot_api_key: str = ""
    # Riot key quota. By default, the development one (20/s and 100 per 2 min) with some margin.
    # With a production key it is enough to raise these three numbers.
    riot_requests_per_second: int = 10
    riot_requests_per_two_minutes: int = 70
    riot_max_connections: int = 6
    # Current season (Riot dates, different every year). Empty end: still open.
    season_start: datetime = datetime(2026, 1, 1, tzinfo=UTC)
    season_end: datetime | None = None
    # Replay analysis: since when replays and the exe of each patch exist (the calendar doesn't allow asking earlier).
    premium_since: datetime = datetime(2026, 9, 23, tzinfo=UTC)  # 16.19 comes out
    # To decode the replays that are uploaded. By default, the harvest PC (YGG and lol-replay-decoder side by
    # side); on another machine, through environment variables.
    decoder_dir: Path = _PROJECTS / "lol-replay-decoder"  # its .venv, its exes (data/cliente-<patch>) and cosecha.py
    premium_dir: Path = _PROJECTS / "lol-replay-decoder" / "data" / "premium"  # replays/ (as they pass through) and cosecha/
    game_data_dir: Path = Path("C:/Riot Games/League of Legends/Game/DATA/FINAL")  # names of the current patch
    research_dir: Path = _PROJECTS / "YGG" / "research"  # replays/ (concepts) and the value model
    decode_processes: int = 4
    anthropic_api_key: str = ""  # without a key, the replay analysis is stored without a review (the numbers stand on their own)
    review_model: str = "claude-opus-5-5"
    review_effort: Literal["low", "medium", "high", "xhigh", "max"] = "high"
    # "memory://" uses an in-memory Redis (development and tests without Redis installed).
    redis_url: str = "redis://localhost:6379/0"

    # ── Auth ───────────────────────────────────────────────────────────────────
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 14
    refresh_cookie_name: str = "ygg_refresh"
    # Unset: Secure cookies only in production (locally it is served over http).
    cookie_secure: bool | None = None

    # ── HTTP ───────────────────────────────────────────────────────────────────
    # Comma-separated list. Never "*": it is incompatible with allow_credentials.
    cors_origins: str = "http://localhost:5173"
    # Trust X-Forwarded-For only behind your own proxy.
    trust_proxy_headers: bool = False

    # ── Rate limiting ──────────────────────────────────────────────────────────
    rate_limit_enabled: bool = True
    rate_limit_global_per_minute: int = 300
    rate_limit_login_per_minute: int = 10
    rate_limit_login_per_email_per_hour: int = 30
    rate_limit_register_per_hour: int = 10
    rate_limit_refresh_per_minute: int = 30
    rate_limit_snapshots_per_hour: int = 20

    # ── Cache ──────────────────────────────────────────────────────────────────
    dashboard_cache_ttl_seconds: int = 24 * 3600
    ddragon_refresh_hours: int = 6

    # ── Job queue ──────────────────────────────────────────────────────────────
    # "arq": analyses are run by a separate worker (production).
    # "inline": in the API process itself (development without a worker or a real Redis).
    job_backend: Literal["arq", "inline"] = "arq"
    worker_max_jobs: int = 2
    job_timeout_seconds: int = 30 * 60
    job_heartbeat_seconds: int = 10
    # A job in "processing" with no heartbeat for this long is considered lost.
    job_stale_after_seconds: int = 60

    # ── Public demo ────────────────────────────────────────────────────────────
    # Read-only: rejects writes and any request that calls the Riot API.
    # The demo serves the data seeded with scripts/seed_demo.py.
    demo_mode: bool = False

    # ── Observabilidad ─────────────────────────────────────────────────────────
    log_level: str = "INFO"
    # Unset: JSON outside development.
    log_json: bool | None = None
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.0

    @model_validator(mode="after")
    def _require_strong_secret_in_production(self) -> "Settings":
        # HS256 with a key shorter than 32 bytes can be brute-forced (RFC 7518 §3.2).
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
