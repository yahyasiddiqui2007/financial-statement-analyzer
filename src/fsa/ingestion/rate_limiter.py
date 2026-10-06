"""A simple rate limiter that spaces requests evenly in time.

The SEC allows at most 10 requests per second per user. Spacing requests at
least 1/N seconds apart guarantees we never exceed N per second.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable


class RateLimiter:
    """Blocks just long enough to keep calls under `max_per_second`.

    The clock and sleep functions can be replaced in tests, so tests run
    instantly instead of actually waiting.
    """

    def __init__(
        self,
        max_per_second: float,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if max_per_second <= 0:
            raise ValueError("max_per_second must be positive")
        self._min_interval = 1.0 / max_per_second
        self._clock = clock
        self._sleep = sleep
        self._next_allowed = 0.0
        # A lock makes this safe if several threads share one client.
        self._lock = threading.Lock()

    def wait(self) -> None:
        """Call before each request. Returns once the request is allowed."""
        with self._lock:
            now = self._clock()
            if now < self._next_allowed:
                self._sleep(self._next_allowed - now)
                now = self._next_allowed
            self._next_allowed = now + self._min_interval
