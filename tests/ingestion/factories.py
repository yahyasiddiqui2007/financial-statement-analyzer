"""Helpers for building fake SEC data in tests. All companies and numbers are fictional."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from fsa.ingestion.companyfacts import RawFact
from fsa.ingestion.models import Company

FIXTURES = Path(__file__).parent / "fixtures"

COMPANY = Company(cik="0001234567", ticker="EXMP", name="Example Manufacturing Corp")


def load_fixture(name: str) -> Any:
    """Load a JSON fixture the same way the SEC client parses responses."""
    return json.loads((FIXTURES / name).read_text(), parse_float=Decimal)


def fact(
    tag: str,
    value: int | str,
    end: str,
    start: str | None = None,
    *,
    form: str = "10-K",
    filed: str = "2025-02-15",
    accession: str | None = None,
    fiscal_year: int | None = None,
    unit: str = "USD",
) -> RawFact:
    """Build one RawFact. Dates are ISO strings to keep tests short."""
    return RawFact(
        tag=tag,
        unit=unit,
        value=Decimal(value),
        start=date.fromisoformat(start) if start else None,
        end=date.fromisoformat(end),
        form=form,
        accession_number=accession or f"acc-{filed}",
        filed=date.fromisoformat(filed),
        filing_fiscal_year=fiscal_year,
    )


def calendar_year(tag: str, year: int, value: int | str, **kwargs: Any) -> RawFact:
    """A duration fact covering one calendar year."""
    return fact(tag, value, f"{year}-12-31", f"{year}-01-01", **kwargs)


def year_end(tag: str, year: int, value: int | str, **kwargs: Any) -> RawFact:
    """An instant (balance sheet) fact on December 31."""
    return fact(tag, value, f"{year}-12-31", **kwargs)
