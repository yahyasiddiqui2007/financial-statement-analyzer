"""Tests for the shared input checks and the MetricResult rules.

These behaviors apply to every metric, so they are tested once here using
gross_margin as a representative metric, plus a few direct helper tests.
"""

from decimal import Decimal

import pytest

from fsa.analytics import MetricResult, MetricStatus, gross_margin
from fsa.analytics._checks import average, to_decimal

D = Decimal


class TestToDecimal:
    def test_none_means_not_reported(self) -> None:
        assert to_decimal("x", None) is None

    def test_int_is_accepted(self) -> None:
        assert to_decimal("x", 42) == D("42")

    def test_decimal_is_accepted_unchanged(self) -> None:
        assert to_decimal("x", D("1.23")) == D("1.23")

    def test_float_is_rejected(self) -> None:
        with pytest.raises(TypeError, match="Floats are rejected"):
            to_decimal("revenue", 0.1)

    def test_bool_is_rejected(self) -> None:
        # True is technically an int in Python; it must not become 1.
        with pytest.raises(TypeError):
            to_decimal("revenue", True)

    def test_string_is_rejected(self) -> None:
        with pytest.raises(TypeError):
            to_decimal("revenue", "100")


class TestSharedInputRules:
    def test_float_input_raises_through_metric(self) -> None:
        with pytest.raises(TypeError):
            gross_margin(40.0, D("100"))  # type: ignore[arg-type]

    def test_all_missing_inputs_are_named(self) -> None:
        result = gross_margin(None, None)
        assert result.status is MetricStatus.MISSING_INPUT
        assert result.value is None
        assert result.reason is not None
        assert "gross_profit" in result.reason
        assert "revenue" in result.reason

    @pytest.mark.parametrize("bad", [D("NaN"), D("Infinity"), D("-Infinity")])
    def test_non_finite_input_is_invalid(self, bad: Decimal) -> None:
        result = gross_margin(bad, D("100"))
        assert result.status is MetricStatus.INVALID_INPUT
        assert result.value is None

    def test_inputs_are_recorded_for_traceability(self) -> None:
        result = gross_margin(D("40"), 100)
        assert result.inputs == {"gross_profit": D("40"), "revenue": D("100")}

    def test_inputs_are_recorded_even_when_missing(self) -> None:
        result = gross_margin(D("40"), None)
        assert result.inputs == {"gross_profit": D("40"), "revenue": None}

    def test_formula_is_always_present(self) -> None:
        assert gross_margin(None, None).formula == "Gross profit / Revenue"

    def test_very_large_values_keep_precision(self) -> None:
        # Trillions of dollars with cents: no rounding should occur.
        result = gross_margin(D("1234567890123.45"), D("2469135780246.90"))
        assert result.value == D("0.5")


class TestAverage:
    def test_average_of_two_balances(self) -> None:
        assert average(D("900"), D("1100")) == D("1000")

    def test_average_keeps_fractions(self) -> None:
        assert average(D("1"), D("2")) == D("1.5")


class TestMetricResultInvariants:
    def test_ok_without_value_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            MetricResult(name="m", formula="f", status=MetricStatus.OK)

    def test_failure_with_value_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            MetricResult(name="m", formula="f", status=MetricStatus.MISSING_INPUT, value=D("1"))

    def test_is_ok(self) -> None:
        assert gross_margin(D("1"), D("2")).is_ok
        assert not gross_margin(None, D("2")).is_ok

    def test_result_is_immutable(self) -> None:
        result = gross_margin(D("1"), D("2"))
        with pytest.raises(AttributeError):
            result.value = D("999")  # type: ignore[misc]
