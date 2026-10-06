"""The ingestion layer's front door: ticker in, normalized history out."""

from __future__ import annotations

from fsa.ingestion.companyfacts import parse_company_facts
from fsa.ingestion.errors import CompanyDataNotFoundError, DataFormatError
from fsa.ingestion.line_items import ALL_TAGS
from fsa.ingestion.models import FinancialHistory
from fsa.ingestion.normalize import build_financial_history
from fsa.ingestion.sec_client import SecClient
from fsa.ingestion.tickers import find_company


def load_financial_history(ticker: str, client: SecClient) -> FinancialHistory:
    """Fetch a company's annual financial statements from SEC EDGAR.

    Steps: ticker → CIK → companyfacts JSON → typed facts → annual periods.

    Raises:
        TickerNotFoundError: unknown ticker.
        CompanyDataNotFoundError: the company has no usable annual US GAAP data.
        SecApiError / SecAccessDeniedError / DataFormatError: network or SEC problems.
    """
    company = find_company(client.fetch_company_tickers(), ticker)
    parsed = parse_company_facts(client.fetch_company_facts(company.cik), tags=ALL_TAGS)
    if parsed.cik != company.cik:
        raise DataFormatError(
            f"Asked the SEC for CIK {company.cik} but received data for {parsed.cik}."
        )

    history = build_financial_history(company, parsed.facts, warnings=parsed.warnings)
    if not history.periods:
        raise CompanyDataNotFoundError(
            f"No annual 10-K data in US GAAP format was found for {company.ticker}. "
            "Foreign companies that report under IFRS (Form 20-F) are not supported yet."
        )
    return history
