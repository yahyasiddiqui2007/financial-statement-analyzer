"""Connects normalized statements to the calculation engine.

This is the only place that knows both sides: which LineItem feeds which
metric argument. The metric functions themselves stay independent of
where the data came from.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from fsa.analytics import (
    MetricResult,
    current_ratio,
    debt_to_equity,
    fcf_margin,
    free_cash_flow,
    gross_margin,
    net_margin,
    operating_margin,
    quick_ratio,
    return_on_assets,
    return_on_equity,
    revenue_growth,
)
from fsa.ingestion import AnnualPeriod, FinancialHistory, LineItem

MetricFormat = Literal["percent", "ratio", "usd"]

# Display order, label and number format for each metric.
METRIC_DISPLAY: dict[str, tuple[str, MetricFormat]] = {
    "revenue_growth": ("Revenue growth", "percent"),
    "gross_margin": ("Gross margin", "percent"),
    "operating_margin": ("Operating margin", "percent"),
    "net_margin": ("Net margin", "percent"),
    "return_on_assets": ("Return on assets", "percent"),
    "return_on_equity": ("Return on equity", "percent"),
    "current_ratio": ("Current ratio", "ratio"),
    "quick_ratio": ("Quick ratio", "ratio"),
    "debt_to_equity": ("Debt to equity", "ratio"),
    "free_cash_flow": ("Free cash flow", "usd"),
    "fcf_margin": ("FCF margin", "percent"),
}


def annual_metrics(history: FinancialHistory, period: AnnualPeriod) -> dict[str, MetricResult]:
    """Every metric for one fiscal year.

    Growth and average-balance metrics need the year before. If that year is
    missing or not directly adjacent, those inputs are None and the metrics
    report MISSING_INPUT instead of comparing the wrong years.
    """
    prior = history.prior_to(period)

    def now(item: LineItem) -> Decimal | None:
        return period.get(item)

    def before(item: LineItem) -> Decimal | None:
        return prior.get(item) if prior is not None else None

    results = [
        revenue_growth(now(LineItem.REVENUE), before(LineItem.REVENUE)),
        gross_margin(now(LineItem.GROSS_PROFIT), now(LineItem.REVENUE)),
        operating_margin(now(LineItem.OPERATING_INCOME), now(LineItem.REVENUE)),
        net_margin(now(LineItem.NET_INCOME), now(LineItem.REVENUE)),
        current_ratio(now(LineItem.CURRENT_ASSETS), now(LineItem.CURRENT_LIABILITIES)),
        quick_ratio(
            now(LineItem.CASH_AND_EQUIVALENTS),
            now(LineItem.SHORT_TERM_INVESTMENTS),
            now(LineItem.ACCOUNTS_RECEIVABLE),
            now(LineItem.CURRENT_LIABILITIES),
        ),
        debt_to_equity(now(LineItem.TOTAL_DEBT), now(LineItem.TOTAL_EQUITY)),
        return_on_assets(
            now(LineItem.NET_INCOME), before(LineItem.TOTAL_ASSETS), now(LineItem.TOTAL_ASSETS)
        ),
        return_on_equity(
            now(LineItem.NET_INCOME), before(LineItem.TOTAL_EQUITY), now(LineItem.TOTAL_EQUITY)
        ),
        free_cash_flow(now(LineItem.OPERATING_CASH_FLOW), now(LineItem.CAPITAL_EXPENDITURES)),
        fcf_margin(
            now(LineItem.OPERATING_CASH_FLOW),
            now(LineItem.CAPITAL_EXPENDITURES),
            now(LineItem.REVENUE),
        ),
    ]
    return {result.name: result for result in results}
