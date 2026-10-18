"""Sentry and business metrics for Prometheus."""

from prometheus_client import Counter

from app.core.config import settings

DASHBOARD_CACHE_REQUESTS = Counter(
    "ygg_dashboard_cache_requests_total",
    "Dashboards served from the Redis cache (hit) or recomputed (miss).",
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
