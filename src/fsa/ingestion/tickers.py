"""Turn a ticker symbol like "AAPL" into the SEC's permanent company ID (CIK).

Tickers can change or be reused, but a CIK never changes, so every SEC API
call uses the CIK.
"""

from __future__ import annotations

import re
from typing import Any

from fsa.ingestion.errors import DataFormatError, TickerNotFoundError
from fsa.ingestion.models import Company

# Letters, digits and hyphens, e.g. "AAPL", "BRK-B".
_TICKER_PATTERN = re.compile(r"^[A-Z0-9-]{1,10}$")


def normalize_ticker(raw: str) -> str:
    """Clean up user input: " brk.b " → "BRK-B" (the SEC writes class shares with a hyphen)."""
    ticker = raw.strip().upper().replace(".", "-")
    if not _TICKER_PATTERN.fullmatch(ticker):
        raise TickerNotFoundError(f"{raw!r} is not a valid ticker symbol.")
    return ticker


def find_company(tickers_payload: Any, ticker: str) -> Company:
    """Look up a ticker in the SEC's company_tickers.json.

    The file looks like:
        {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}, ...}
    """
    wanted = normalize_ticker(ticker)
    if not isinstance(tickers_payload, dict):
        raise DataFormatError("Ticker list should be a JSON object.")

    for entry in tickers_payload.values():
        if not isinstance(entry, dict):
            raise DataFormatError("Each ticker entry should be a JSON object.")
        entry_ticker = entry.get("ticker")
        if not isinstance(entry_ticker, str) or entry_ticker.upper() != wanted:
            continue

        cik, name = entry.get("cik_str"), entry.get("title")
        if isinstance(cik, bool) or not isinstance(cik, int) or not isinstance(name, str):
            raise DataFormatError(f"Ticker entry for {wanted} is malformed: {entry!r}")
        return Company(cik=f"{cik:010d}", ticker=wanted, name=name)

    raise TickerNotFoundError(f"No SEC-registered company has the ticker {wanted}.")
