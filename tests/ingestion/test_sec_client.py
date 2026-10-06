"""SecClient tests. httpx.MockTransport stands in for the SEC, so no real network calls happen."""

from collections.abc import Callable
from decimal import Decimal

import httpx
import pytest

from fsa.ingestion.errors import (
    CompanyDataNotFoundError,
    DataFormatError,
    SecAccessDeniedError,
    SecApiError,
)
from fsa.ingestion.rate_limiter import RateLimiter
from fsa.ingestion.sec_client import COMPANY_FACTS_URL, USER_AGENT_ENV_VAR, SecClient

UA = "Test Student test@example.com"
Handler = Callable[[httpx.Request], httpx.Response]


class Recorder:
    """Serves a scripted list of responses and records requests and sleeps."""

    def __init__(self, *responses: httpx.Response | Exception) -> None:
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []
        self.sleeps: list[float] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        next_response = self.responses.pop(0)
        if isinstance(next_response, Exception):
            raise next_response
        return next_response

    def client(self, max_retries: int = 3) -> SecClient:
        return SecClient(
            UA,
            http_client=httpx.Client(transport=httpx.MockTransport(self.handle)),
            rate_limiter=RateLimiter(1000, sleep=lambda s: None),
            max_retries=max_retries,
            sleep=self.sleeps.append,
        )


def ok(body: str = '{"ok": true}') -> httpx.Response:
    return httpx.Response(200, content=body.encode())


class TestSuccess:
    def test_returns_parsed_json(self) -> None:
        rec = Recorder(ok('{"a": 1}'))
        assert rec.client().get_json("https://example.test/x") == {"a": 1}

    def test_sends_user_agent(self) -> None:
        rec = Recorder(ok())
        rec.client().get_json("https://example.test/x")
        assert rec.requests[0].headers["User-Agent"] == UA

    def test_decimals_are_not_floats(self) -> None:
        rec = Recorder(ok('{"eps": 6.13}'))
        result = rec.client().get_json("https://example.test/x")
        assert result["eps"] == Decimal("6.13")
        assert isinstance(result["eps"], Decimal)

    def test_company_facts_url_uses_padded_cik(self) -> None:
        rec = Recorder(ok())
        rec.client().fetch_company_facts("0000320193")
        assert str(rec.requests[0].url) == COMPANY_FACTS_URL.format(cik="0000320193")


class TestRetries:
    @pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
    def test_retries_temporary_errors_then_succeeds(self, status: int) -> None:
        rec = Recorder(httpx.Response(status), ok())
        assert rec.client().get_json("https://example.test/x") == {"ok": True}
        assert len(rec.requests) == 2

    def test_exponential_backoff(self) -> None:
        rec = Recorder(httpx.Response(503), httpx.Response(503), httpx.Response(503), ok())
        rec.client().get_json("https://example.test/x")
        assert rec.sleeps == [1.0, 2.0, 4.0]

    def test_respects_retry_after_header(self) -> None:
        rec = Recorder(httpx.Response(429, headers={"Retry-After": "7"}), ok())
        rec.client().get_json("https://example.test/x")
        assert rec.sleeps == [7.0]

    def test_ignores_unparseable_retry_after(self) -> None:
        rec = Recorder(
            httpx.Response(429, headers={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}), ok()
        )
        rec.client().get_json("https://example.test/x")
        assert rec.sleeps == [1.0]

    def test_gives_up_after_max_retries(self) -> None:
        rec = Recorder(*[httpx.Response(503) for _ in range(3)])
        with pytest.raises(SecApiError) as info:
            rec.client(max_retries=2).get_json("https://example.test/x")
        assert info.value.status_code == 503
        assert len(rec.requests) == 3

    def test_retries_network_errors(self) -> None:
        rec = Recorder(httpx.ConnectTimeout("slow"), httpx.ConnectError("down"), ok())
        assert rec.client().get_json("https://example.test/x") == {"ok": True}

    def test_network_errors_eventually_raise(self) -> None:
        rec = Recorder(*[httpx.ReadTimeout("slow") for _ in range(2)])
        with pytest.raises(SecApiError, match="Network error"):
            rec.client(max_retries=1).get_json("https://example.test/x")


class TestErrors:
    def test_404_on_company_facts_means_no_data(self) -> None:
        rec = Recorder(httpx.Response(404))
        with pytest.raises(CompanyDataNotFoundError):
            rec.client().fetch_company_facts("0000000001")
        assert len(rec.requests) == 1  # not retried

    def test_403_is_access_denied_and_not_retried(self) -> None:
        rec = Recorder(httpx.Response(403))
        with pytest.raises(SecAccessDeniedError):
            rec.client().get_json("https://example.test/x")
        assert len(rec.requests) == 1

    def test_other_client_errors_are_not_retried(self) -> None:
        rec = Recorder(httpx.Response(400))
        with pytest.raises(SecApiError) as info:
            rec.client().get_json("https://example.test/x")
        assert info.value.status_code == 400
        assert len(rec.requests) == 1

    def test_invalid_json(self) -> None:
        rec = Recorder(ok("<html>maintenance</html>"))
        with pytest.raises(DataFormatError):
            rec.client().get_json("https://example.test/x")

    @pytest.mark.parametrize("cik", ["320193", "00003201930", "abcdefghij"])
    def test_rejects_badly_formatted_cik(self, cik: str) -> None:
        with pytest.raises(ValueError):
            Recorder().client().fetch_company_facts(cik)


class TestUserAgent:
    @pytest.mark.parametrize("ua", ["", "   ", "MyApp/1.0"])
    def test_requires_contact_email(self, ua: str) -> None:
        with pytest.raises(ValueError, match="User-Agent"):
            SecClient(ua)

    def test_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(USER_AGENT_ENV_VAR, UA)
        with SecClient.from_env() as client:
            assert isinstance(client, SecClient)

    def test_from_env_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(USER_AGENT_ENV_VAR, raising=False)
        with pytest.raises(ValueError, match=USER_AGENT_ENV_VAR):
            SecClient.from_env()
