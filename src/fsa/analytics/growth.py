"""Growth metrics: how fast a line item changes from one period to the next."""

from __future__ import annotations

from decimal import Decimal

from fsa.analytics._checks import Amount, check_inputs, divide, failure, nth_root, success
from fsa.analytics.results import MetricResult, MetricStatus

REVENUE_GROWTH_FORMULA = "(Current revenue − Prior revenue) / Prior revenue"


def revenue_growth(current_revenue: Amount, prior_revenue: Amount) -> MetricResult:
    """Year-over-year (or period-over-period) revenue growth.

    Example: revenue rising from 100 to 110 gives 0.10 (10% growth).

    Both values must cover periods of the same length (two fiscal years, or
    the same quarter in two years); this function cannot check that.

    Edge cases:
        - Prior revenue of zero: growth from nothing is undefined (ZERO_DENOMINATOR).
        - Negative revenue: not a real revenue figure (INVALID_INPUT).
    """
    name = "revenue_growth"
    checked = check_inputs(
        name,
        REVENUE_GROWTH_FORMULA,
        {"current_revenue": current_revenue, "prior_revenue": prior_revenue},
        non_negative=("current_revenue", "prior_revenue"),
    )
    if isinstance(checked, MetricResult):
        return checked

    current, prior = checked["current_revenue"], checked["prior_revenue"]
    return divide(
        name,
        REVENUE_GROWTH_FORMULA,
        current - prior,
        prior,
        checked,
        denominator_label="Prior revenue",
    )


PERCENT_CHANGE_FORMULA = "(Current − Prior) / Prior"


def percent_change(current: Amount, prior: Amount) -> MetricResult:
    """Year-over-year change for any line item (net income, total assets, ...).

    Unlike revenue, many line items can be negative. When the prior value is
    negative, the percentage has a misleading sign: a loss shrinking from −100
    to −50 would show as −50% even though results improved. Those cases
    return NOT_MEANINGFUL; the dollar amounts still tell the story.

    Example: 200 → 250 gives 0.25 (+25%).
    """
    name = "percent_change"
    checked = check_inputs(name, PERCENT_CHANGE_FORMULA, {"current": current, "prior": prior})
    if isinstance(checked, MetricResult):
        return checked

    current_value, prior_value = checked["current"], checked["prior"]
    if prior_value < 0:
        return failure(
            name,
            PERCENT_CHANGE_FORMULA,
            MetricStatus.NOT_MEANINGFUL,
            "The prior value is negative, so a percentage change would have a misleading sign.",
            checked,
        )
    return divide(
        name,
        PERCENT_CHANGE_FORMULA,
        current_value - prior_value,
        prior_value,
        checked,
        denominator_label="Prior value",
    )


CAGR_FORMULA = "(Ending value / Beginning value)^(1 / Years) − 1"


def compound_annual_growth_rate(beginning: Amount, ending: Amount, years: int) -> MetricResult:
    """The steady yearly growth rate that turns `beginning` into `ending`.

    Example: 100 → 121 over 2 years gives 0.10 (10% a year), even though the
    path may have been +5% then +15%. CAGR smooths out the bumps, which makes
    periods of different lengths comparable.

    `years` is the number of yearly steps (5 fiscal years → 4 steps).

    Edge cases:
        - Beginning value of zero: ZERO_DENOMINATOR.
        - Negative beginning or ending value (e.g. a net loss): NOT_MEANINGFUL,
          because a growth rate between a loss and a profit has no sensible value.
    """
    if years < 1:
        raise ValueError("years must be at least 1")
    name = "cagr"
    checked = check_inputs(
        name, CAGR_FORMULA, {"beginning_value": beginning, "ending_value": ending}
    )
    if isinstance(checked, MetricResult):
        return checked
    inputs = {**checked, "years": Decimal(years)}

    start, end = checked["beginning_value"], checked["ending_value"]
    if start < 0 or end < 0:
        return failure(
            name,
            CAGR_FORMULA,
            MetricStatus.NOT_MEANINGFUL,
            "A compound growth rate needs positive values at both ends; "
            "it is not meaningful when either value is negative.",
            inputs,
        )
    ratio = divide(name, CAGR_FORMULA, end, start, inputs, denominator_label="Beginning value")
    if ratio.value is None:
        return ratio
    return success(name, CAGR_FORMULA, nth_root(ratio.value, years) - 1, inputs)


ABSOLUTE_CHANGE_FORMULA = "Current − Prior"


def absolute_change(current: Amount, prior: Amount) -> MetricResult:
    """The plain difference between two values, in their own units.

    For dollar amounts this is a dollar change; for margins (fractions) it is
    a change in percentage points: 0.32 − 0.30 = 0.02, i.e. +2 points.
    """
    name = "absolute_change"
    checked = check_inputs(name, ABSOLUTE_CHANGE_FORMULA, {"current": current, "prior": prior})
    if isinstance(checked, MetricResult):
        return checked
    return success(name, ABSOLUTE_CHANGE_FORMULA, checked["current"] - checked["prior"], checked)
