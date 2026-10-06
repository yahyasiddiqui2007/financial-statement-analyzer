"""The only module that talks to the SEC over the network.

Everything else in the app works with plain Python data, which keeps the
network details (headers, retries, rate limits) in one place and makes the
rest of the code testable without internet access.

SEC fair-access rules: https://www.sec.gov/os/accessing-edgar-data
  - Send a User-Agent header that identifies you, including an email address.
  - Make no more than 10 requests per second.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from decimal import Decimal
from types import TracebackType
from typing import Any, Self

import httpx

from fsa.ingestion.errors import (
    CompanyDataNotFoundError,
    DataFormatError,
    SecAccessDeniedError,
    SecApiError,
)
from fsa.ingestion.rate_limiter import RateLimiter

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

USER_AGENT_ENV_VAR = "FSA_SEC_USER_AGENT"

# Stay safely below the SEC's limit of 10 per second.
DEFAULT_MAX_REQUESTS_PER_SECOND = 8.0
# Status codes that usually mean "try again later" rather than "you did something wrong".
RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
MAX_BACKOFF_SECONDS = 60.0


class SecClient:
    """Fetches JSON from SEC EDGAR, with rate limiting and retries.

    Use it as a context manager so the network connection is closed afterwards:

        with SecClient.from_env() as client:
            facts = client.fetch_company_facts("0000320193")
    """

    def __init__(
        self,
        user_agent: str,
        *,
        http_client: httpx.Client | None = None,
        rate_limiter: RateLimiter | None = None,
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
        sleep: Callable[[float], None] = time.sleep,
        timeout_seconds: float = 30.0,
    ) -> None:
        user_agent = user_agent.strip()
        if "@" not in user_agent:
            raise ValueError(
                "The SEC requires a User-Agent with contact info, e.g. 'Jane Doe jane@example.com'."
            )
        self._http = http_client or httpx.Client(timeout=timeout_seconds)
        self._http.headers["User-Agent"] = user_agent
        self._rate_limiter = rate_limiter or RateLimiter(DEFAULT_MAX_REQUESTS_PER_SECOND)
        self._max_retries = max_retries
        self._backoff_seconds = backoff_seconds
        self._sleep = sleep

    @classmethod
    def from_env(cls) -> Self:
        """Build a client using the User-Agent stored in an environment variable."""
        user_agent = os.environ.get(USER_AGENT_ENV_VAR, "")
        if not user_agent:
            raise ValueError(
                f"Set the {USER_AGENT_ENV_VAR} environment variable to your name and "
                "email, e.g. export FSA_SEC_USER_AGENT='Jane Doe jane@example.com'."
            )
        return cls(user_agent)

    def fetch_company_tickers(self) -> Any:
        """The SEC's ticker → CIK list (one JSON object for every listed company)."""
        return self.get_json(TICKERS_URL)

    def fetch_company_facts(self, cik: str) -> Any:
        """Every XBRL fact a company has filed. `cik` must be 10 digits, zero-padded."""
        if len(cik) != 10 or not cik.isdigit():
            raise ValueError(f"CIK must be 10 digits, got {cik!r}")
        try:
            return self.get_json(COMPANY_FACTS_URL.format(cik=cik))
        except SecApiError as exc:
            if exc.status_code == 404:
                raise CompanyDataNotFoundError(
                    f"The SEC has no XBRL financial data for CIK {cik}."
                ) from exc
            raise

    def get_json(self, url: str) -> Any:
        """GET a URL and parse the JSON body, retrying temporary failures.

        Numbers with decimal points are parsed as Decimal, never float, so no
        precision is lost between the SEC and the calculation engine.
        """
        attempts = self._max_retries + 1
        for attempt in range(attempts):
            is_last_attempt = attempt == attempts - 1
            self._rate_limiter.wait()

            try:
                response = self._http.get(url)
            except httpx.TransportError as exc:  # timeouts, dropped connections, DNS
                if is_last_attempt:
                    raise SecApiError(
                        f"Network error contacting the SEC after {attempts} attempts: {exc}"
                    ) from exc
                self._sleep(self._backoff_delay(attempt))
                continue

            status = response.status_code
            if status == 200:
                return _parse_json(response, url)
            if status == 403:
                raise SecAccessDeniedError(
                    "The SEC denied the request (HTTP 403). Check that the User-Agent "
                    "includes a real name and email, and that requests are not too frequent."
                )
            if status in RETRYABLE_STATUS_CODES and not is_last_attempt:
                self._sleep(_retry_after_seconds(response) or self._backoff_delay(attempt))
                continue
            if status in RETRYABLE_STATUS_CODES:
                raise SecApiError(
                    f"The SEC kept returning HTTP {status} after {attempts} attempts.", status
                )
            raise SecApiError(f"The SEC returned HTTP {status} for {url}.", status)

        raise AssertionError("unreachable")  # the loop always returns or raises

    def _backoff_delay(self, attempt: int) -> float:
        """Exponential backoff: 1s, 2s, 4s, ... so a struggling server gets breathing room."""
        return min(self._backoff_seconds * (2.0**attempt), MAX_BACKOFF_SECONDS)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


def _parse_json(response: httpx.Response, url: str) -> Any:
    try:
        return json.loads(response.content, parse_float=Decimal)
    except ValueError as exc:
        raise DataFormatError(f"Response from {url} was not valid JSON.") from exc


def _retry_after_seconds(response: httpx.Response) -> float | None:
    """Read the server's Retry-After header, if it gave a number of seconds."""
    header = response.headers.get("Retry-After")
    if header is None:
        return None
    try:
        seconds = float(header)
    except ValueError:
        return None  # an HTTP-date; fall back to our own backoff
    return min(max(seconds, 0.0), MAX_BACKOFF_SECONDS)
