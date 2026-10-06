"""Leverage metrics: how much the company relies on borrowed money."""

from __future__ import annotations

from fsa.analytics._checks import Amount, check_inputs, divide, failure
from fsa.analytics.results import MetricResult, MetricStatus

DEBT_TO_EQUITY_FORMULA = "Total debt / Total shareholders' equity"


def debt_to_equity(total_debt: Amount, total_equity: Amount) -> MetricResult:
    """Dollars of debt per dollar of shareholders' equity.

    "Total debt" means interest-bearing borrowings (short-term debt, the
    current portion of long-term debt, and long-term debt). It is NOT total
    liabilities, which would also include things like accounts payable.

    Example: debt 150, equity 100 gives 1.5.

    Edge cases:
        - Negative equity: NOT_MEANINGFUL (the ratio would be negative, which
          looks safer than zero debt even though it means the opposite).
        - Zero equity: ZERO_DENOMINATOR.
    """
    name = "debt_to_equity"
    checked = check_inputs(
        name,
        DEBT_TO_EQUITY_FORMULA,
        {"total_debt": total_debt, "total_equity": total_equity},
        non_negative=("total_debt",),
    )
    if isinstance(checked, MetricResult):
        return checked

    if checked["total_equity"] < 0:
        return failure(
            name,
            DEBT_TO_EQUITY_FORMULA,
            MetricStatus.NOT_MEANINGFUL,
            "Shareholders' equity is negative, so debt-to-equity would be misleading.",
            checked,
        )
    return divide(
        name,
        DEBT_TO_EQUITY_FORMULA,
        checked["total_debt"],
        checked["total_equity"],
        checked,
        denominator_label="Total shareholders' equity",
    )
