"""Profitability metrics: how much profit a company keeps from its sales and assets.

Margins (gross, operating, net) compare a profit line to revenue for the
same period. Returns (ROA, ROE) compare a full period's profit to the
average balance of assets or equity held during that period.
"""

from __future__ import annotations

from fsa.analytics._checks import Amount, average, check_inputs, divide, failure
from fsa.analytics.results import MetricResult, MetricStatus

GROSS_MARGIN_FORMULA = "Gross profit / Revenue"
OPERATING_MARGIN_FORMULA = "Operating income / Revenue"
NET_MARGIN_FORMULA = "Net income / Revenue"
ROA_FORMULA = "Net income / Average total assets (beginning and end of period)"
ROE_FORMULA = "Net income / Average shareholders' equity (beginning and end of period)"


def _margin(
    name: str, formula: str, profit_label: str, profit: Amount, revenue: Amount
) -> MetricResult:
    """Shared logic for all three margins: profit / revenue.

    Profit may be negative (a loss gives a negative margin). Revenue may not.
    """
    checked = check_inputs(
        name, formula, {profit_label: profit, "revenue": revenue}, non_negative=("revenue",)
    )
    if isinstance(checked, MetricResult):
        return checked
    return divide(
        name,
        formula,
        checked[profit_label],
        checked["revenue"],
        checked,
        denominator_label="Revenue",
    )


def gross_margin(gross_profit: Amount, revenue: Amount) -> MetricResult:
    """Share of revenue left after the direct cost of producing what was sold.

    Example: revenue 1,000 and gross profit 400 gives 0.40 (40%).
    """
    return _margin("gross_margin", GROSS_MARGIN_FORMULA, "gross_profit", gross_profit, revenue)


def operating_margin(operating_income: Amount, revenue: Amount) -> MetricResult:
    """Share of revenue left after all operating costs (COGS, R&D, SG&A, ...).

    Example: revenue 1,000 and operating income 150 gives 0.15 (15%).
    """
    return _margin(
        "operating_margin", OPERATING_MARGIN_FORMULA, "operating_income", operating_income, revenue
    )


def net_margin(net_income: Amount, revenue: Amount) -> MetricResult:
    """Share of revenue left after every expense, including interest and taxes.

    Example: revenue 1,000 and net income 80 gives 0.08 (8%).
    """
    return _margin("net_margin", NET_MARGIN_FORMULA, "net_income", net_income, revenue)


def return_on_assets(
    net_income: Amount, total_assets_begin: Amount, total_assets_end: Amount
) -> MetricResult:
    """Return on assets (ROA): profit generated per dollar of assets.

    Uses the average of beginning and ending total assets because net income
    is earned over the whole period, while assets are a snapshot at one date.
    "Beginning" is the balance at the end of the prior period.

    Example: net income 50, assets 900 → 1,100 (average 1,000) gives 0.05 (5%).
    """
    name = "return_on_assets"
    checked = check_inputs(
        name,
        ROA_FORMULA,
        {
            "net_income": net_income,
            "total_assets_begin": total_assets_begin,
            "total_assets_end": total_assets_end,
        },
        non_negative=("total_assets_begin", "total_assets_end"),
    )
    if isinstance(checked, MetricResult):
        return checked

    average_assets = average(checked["total_assets_begin"], checked["total_assets_end"])
    return divide(
        name,
        ROA_FORMULA,
        checked["net_income"],
        average_assets,
        checked,
        denominator_label="Average total assets",
    )


def return_on_equity(net_income: Amount, equity_begin: Amount, equity_end: Amount) -> MetricResult:
    """Return on equity (ROE): profit generated per dollar of shareholders' equity.

    Uses average equity for the same reason ROA uses average assets.

    Example: net income 30, equity 180 → 220 (average 200) gives 0.15 (15%).

    Edge cases:
        - Negative equity at either date: NOT_MEANINGFUL. Companies with large
          buybacks or accumulated losses can have negative equity; dividing by
          it flips the sign, so a profitable company would show a negative ROE.
        - Zero average equity: ZERO_DENOMINATOR.
    """
    name = "return_on_equity"
    checked = check_inputs(
        name,
        ROE_FORMULA,
        {"net_income": net_income, "equity_begin": equity_begin, "equity_end": equity_end},
    )
    if isinstance(checked, MetricResult):
        return checked

    if checked["equity_begin"] < 0 or checked["equity_end"] < 0:
        return failure(
            name,
            ROE_FORMULA,
            MetricStatus.NOT_MEANINGFUL,
            "Shareholders' equity is negative, so ROE would be misleading.",
            checked,
        )

    average_equity = average(checked["equity_begin"], checked["equity_end"])
    return divide(
        name,
        ROE_FORMULA,
        checked["net_income"],
        average_equity,
        checked,
        denominator_label="Average shareholders' equity",
    )
