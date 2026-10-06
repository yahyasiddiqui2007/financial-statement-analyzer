"""Fetch financial statements from SEC EDGAR and normalize them."""

from fsa.ingestion.errors import (
    CompanyDataNotFoundError,
    DataFormatError,
    IngestionError,
    SecAccessDeniedError,
    SecApiError,
    TickerNotFoundError,
)
from fsa.ingestion.line_items import DEFINITIONS, LineItem, Statement
from fsa.ingestion.models import (
    AnnualPeriod,
    Company,
    FinancialHistory,
    LineItemValue,
    SourceFact,
)
from fsa.ingestion.sec_client import SecClient
from fsa.ingestion.service import load_financial_history

__all__ = [
    "DEFINITIONS",
    "AnnualPeriod",
    "Company",
    "CompanyDataNotFoundError",
    "DataFormatError",
    "FinancialHistory",
    "IngestionError",
    "LineItem",
    "LineItemValue",
    "SecAccessDeniedError",
    "SecApiError",
    "SecClient",
    "SourceFact",
    "Statement",
    "TickerNotFoundError",
    "load_financial_history",
]
