"""Shared input checks and safe arithmetic used by every metric.

The leading underscore in the module name means "internal": other parts of
the app should import the metric functions, not these helpers.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from decimal import ROUND_HALF_EVEN, Context, Decimal

from fsa.analytics.results import MetricResult, MetricStatus

# What a metric function accepts for each input. None means "not reported".
# Floats are deliberately excluded (see to_decimal).
Amount = Decimal | int | None

# A fixed arithmetic context so results never depend on global settings that
# some other code might have changed. 28 significant digits is far more than
# any financial statement needs.
_CONTEXT = Context(prec=28, rounding=ROUND_HALF_EVEN)


def to_decimal(name: str, value: object) -> Decimal | None:
    """Convert an input to Decimal, rejecting types that would lose precision.

    Passing the wrong type is a programming bug, not a data problem, so it
    raises an exception instead of returning a MetricResult.
    """
    if value is None:
        return None
    # bool is a subclass of int in Python, so True would otherwise become 1.
    if isinstance(value, bool) or not isinstance(value, (Decimal, int)):
        raise TypeError(
            f"{name} must be a Decimal, int, or None, got {type(value).__name__}. "
            "Floats are rejected because they cannot store most decimal amounts "
            "exactly; use Decimal('123.45') instead."
        )
    return Decimal(value)


def success(
    name: str, formula: str, value: Decimal, inputs: Mapping[str, Decimal | None]
) -> MetricResult:
    return MetricResult(
        name=name, formula=formula, status=MetricStatus.OK, value=value, inputs=dict(inputs)
    )


def failure(
    name: str,
    formula: str,
    status: MetricStatus,
    reason: str,
    inputs: Mapping[str, Decimal | None],
) -> MetricResult:
    return MetricResult(
        name=name, formula=formula, status=status, reason=reason, inputs=dict(inputs)
    )


def check_inputs(
    name: str,
    formula: str,
    inputs: Mapping[str, Amount],
    *,
    non_negative: Collection[str] = (),
) -> dict[str, Decimal] | MetricResult:
    """Validate a metric's inputs before any math happens.

    Returns either the inputs as Decimals (all present and valid), or a
    MetricResult explaining the first problem found. Callers check which one
    they got with `isinstance(checked, MetricResult)`.

    Args:
        non_negative: Inputs that can never be below zero for a real company,
            such as total assets. A negative value here usually means the data
            source used a different sign convention, so we refuse to guess.
    """
    converted = {key: to_decimal(key, value) for key, value in inputs.items()}

    missing = [key for key, value in converted.items() if value is None]
    if missing:
        return failure(
            name,
            formula,
            MetricStatus.MISSING_INPUT,
            f"Missing required input(s): {', '.join(missing)}.",
            converted,
        )

    values = {key: value for key, value in converted.items() if value is not None}

    non_finite = [key for key, value in values.items() if not value.is_finite()]
    if non_finite:
        return failure(
            name,
            formula,
            MetricStatus.INVALID_INPUT,
            f"Input(s) are not finite numbers: {', '.join(non_finite)}.",
            converted,
        )

    negative = [key for key in non_negative if values[key] < 0]
    if negative:
        details = ", ".join(f"{key}={values[key]}" for key in negative)
        return failure(
            name,
            formula,
            MetricStatus.INVALID_INPUT,
            f"Input(s) cannot be negative: {details}. Check the source data's sign convention.",
            converted,
        )

    return values


def divide(
    name: str,
    formula: str,
    numerator: Decimal,
    denominator: Decimal,
    inputs: Mapping[str, Decimal | None],
    *,
    denominator_label: str,
) -> MetricResult:
    """Divide, returning a ZERO_DENOMINATOR result instead of crashing on zero."""
    if denominator == 0:
        return failure(
            name,
            formula,
            MetricStatus.ZERO_DENOMINATOR,
            f"{denominator_label} is zero, so {name} is undefined.",
            inputs,
        )
    return success(name, formula, _CONTEXT.divide(numerator, denominator), inputs)


def average(first: Decimal, second: Decimal) -> Decimal:
    """Simple average of two balances, e.g. beginning and ending total assets."""
    return _CONTEXT.divide(_CONTEXT.add(first, second), Decimal(2))


def nth_root(value: Decimal, n: int) -> Decimal:
    """The n-th root of a non-negative number, e.g. nth_root(1.21, 2) = 1.1."""
    if n < 1:
        raise ValueError("n must be at least 1")
    return _CONTEXT.power(value, _CONTEXT.divide(Decimal(1), Decimal(n)))
