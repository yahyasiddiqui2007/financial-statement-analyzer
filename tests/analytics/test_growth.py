from decimal import Decimal

import pytest

from fsa.analytics import (
    MetricStatus,
    absolute_change,
    compound_annual_growth_rate,
    percent_change,
    revenue_growth,
)

D = Decimal


class TestRevenueGrowth:
    @pytest.mark.parametrize(
        ("current", "prior", "expected"),
        [
            (D("110"), D("100"), D("0.1")),  # 10% growth
            (D("90"), D("100"), D("-0.1")),  # 10% decline
            (D("100"), D("100"), D("0")),  # flat
            (D("0"), D("100"), D("-1")),  # revenue fell to zero: -100%
            (D("300"), D("100"), D("2")),  # tripled: +200%
        ],
    )
    def test_values(self, current: Decimal, prior: Decimal, expected: Decimal) -> None:
        result = revenue_growth(current, prior)
        assert result.status is MetricStatus.OK
        assert result.value == expected

    def test_realistic_scale(self) -> None:
        # Hypothetical company, values in millions: 7,750 / 383,285 = 0.0202199...
        result = revenue_growth(D("391035"), D("383285"))
        assert result.value is not None
        assert round(result.value, 6) == D("0.020220")

    def test_int_inputs(self) -> None:
        assert revenue_growth(150, 100).value == D("0.5")

    def test_prior_zero_is_zero_denominator(self) -> None:
        result = revenue_growth(D("50"), D("0"))
        assert result.status is MetricStatus.ZERO_DENOMINATOR
        assert result.value is None

    @pytest.mark.parametrize(("current", "prior"), [(None, D("100")), (D("100"), None)])
    def test_missing_input(self, current: Decimal | None, prior: Decimal | None) -> None:
        assert revenue_growth(current, prior).status is MetricStatus.MISSING_INPUT

    @pytest.mark.parametrize(("current", "prior"), [(D("-1"), D("100")), (D("100"), D("-1"))])
    def test_negative_revenue_is_invalid(self, current: Decimal, prior: Decimal) -> None:
        assert revenue_growth(current, prior).status is MetricStatus.INVALID_INPUT


class TestPercentChange:
    @pytest.mark.parametrize(
        ("current", "prior", "expected"),
        [
            (D("250"), D("200"), D("0.25")),
            (D("150"), D("200"), D("-0.25")),
            (D("-50"), D("200"), D("-1.25")),  # profit turned into a loss
            (D("0"), D("200"), D("-1")),
        ],
    )
    def test_values(self, current: Decimal, prior: Decimal, expected: Decimal) -> None:
        result = percent_change(current, prior)
        assert result.status is MetricStatus.OK
        assert result.value == expected

    @pytest.mark.parametrize(("current", "prior"), [(D("-50"), D("-100")), (D("50"), D("-100"))])
    def test_negative_prior_is_not_meaningful(self, current: Decimal, prior: Decimal) -> None:
        result = percent_change(current, prior)
        assert result.status is MetricStatus.NOT_MEANINGFUL
        assert result.value is None

    def test_zero_prior_is_zero_denominator(self) -> None:
        assert percent_change(D("10"), D("0")).status is MetricStatus.ZERO_DENOMINATOR

    @pytest.mark.parametrize(("current", "prior"), [(None, D("1")), (D("1"), None)])
    def test_missing_input(self, current: Decimal | None, prior: Decimal | None) -> None:
        assert percent_change(current, prior).status is MetricStatus.MISSING_INPUT


class TestCompoundAnnualGrowthRate:
    @pytest.mark.parametrize(
        ("beginning", "ending", "years", "expected"),
        [
            (D("100"), D("121"), 2, D("0.1")),  # 10% a year
            (D("100"), D("100"), 4, D("0")),  # flat
            (D("100"), D("81"), 2, D("-0.1")),  # −10% a year
            (D("100"), D("150"), 1, D("0.5")),  # one step = simple growth
            (D("100"), D("0"), 3, D("-1")),  # fell to zero
        ],
    )
    def test_values(
        self, beginning: Decimal, ending: Decimal, years: int, expected: Decimal
    ) -> None:
        result = compound_annual_growth_rate(beginning, ending, years)
        assert result.status is MetricStatus.OK
        assert result.value is not None
        assert round(result.value, 12) == expected

    def test_records_years_as_input(self) -> None:
        result = compound_annual_growth_rate(D("100"), D("121"), 2)
        assert result.inputs["years"] == D("2")

    @pytest.mark.parametrize(("beginning", "ending"), [(D("-50"), D("100")), (D("100"), D("-50"))])
    def test_negative_values_are_not_meaningful(self, beginning: Decimal, ending: Decimal) -> None:
        result = compound_annual_growth_rate(beginning, ending, 3)
        assert result.status is MetricStatus.NOT_MEANINGFUL
        assert result.value is None

    def test_zero_beginning_is_zero_denominator(self) -> None:
        assert (
            compound_annual_growth_rate(D("0"), D("10"), 2).status is MetricStatus.ZERO_DENOMINATOR
        )

    def test_missing_input(self) -> None:
        assert compound_annual_growth_rate(None, D("1"), 2).status is MetricStatus.MISSING_INPUT

    def test_years_must_be_positive(self) -> None:
        with pytest.raises(ValueError):
            compound_annual_growth_rate(D("1"), D("2"), 0)


class TestAbsoluteChange:
    def test_dollars(self) -> None:
        assert absolute_change(D("120"), D("100")).value == D("20")

    def test_margin_points(self) -> None:
        assert absolute_change(D("0.32"), D("0.30")).value == D("0.02")

    def test_negative_values_are_fine(self) -> None:
        assert absolute_change(D("-50"), D("-100")).value == D("50")

    def test_missing_input(self) -> None:
        assert absolute_change(D("1"), None).status is MetricStatus.MISSING_INPUT
