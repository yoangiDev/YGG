"""Global proactive rate limiter for Riot API requests (shared across all clients)."""

from __future__ import annotations

import asyncio
import time
from collections import deque

# Riot dev key: 20 req/s, 100 req / 2 min. Stay well under (2 HTTP calls per match).
_PER_SECOND = 10
_PER_TWO_MINUTES = 70


class RiotRateLimiter:
    """Sliding-window limiter with global pause on 429 responses."""

    def __init__(
        self,
        per_second: int = _PER_SECOND,
        per_two_minutes: int = _PER_TWO_MINUTES,
    ):
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
        """Extend global pause. Returns True only when the window was extended."""
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


def get_riot_rate_limiter() -> RiotRateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = RiotRateLimiter()
    return _limiter

def reset_riot_rate_limiter() -> None:
    """For tests only."""
    global _limiter
    _limiter = None
