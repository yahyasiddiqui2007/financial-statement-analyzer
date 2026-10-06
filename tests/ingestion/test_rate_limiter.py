import pytest

from fsa.ingestion.rate_limiter import RateLimiter


class FakeClock:
    """A clock that only moves when sleep() is called, so tests run instantly."""

    def __init__(self) -> None:
        self.now = 100.0
        self.sleeps: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def test_first_call_does_not_wait() -> None:
    clock = FakeClock()
    RateLimiter(10, clock=clock.time, sleep=clock.sleep).wait()
    assert clock.sleeps == []


def test_back_to_back_calls_are_spaced_out() -> None:
    clock = FakeClock()
    limiter = RateLimiter(10, clock=clock.time, sleep=clock.sleep)
    for _ in range(3):
        limiter.wait()
    assert clock.sleeps == pytest.approx([0.1, 0.1])


def test_no_wait_when_enough_time_has_passed() -> None:
    clock = FakeClock()
    limiter = RateLimiter(10, clock=clock.time, sleep=clock.sleep)
    limiter.wait()
    clock.now += 5
    limiter.wait()
    assert clock.sleeps == []


def test_never_exceeds_limit_in_any_second() -> None:
    clock = FakeClock()
    limiter = RateLimiter(8, clock=clock.time, sleep=clock.sleep)
    call_times = []
    for _ in range(50):
        limiter.wait()
        call_times.append(clock.now)
    for t in call_times:
        in_window = [c for c in call_times if t <= c < t + 1]
        assert len(in_window) <= 8


@pytest.mark.parametrize("bad", [0, -1])
def test_rejects_non_positive_rate(bad: float) -> None:
    with pytest.raises(ValueError):
        RateLimiter(bad)
