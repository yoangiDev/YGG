"""Global, proactive limiter for the Riot API, shared by all clients."""

from __future__ import annotations

import asyncio
import time
from collections import deque

# Development key: 20 req/s and 100 req / 2 min. We stay well below that
# (each match is 2 calls: match + timeline).
_PER_SECOND = 10
_PER_TWO_MINUTES = 70


class RiotRateLimiter:
    """Sliding window with a coordinated global pause on receiving a 429."""

    def __init__(
        self,
        per_second: int = _PER_SECOND,
        per_two_minutes: int = _PER_TWO_MINUTES,
    ) -> None:
        self.per_second = per_second
        self.per_two_minutes = per_two_minutes
        self._lock = asyncio.Lock()
        self._second_window: deque[float] = deque()
        self._two_min_window: deque[float] = deque()
        self._paused_until = 0.0

    @staticmethod
    def _prune(window: deque[float], now: float, span: float) -> None:
        cutoff = now - span
        while window and window[0] <= cutoff:
            window.popleft()

    def _seconds_until_slot(self, now: float) -> float:
        wait = 0.0
        if now < self._paused_until:
            wait = max(wait, self._paused_until - now)
        if len(self._second_window) >= self.per_second:
            wait = max(wait, self._second_window[0] + 1.0 - now)
        if len(self._two_min_window) >= self.per_two_minutes:
            wait = max(wait, self._two_min_window[0] + 120.0 - now)
        return max(wait, 0.05)

    async def pause(self, seconds: float) -> bool:
        """Extends the global pause. Returns True only if the window grew."""
        async with self._lock:
            new_until = time.monotonic() + seconds
            extended = new_until > self._paused_until + 0.05
            self._paused_until = max(self._paused_until, new_until)
            return extended

    async def acquire(self) -> None:
        while True:
            async with self._lock:
                now = time.monotonic()
                self._prune(self._second_window, now, 1.0)
                self._prune(self._two_min_window, now, 120.0)
                if (
                    now >= self._paused_until
                    and len(self._second_window) < self.per_second
                    and len(self._two_min_window) < self.per_two_minutes
                ):
                    self._second_window.append(now)
                    self._two_min_window.append(now)
                    return
                wait = self._seconds_until_slot(now)
            await asyncio.sleep(wait)


_limiter: RiotRateLimiter | None = None


def configure_riot_rate_limiter(per_second: int, per_two_minutes: int) -> RiotRateLimiter:
    """Sets the global limiter's quota: with a production key it is enough to raise these numbers."""
    global _limiter
    _limiter = RiotRateLimiter(per_second, per_two_minutes)
    return _limiter


def get_riot_rate_limiter() -> RiotRateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = RiotRateLimiter()
    return _limiter


def reset_riot_rate_limiter() -> None:
    """For tests only."""
    global _limiter
    _limiter = None
