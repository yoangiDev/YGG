from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute
from prometheus_fastapi_instrumentator import Instrumentator

import app.db.models  # noqa: F401  (registra todos los modelos ORM)
from app.auth.router import router as auth_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.middleware import DemoModeMiddleware, GlobalRateLimitMiddleware, RequestContextMiddleware
from app.core.observability import init_sentry
from app.db.session import engine
from app.routers.admin import router as admin_router
from app.routers.ddragon import router as ddragon_router
from app.routers.health import router as health_router
from app.routers.league import router as league_router
from app.routers.matches import router as matches_router
from app.routers.players import router as players_router
from app.routers.snapshots import router as snapshots_router
from app.schemas.common import MessageResponse

configure_logging()
init_sentry()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # El esquema lo gestiona exclusivamente Alembic (`alembic upgrade head`).
    yield
    await engine.dispose()


def _operation_id(route: APIRoute) -> str:
    """IDs estables y legibles para el cliente TypeScript generado (p. ej. players_list_players)."""
    return f"{route.tags[0]}_{route.name}" if route.tags else route.name


def create_app() -> FastAPI:
    application = FastAPI(
        title="YGG API",
        description="API de análisis de partidas de League of Legends",
        version="2.0.0",
        lifespan=lifespan,
        generate_unique_id_function=_operation_id,
    )

    # El último middleware añadido es el más externo: request-id → CORS → rate limit → demo → rutas.
    # La demo va dentro de CORS para que el navegador pueda leer su 403.
    application.add_middleware(DemoModeMiddleware)
    application.add_middleware(GlobalRateLimitMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID", "Retry-After", "X-RateLimit-Limit", "X-RateLimit-Remaining"],
    )
    application.add_middleware(RequestContextMiddleware)

    for router in (
        health_router,
        auth_router,
        players_router,
        matches_router,
        snapshots_router,
        ddragon_router,
        league_router,
        admin_router,
    ):
        application.include_router(router)

    @application.get("/", response_model=MessageResponse, tags=["health"])
    async def root() -> MessageResponse:
        return MessageResponse(message="YGG API", status="running")

    Instrumentator(excluded_handlers=["/metrics", "/health", "/health/live"]).instrument(application).expose(
        application, include_in_schema=False
    )
    return application


app = create_app()
