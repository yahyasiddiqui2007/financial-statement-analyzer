"""The result type returned by every metric function.

A metric never returns a bare number. It returns a MetricResult that says
whether the calculation succeeded and, if not, why. That way a missing input
can never silently turn into a zero, and the UI can explain every blank cell.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum


class MetricStatus(StrEnum):
    """Why a metric does or does not have a value."""

    OK = "ok"
    # A required input was not provided (e.g. the company did not report it).
    MISSING_INPUT = "missing_input"
    # An input is impossible for that line item (e.g. negative total assets),
    # which points to a data or sign-convention error upstream.
    INVALID_INPUT = "invalid_input"
    # The denominator is exactly zero, so the ratio is undefined.
    ZERO_DENOMINATOR = "zero_denominator"
    # The math works, but the answer would mislead (e.g. ROE with negative equity).
    NOT_MEANINGFUL = "not_meaningful"


@dataclass(frozen=True, slots=True)
class MetricResult:
    """The outcome of one metric calculation.

    Attributes:
        name: Machine-friendly metric name, e.g. "gross_margin".
        formula: Human-readable formula, shown in the UI as a tooltip.
        status: OK, or the reason there is no value.
        value: The result when status is OK, otherwise None. Ratios are
            fractions (0.25 means 25%); dollar metrics are in the input currency.
        reason: A plain-English explanation when status is not OK.
        inputs: The exact inputs used, so every result can be traced and checked.
    """

    name: str
    formula: str
    status: MetricStatus
    value: Decimal | None = None
    reason: str | None = None
    inputs: dict[str, Decimal | None] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Enforce the rule "a value exists if and only if the status is OK".
        if self.status is MetricStatus.OK and self.value is None:
            raise ValueError(f"{self.name}: OK result must have a value")
        if self.status is not MetricStatus.OK and self.value is not None:
            raise ValueError(f"{self.name}: non-OK result must not have a value")

    @property
    def is_ok(self) -> bool:
        return self.status is MetricStatus.OK
