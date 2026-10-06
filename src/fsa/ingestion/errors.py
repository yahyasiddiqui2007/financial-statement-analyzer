"""Errors the ingestion layer can raise.

They all inherit from IngestionError, so callers (like a future API) can
catch one type and turn it into a friendly message.
"""

from __future__ import annotations


class IngestionError(Exception):
    """Base class for every ingestion failure."""


class TickerNotFoundError(IngestionError):
    """The ticker is not in the SEC's list of companies."""


class CompanyDataNotFoundError(IngestionError):
    """The SEC has no XBRL financial data for this company (HTTP 404)."""


class SecAccessDeniedError(IngestionError):
    """The SEC refused the request (HTTP 403).

    Usually means the User-Agent header is missing contact information, or the
    SEC has temporarily blocked us for sending too many requests.
    """


class SecApiError(IngestionError):
    """The SEC returned an error, or kept failing after all retries."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class DataFormatError(IngestionError):
    """The response did not have the structure we expect."""
