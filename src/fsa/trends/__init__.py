"""Multi-year trend findings, built only from calculated financial metrics."""

from fsa.trends.analyzer import MAX_YEARS, MIN_YEARS, analyze_trends, trend_window
from fsa.trends.models import (
    Direction,
    Series,
    SeriesPoint,
    Statistic,
    TrendFinding,
    TrendReport,
)

__all__ = [
    "MAX_YEARS",
    "MIN_YEARS",
    "Direction",
    "Series",
    "SeriesPoint",
    "Statistic",
    "TrendFinding",
    "TrendReport",
    "analyze_trends",
    "trend_window",
]
