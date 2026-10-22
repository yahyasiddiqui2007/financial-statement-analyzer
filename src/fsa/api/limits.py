"""Daily limits on AI analyses, so a public deployment can't run up a large API bill.

Two limits apply over a rolling 24 hours: one per client (by IP address) and
one for the whole site. Like the cache, the counts live in memory and reset
when the server restarts, which is fine for a small single-server deployment.
"""

from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable

DAY_SECONDS = 24 * 60 * 60
PER_CLIENT_ENV_VAR = "FSA_AI_PER_CLIENT_DAILY"
TOTAL_ENV_VAR = "FSA_AI_TOTAL_DAILY"
DEFAULT_PER_CLIENT = 5
DEFAULT_TOTAL = 50


class DailyQuota:
    def __init__(
        self,
        per_client: int,
        total: int,
        *,
        window_seconds: float = DAY_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if per_client < 0 or total < 0:
            raise ValueError("limits cannot be negative")
        self.per_client = per_client
        self.total = total
        self._window = window_seconds
        self._clock = clock
        self._by_client: dict[str, deque[float]] = defaultdict(deque)
        self._all: deque[float] = deque()
        self._lock = threading.Lock()

    @classmethod
    def from_env(cls) -> DailyQuota:
        return cls(
            per_client=int(os.environ.get(PER_CLIENT_ENV_VAR, DEFAULT_PER_CLIENT)),
            total=int(os.environ.get(TOTAL_ENV_VAR, DEFAULT_TOTAL)),
        )

    def _prune(self, uses: deque[float], now: float) -> None:
        while uses and uses[0] <= now - self._window:
            uses.popleft()

    def try_acquire(self, client: str) -> str | None:
        """Record one use. Returns None if allowed, or a message explaining the refusal."""
        with self._lock:
            now = self._clock()
            mine = self._by_client[client]
            self._prune(mine, now)
            self._prune(self._all, now)
            if len(self._all) >= self.total:
                return (
                    "This site has reached its daily limit for AI analyses. "
                    "Please try again tomorrow."
                )
            if len(mine) >= self.per_client:
                return (
                    f"You've reached the limit of {self.per_client} AI analyses per day. "
                    "Please try again tomorrow."
                )
            mine.append(now)
            self._all.append(now)
            return None

    def release(self, client: str) -> None:
        """Give back the most recent use, e.g. when the analysis failed."""
        with self._lock:
            if self._by_client[client]:
                self._by_client[client].pop()
            if self._all:
                self._all.pop()
