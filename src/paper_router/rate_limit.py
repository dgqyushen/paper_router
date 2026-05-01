from __future__ import annotations

import asyncio
from dataclasses import dataclass
from time import monotonic


@dataclass(slots=True)
class RateLimit:
    requests_per_second: float

    def __post_init__(self) -> None:
        if self.requests_per_second <= 0:
            raise ValueError("requests_per_second must be positive")


class AsyncRateLimiter:
    def __init__(self, rate_limit: RateLimit) -> None:
        self._min_interval = 1 / rate_limit.requests_per_second
        self._lock = asyncio.Lock()
        self._last_call_started_at = 0.0

    async def acquire(self) -> None:
        async with self._lock:
            now = monotonic()
            wait_seconds = self._min_interval - (now - self._last_call_started_at)
            if wait_seconds > 0:
                await asyncio.sleep(wait_seconds)
            self._last_call_started_at = monotonic()
