"""The financial calculation engine.

Every function takes Decimal/int amounts (or None when a value is not
reported) and returns a MetricResult. Nothing here fetches data or prints.
"""

from fsa.analytics.cash_flow import fcf_margin, free_cash_flow
from fsa.analytics.growth import (
    absolute_change,
    compound_annual_growth_rate,
    percent_change,
    revenue_growth,
)
from fsa.analytics.leverage import debt_to_equity
from fsa.analytics.liquidity import current_ratio, quick_ratio, working_capital
from fsa.analytics.profitability import (
    gross_margin,
    net_margin,
    operating_margin,
    return_on_assets,
    return_on_equity,
)
from fsa.analytics.results import MetricResult, MetricStatus

__all__ = [
    "MetricResult",
    "MetricStatus",
    "absolute_change",
    "compound_annual_growth_rate",
    "current_ratio",
    "debt_to_equity",
    "fcf_margin",
    "free_cash_flow",
    "gross_margin",
    "net_margin",
    "operating_margin",
    "percent_change",
    "quick_ratio",
    "return_on_assets",
    "return_on_equity",
    "revenue_growth",
    "working_capital",
]
