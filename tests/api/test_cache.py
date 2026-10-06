from datetime import UTC, datetime

import pytest

from fsa.api.cache import TTLCache


class Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def test_value_is_reused_until_expiry() -> None:
    clock = Clock()
    cache: TTLCache[int] = TTLCache(60, clock=clock)
    loads = iter([1, 2])
    assert cache.get_or_load("k", lambda: next(loads)).value == 1
    clock.t = 59
    assert cache.get_or_load("k", lambda: next(loads)).value == 1
    clock.t = 61
    assert cache.get_or_load("k", lambda: next(loads)).value == 2


def test_records_retrieval_time() -> None:
    fixed = datetime(2026, 1, 2, tzinfo=UTC)
    cache: TTLCache[int] = TTLCache(60, now=lambda: fixed)
    assert cache.get_or_load("k", lambda: 1).retrieved_at == fixed


def test_errors_are_not_cached() -> None:
    cache: TTLCache[int] = TTLCache(60)

    def fail() -> int:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        cache.get_or_load("k", fail)
    assert cache.get_or_load("k", lambda: 5).value == 5


def test_evicts_when_full() -> None:
    clock = Clock()
    cache: TTLCache[int] = TTLCache(60, max_entries=2, clock=clock)
    cache.get_or_load("a", lambda: 1)
    clock.t = 1
    cache.get_or_load("b", lambda: 2)
    cache.get_or_load("c", lambda: 3)  # evicts "a", the one expiring soonest
    assert cache.get_or_load("a", lambda: 10).value == 10
