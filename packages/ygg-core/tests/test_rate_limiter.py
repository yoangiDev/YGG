import time

from ygg_core.riot.rate_limiter import RiotRateLimiter


async def test_per_second_limit():
    limiter = RiotRateLimiter(per_second=3, per_two_minutes=100)
    start = time.monotonic()
    for _ in range(5):
        await limiter.acquire()
    assert time.monotonic() - start >= 0.9


async def test_burst_within_limits():
    limiter = RiotRateLimiter(per_second=10, per_two_minutes=100)
    start = time.monotonic()
    for _ in range(10):
        await limiter.acquire()
    assert time.monotonic() - start < 0.5


async def test_global_pause_blocks_acquire():
    limiter = RiotRateLimiter(per_second=100, per_two_minutes=100)
    assert await limiter.pause(0.3) is True
    assert await limiter.pause(0.2) is False  # no extiende una pausa más larga
    start = time.monotonic()
    await limiter.acquire()
    assert time.monotonic() - start >= 0.25
