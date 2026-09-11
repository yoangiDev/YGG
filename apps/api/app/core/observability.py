"""Sentry y métricas de negocio para Prometheus."""

from prometheus_client import Counter

from app.core.config import settings

DASHBOARD_CACHE_REQUESTS = Counter(
    "ygg_dashboard_cache_requests_total",
    "Dashboards servidos desde la caché de Redis (hit) o recalculados (miss).",
    ["result"],
)


def init_sentry() -> None:
    if not settings.sentry_dsn:
        return
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        send_default_pii=False,
    )
