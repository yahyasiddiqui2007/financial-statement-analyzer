"""The app's internal format for financial data.

Everything after ingestion (the calculation engine, a future API, the
frontend) uses these classes and never sees the SEC's JSON. If we ever
switch data providers, only the ingestion layer has to change.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from fsa.ingestion.line_items import LineItem


@dataclass(frozen=True, slots=True)
class Company:
    cik: str  # 10 digits, zero-padded, e.g. "0000320193"
    ticker: str
    name: str


@dataclass(frozen=True, slots=True)
class SourceFact:
    """One reported number and the filing it came from, for traceability."""

    tag: str
    value: Decimal
    accession_number: str  # the filing's unique ID, e.g. "0000320193-24-000123"
    form: str  # "10-K" or "10-K/A"
    filed: date

    def filing_url(self, cik: str) -> str:
        """Link to the filing's index page on sec.gov."""
        return (
            f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
            f"{self.accession_number.replace('-', '')}/"
        )


@dataclass(frozen=True, slots=True)
class LineItemValue:
    """The value we chose for one line item in one period, plus where it came from.

    Attributes:
        sources: One fact if reported directly; several if derived.
        derivation: How it was derived (e.g. "Revenue − Cost of revenue"), or
            None when the company reported it directly.
        restated: True when filings disagree about this value, meaning a later
            filing changed it. We use the most recently filed value.
    """

    item: LineItem
    value: Decimal
    sources: tuple[SourceFact, ...]
    derivation: str | None = None
    restated: bool = False

    @property
    def is_derived(self) -> bool:
        return self.derivation is not None


@dataclass(frozen=True, slots=True)
class AnnualPeriod:
    """One fiscal year of normalized statement data.

    A period is identified by its end date. `fiscal_year` is the company's own
    label (Apple's year ending 2024-09-28 is "fiscal 2024"); it is None when
    no filing tells us the label, because guessing is error-prone for
    companies whose year ends in January.
    """

    start: date
    end: date
    fiscal_year: int | None
    values: Mapping[LineItem, LineItemValue] = field(default_factory=dict)

    def get(self, item: LineItem) -> Decimal | None:
        """The value for a line item, or None if it was not reported."""
        line = self.values.get(item)
        return line.value if line is not None else None

    @property
    def label(self) -> str:
        if self.fiscal_year is not None:
            return f"FY{self.fiscal_year} (ended {self.end.isoformat()})"
        return f"Year ended {self.end.isoformat()}"


@dataclass(frozen=True, slots=True)
class FinancialHistory:
    """All annual periods we found for a company, oldest first."""

    company: Company
    periods: tuple[AnnualPeriod, ...]
    # Data-quality notes worth showing to the user (conflicts, unsupported units, ...).
    warnings: tuple[str, ...] = ()

    @property
    def latest(self) -> AnnualPeriod | None:
        return self.periods[-1] if self.periods else None

    def prior_to(self, period: AnnualPeriod) -> AnnualPeriod | None:
        """The fiscal year immediately before `period`, or None.

        Returns None if there is a gap (e.g. a missing year, or a fiscal
        year-end change), because comparing non-adjacent years as if they
        were consecutive would give wrong growth rates and averages.
        """
        for candidate in self.periods:
            if (period.start - candidate.end).days == 1:
                return candidate
        return None
