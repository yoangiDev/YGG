"""Health checks reales y métricas (P15)."""

import re
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.routers import health
from main import app

client = TestClient(app)


def test_liveness_does_not_touch_dependencies():
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {}}


def test_readiness_checks_database_and_redis():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"database": "ok", "redis": "ok"}}


def test_readiness_fails_when_a_dependency_is_down(monkeypatch):
    monkeypatch.setattr(health, "check_database", AsyncMock(return_value="error"))
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["checks"] == {"database": "error", "redis": "ok"}


def test_prometheus_metrics_are_exposed():
    client.get("/")
    response = client.get("/metrics")
    assert response.status_code == 200
    assert re.search(r"^http_requests_total\{", response.text, re.MULTILINE)
    assert "/metrics" not in app.openapi()["paths"]


def test_request_id_is_generated_and_returned():
    response = client.get("/")
    assert re.fullmatch(r"[0-9a-f]{32}", response.headers["x-request-id"])


def test_valid_incoming_request_id_is_propagated():
    assert client.get("/", headers={"X-Request-ID": "trace-abc.123"}).headers["x-request-id"] == "trace-abc.123"


def test_malformed_incoming_request_id_is_replaced():
    response = client.get("/", headers={"X-Request-ID": "x" * 300})
    assert re.fullmatch(r"[0-9a-f]{32}", response.headers["x-request-id"])
