"""The JSON shapes the API returns, defined with Pydantic.

FastAPI uses these to validate every response and to generate interactive
docs at /docs. The frontend's TypeScript types (frontend/src/api/types.ts)
mirror these classes one-to-one.

Money and ratio values are sent as STRINGS like "391035000000" or
"0.2022", not JSON numbers. JSON numbers become binary floats in the
browser; strings preserve the exact Decimal value from the pipeline, and the
frontend only converts them for display.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from fsa.analysis import MetricFormat


class CompanyOut(BaseModel):
    cik: str
    ticker: str
    name: str
    edgar_url: str  # the company's filing list on sec.gov


class DataSourceOut(BaseModel):
    provider: str
    url: str
    retrieved_at: datetime


class PeriodOut(BaseModel):
    start: date
    end: date
    fiscal_year: int | None
    label: str
    # False when the year before is missing, so growth can't be computed.
    has_prior: bool


class SourceFactOut(BaseModel):
    tag: str
    accession_number: str
    form: str
    filed: date
    url: str


class ChangeOut(BaseModel):
    """Year-over-year percentage change, or why there isn't one."""

    value: str | None
    status: str
    reason: str | None


class CellOut(BaseModel):
    value: str | None  # None = not reported
    derived: bool
    derivation: str | None
    restated: bool
    sources: list[SourceFactOut]
    change: ChangeOut | None  # None when there is no prior year to compare with


class RowOut(BaseModel):
    item: str
    label: str
    cells: list[CellOut]  # one per period, same order as FinancialsOut.periods


class StatementOut(BaseModel):
    id: str
    title: str
    rows: list[RowOut]


class MetricValueOut(BaseModel):
    value: str | None
    status: str
    reason: str | None
    # Current minus prior year's value (e.g. 0.007 = +0.7 percentage points
    # for a margin). None if either year has no value.
    difference: str | None
    inputs: dict[str, str | None]


class MetricOut(BaseModel):
    name: str
    label: str
    format: MetricFormat
    formula: str
    values: list[MetricValueOut]  # one per period


TrendValueFormat = Literal[
    "usd", "usd_change", "percent", "percent_change", "pp_change", "ratio", "ratio_change"
]


class TrendStatisticOut(BaseModel):
    """A calculated number behind a finding, with everything needed to recompute it."""

    key: str
    label: str
    format: TrendValueFormat
    value: str | None
    status: str
    reason: str | None
    formula: str
    inputs: dict[str, str | None]


class TrendPointOut(BaseModel):
    label: str
    end: date
    value: str | None


class TrendSeriesOut(BaseModel):
    key: str
    label: str
    format: TrendValueFormat
    points: list[TrendPointOut]


class TrendFindingOut(BaseModel):
    topic: str
    title: str
    direction: Literal["increasing", "decreasing", "stable", "mixed", "insufficient_data"]
    summary: str
    details: list[str]
    statistics: list[TrendStatisticOut]
    series: list[TrendSeriesOut]
    method: str


class TrendReportOut(BaseModel):
    requested_years: int
    years: int
    start_label: str | None
    end_label: str | None
    findings: list[TrendFindingOut]
    notes: list[str]


class FinancialsOut(BaseModel):
    company: CompanyOut
    source: DataSourceOut
    periods: list[PeriodOut]  # oldest first
    statements: list[StatementOut]
    metrics: list[MetricOut]
    # Trend analysis over the latest 3 and 5 fiscal years (or fewer, if that's all there is).
    trends: list[TrendReportOut]
    warnings: list[str]


class AIEvidenceOut(BaseModel):
    id: str
    kind: Literal["line_item", "metric", "trend", "trend_statistic"]
    label: str
    period: str | None
    value: str
    note: str | None


class AIClaimOut(BaseModel):
    statement: str
    evidence: list[AIEvidenceOut]  # every cited fact, so the claim can be checked


class AIRejectedClaimOut(BaseModel):
    section: Literal["strengths", "concerns", "trends", "questions"]
    statement: str
    reason: str


class AIAnalysisOut(BaseModel):
    ticker: str
    model: str
    generated_at: datetime
    disclaimer: str
    evidence_count: int  # how many facts the model was given
    strengths: list[AIClaimOut]
    concerns: list[AIClaimOut]
    trends: list[AIClaimOut]
    questions: list[AIClaimOut]
    # Claims removed by verification (shown so the filtering is transparent).
    rejected: list[AIRejectedClaimOut]


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorOut(BaseModel):
    error: ErrorDetail
