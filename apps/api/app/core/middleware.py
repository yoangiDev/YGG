"""Middlewares ASGI puros (sin BaseHTTPMiddleware, que rompe el streaming de SSE)."""

import re
import time
import uuid

import structlog
from starlette.datastructures import Headers, MutableHeaders
from starlette.requests import HTTPConnection
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import settings
from app.core.rate_limit import TOO_MANY_REQUESTS, check, client_ip

logger = structlog.get_logger("app.http")

_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_QUIET_PATHS = ("/health", "/metrics")


class RequestContextMiddleware:
    """Asigna un request_id a cada petición, lo propaga a los logs y lo devuelve en X-Request-ID."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = Headers(scope=scope).get("x-request-id", "")
        request_id = incoming if _VALID_REQUEST_ID.match(incoming) else uuid.uuid4().hex
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        status_code = 500
        started = time.perf_counter()

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message).append("X-Request-ID", request_id)
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            path = scope["path"]
            log = logger.debug if path.startswith(_QUIET_PATHS) else logger.info
            log(
                "http_request",
                method=scope["method"],
                path=path,
                status=status_code,
                duration_ms=round((time.perf_counter() - started) * 1000, 1),
            )
            structlog.contextvars.clear_contextvars()


DEMO_READ_ONLY = "The public demo is read-only."

# Escrituras que sí se permiten en la demo: sin ellas no se puede entrar ni salir.
_DEMO_ALLOWED_WRITES = frozenset({("POST", "/auth/login"), ("POST", "/auth/refresh"), ("POST", "/auth/logout")})
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
# Parámetros de lectura que fuerzan llamadas a la Riot API (y gastan su cuota).
_RIOT_QUERY_FLAGS = frozenset({"sync", "live", "refresh"})
_RIOT_QUERY_PARAMS = frozenset({"compare_game_name", "compare_tag_line"})


def demo_blocks(method: str, path: str, query_string: bytes) -> bool:
    """True si la petición escribe en la base de datos o llama a Riot."""
    if method not in _SAFE_METHODS:
        return (method, path.rstrip("/") or "/") not in _DEMO_ALLOWED_WRITES
    for pair in query_string.decode("latin-1").split("&"):
        name, _, value = pair.partition("=")
        if name in _RIOT_QUERY_PARAMS and value:
            return True
        if name in _RIOT_QUERY_FLAGS and value.lower() in ("1", "true", "yes", "on"):
            return True
    return False


class DemoModeMiddleware:
    """Con DEMO_MODE activo, la API es de solo lectura y nunca toca la Riot API."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] == "http"
            and settings.demo_mode
            and demo_blocks(scope["method"], scope["path"], scope.get("query_string", b""))
        ):
            await JSONResponse({"detail": DEMO_READ_ONLY}, status_code=403)(scope, receive, send)
            return
        await self.app(scope, receive, send)


class GlobalRateLimitMiddleware:
    """Límite global por IP para toda la API, salvo health checks y métricas."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"].startswith(_QUIET_PATHS):
            await self.app(scope, receive, send)
            return

        result = await check(
            "global", client_ip(HTTPConnection(scope)), settings.rate_limit_global_per_minute, 60
        )
        if result is not None and not result.allowed:
            response = JSONResponse(
                {"detail": TOO_MANY_REQUESTS},
                status_code=429,
                headers={"Retry-After": str(result.retry_after)},
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
