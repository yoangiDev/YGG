"""Rate limiting propio de la API (P6)."""

import random

import fakeredis
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.rate_limit import hit
from main import app
from tests.helpers import unique

client = TestClient(app)


@pytest.fixture
def limits_on(monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    # Una IP distinta por test: las ventanas de un test no afectan a otro.
    monkeypatch.setattr(settings, "trust_proxy_headers", True)
    return {"X-Forwarded-For": f"203.0.113.{random.randint(1, 254)}, 10.0.0.1"}


async def test_sliding_window_blocks_over_the_limit():
    redis = fakeredis.FakeAsyncRedis(decode_responses=True)
    key = unique("rl")

    results = [await hit(redis, key, limit=3, window_seconds=60) for _ in range(4)]

    assert [r.allowed for r in results] == [True, True, True, False]
    assert [r.remaining for r in results[:3]] == [2, 1, 0]
    assert 1 <= results[3].retry_after <= 61
    assert await redis.zcard(key) == 3  # el intento rechazado no ocupa hueco


def test_global_limit_returns_429_with_retry_after(limits_on, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_global_per_minute", 2)

    statuses = [client.get("/", headers=limits_on).status_code for _ in range(3)]

    assert statuses == [200, 200, 429]
    blocked = client.get("/", headers=limits_on)
    assert int(blocked.headers["retry-after"]) >= 1


def test_health_checks_are_never_limited(limits_on, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_global_per_minute", 1)
    assert [client.get("/health/live", headers=limits_on).status_code for _ in range(3)] == [200, 200, 200]


def test_login_is_limited_per_account(limits_on, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_login_per_email_per_hour", 3)
    email = f"{unique('bruteforce')}@example.com"

    attempts = [
        client.post("/auth/login", json={"email": email, "password": "wrong-password"}, headers=limits_on)
        for _ in range(4)
    ]

    assert [a.status_code for a in attempts] == [401, 401, 401, 429]
    assert int(attempts[3].headers["retry-after"]) >= 1
