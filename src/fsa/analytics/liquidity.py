"""Liquidity metrics: can the company pay bills due within the next year?

All inputs are balance-sheet amounts from the same date.
"""

from __future__ import annotations

from fsa.analytics._checks import Amount, check_inputs, divide, success
from fsa.analytics.results import MetricResult

CURRENT_RATIO_FORMULA = "Current assets / Current liabilities"
QUICK_RATIO_FORMULA = (
    "(Cash and equivalents + Short-term investments + Accounts receivable) / Current liabilities"
)


def current_ratio(current_assets: Amount, current_liabilities: Amount) -> MetricResult:
    """Current assets available per dollar of current liabilities.

    Example: current assets 300, current liabilities 200 gives 1.5.
    """
    name = "current_ratio"
    checked = check_inputs(
        name,
        CURRENT_RATIO_FORMULA,
        {"current_assets": current_assets, "current_liabilities": current_liabilities},
        non_negative=("current_assets", "current_liabilities"),
    )
    if isinstance(checked, MetricResult):
        return checked
    return divide(
        name,
        CURRENT_RATIO_FORMULA,
        checked["current_assets"],
        checked["current_liabilities"],
        checked,
        denominator_label="Current liabilities",
    )


def quick_ratio(
    cash_and_equivalents: Amount,
    short_term_investments: Amount,
    accounts_receivable: Amount,
    current_liabilities: Amount,
) -> MetricResult:
    """Like the current ratio, but counting only assets that turn into cash quickly.

    Inventory and prepaid expenses are left out because they may take months
    to become cash, or may not convert at full value.

    Example: cash 50, investments 30, receivables 70, current liabilities 100 gives 1.5.

    Every input is required. If a company truly has no short-term investments,
    the caller must pass 0 explicitly; a missing value is never assumed to be zero.
    """
    name = "quick_ratio"
    checked = check_inputs(
        name,
        QUICK_RATIO_FORMULA,
        {
            "cash_and_equivalents": cash_and_equivalents,
            "short_term_investments": short_term_investments,
            "accounts_receivable": accounts_receivable,
            "current_liabilities": current_liabilities,
        },
        non_negative=(
            "cash_and_equivalents",
            "short_term_investments",
            "accounts_receivable",
            "current_liabilities",
        ),
    )
    if isinstance(checked, MetricResult):
        return checked

    quick_assets = (
        checked["cash_and_equivalents"]
        + checked["short_term_investments"]
        + checked["accounts_receivable"]
    )
    return divide(
        name,
        QUICK_RATIO_FORMULA,
        quick_assets,
        checked["current_liabilities"],
        checked,
        denominator_label="Current liabilities",
    )


WORKING_CAPITAL_FORMULA = "Current assets − Current liabilities"


def working_capital(current_assets: Amount, current_liabilities: Amount) -> MetricResult:
    """Short-term assets left over after covering short-term obligations, in dollars.

    Example: current assets 300, current liabilities 200 gives 100.

    It can be negative, meaning current liabilities exceed current assets.
    Some businesses run this way on purpose (they collect cash from customers
    before paying suppliers), so a negative value is reported as-is.
    """
    name = "working_capital"
    checked = check_inputs(
        name,
        WORKING_CAPITAL_FORMULA,
        {"current_assets": current_assets, "current_liabilities": current_liabilities},
        non_negative=("current_assets", "current_liabilities"),
    )
    if isinstance(checked, MetricResult):
        return checked
    value = checked["current_assets"] - checked["current_liabilities"]
    return success(name, WORKING_CAPITAL_FORMULA, value, checked)
