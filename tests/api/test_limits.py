import pytest

from fsa.api.limits import DailyQuota


class Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def test_per_client_limit() -> None:
    quota = DailyQuota(per_client=2, total=100, clock=Clock())
    assert quota.try_acquire("a") is None
    assert quota.try_acquire("a") is None
    refusal = quota.try_acquire("a")
    assert refusal is not None and "limit of 2" in refusal
    assert quota.try_acquire("b") is None  # other clients are unaffected


def test_site_wide_limit() -> None:
    quota = DailyQuota(per_client=10, total=2, clock=Clock())
    assert quota.try_acquire("a") is None
    assert quota.try_acquire("b") is None
    refusal = quota.try_acquire("c")
    assert refusal is not None and "This site" in refusal


def test_window_rolls_over() -> None:
    clock = Clock()
    quota = DailyQuota(per_client=1, total=10, window_seconds=100, clock=clock)
    assert quota.try_acquire("a") is None
    assert quota.try_acquire("a") is not None
    clock.t = 101
    assert quota.try_acquire("a") is None


def test_release_gives_quota_back() -> None:
    quota = DailyQuota(per_client=1, total=1, clock=Clock())
    assert quota.try_acquire("a") is None
    quota.release("a")
    assert quota.try_acquire("a") is None


def test_zero_disables() -> None:
    assert DailyQuota(per_client=0, total=10).try_acquire("a") is not None


def test_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FSA_AI_PER_CLIENT_DAILY", "3")
    monkeypatch.setenv("FSA_AI_TOTAL_DAILY", "7")
    quota = DailyQuota.from_env()
    assert (quota.per_client, quota.total) == (3, 7)


def test_negative_rejected() -> None:
    with pytest.raises(ValueError):
        DailyQuota(per_client=-1, total=1)
