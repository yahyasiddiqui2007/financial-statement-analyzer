"""Data types for trend findings.

Every finding carries its evidence: the yearly values it looked at (series),
the calculated statistics behind its conclusion (each a MetricResult from the
calculation engine, with formula and inputs), and the rule that turned those
numbers into a direction. Nothing in a finding is unverifiable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from fsa.analytics import MetricResult

# How the frontend should display a number.
ValueFormat = Literal[
    "usd",  # dollar amount
    "usd_change",  # signed dollar change
    "percent",  # fraction shown as a percentage (0.25 → 25%)
    "percent_change",  # signed percentage change
    "pp_change",  # change between two percentages, in percentage points
    "ratio",  # e.g. 1.50x
    "ratio_change",  # signed change in a ratio
]


class Direction(StrEnum):
    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"
    MIXED = "mixed"  # parts of the finding moved in different directions
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True, slots=True)
class Statistic:
    """One calculated number supporting a finding, e.g. a 5-year CAGR."""

    key: str  # stable id within its finding, e.g. "cagr" (labels can change; keys don't)
    label: str
    format: ValueFormat
    result: MetricResult


@dataclass(frozen=True, slots=True)
class SeriesPoint:
    label: str  # "FY2025"
    end: date
    value: Decimal | None


@dataclass(frozen=True, slots=True)
class Series:
    """A line item or metric for every year in the window, oldest first."""

    key: str
    label: str
    format: ValueFormat
    points: tuple[SeriesPoint, ...]


@dataclass(frozen=True, slots=True)
class TrendFinding:
    topic: str  # machine-friendly id, e.g. "revenue_growth"
    title: str
    direction: Direction
    summary: str  # one factual sentence
    details: tuple[str, ...]  # further factual sentences
    statistics: tuple[Statistic, ...]
    series: tuple[Series, ...]
    method: str  # the rule used to choose the direction


@dataclass(frozen=True, slots=True)
class TrendReport:
    requested_years: int
    years: int  # fiscal years actually analyzed (may be fewer than requested)
    start_label: str | None
    end_label: str | None
    findings: tuple[TrendFinding, ...]
    notes: tuple[str, ...]
