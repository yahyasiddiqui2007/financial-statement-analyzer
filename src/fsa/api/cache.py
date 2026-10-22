"""A small in-memory cache so repeat searches don't re-download from the SEC.

Annual data changes at most a few times a year, so caching for an hour is
safe and keeps us far below the SEC's rate limit. Failures are never cached:
if the SEC is down, the next search tries again.

This lives in memory, so it resets when the server restarts. The database
phase will replace it with persistent storage.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class CachedValue[T]:
    value: T
    retrieved_at: datetime  # when the data was fetched from the source


class TTLCache[T]:
    """Keeps each value for `ttl_seconds`, then fetches it again."""

    def __init__(
        self,
        ttl_seconds: float,
        *,
        max_entries: int = 256,
        clock: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._ttl = ttl_seconds
        self._max_entries = max_entries
        self._clock = clock
        self._now = now
        self._entries: dict[str, tuple[float, CachedValue[T]]] = {}
        self._lock = threading.Lock()

    def peek(self, key: str) -> CachedValue[T] | None:
        """The cached value if present and fresh, without loading anything."""
        with self._lock:
            entry = self._entries.get(key)
            if entry is not None and self._clock() < entry[0]:
                return entry[1]
            return None

    def get_or_load(self, key: str, load: Callable[[], T]) -> CachedValue[T]:
        with self._lock:
            entry = self._entries.get(key)
            if entry is not None and self._clock() < entry[0]:
                return entry[1]

        # Load outside the lock so one slow request doesn't block others.
        cached = CachedValue(value=load(), retrieved_at=self._now())
        with self._lock:
            if len(self._entries) >= self._max_entries:
                # Drop the entry closest to expiring to make room.
                oldest = min(self._entries, key=lambda k: self._entries[k][0])
                del self._entries[oldest]
            self._entries[key] = (self._clock() + self._ttl, cached)
        return cached
