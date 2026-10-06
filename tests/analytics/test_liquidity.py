from decimal import Decimal

import pytest

from fsa.analytics import MetricStatus, current_ratio, quick_ratio, working_capital

D = Decimal


class TestCurrentRatio:
    @pytest.mark.parametrize(
        ("assets", "liabilities", "expected"),
        [
            (D("300"), D("200"), D("1.5")),
            (D("100"), D("200"), D("0.5")),
            (D("0"), D("200"), D("0")),
        ],
    )
    def test_values(self, assets: Decimal, liabilities: Decimal, expected: Decimal) -> None:
        assert current_ratio(assets, liabilities).value == expected

    def test_zero_liabilities_is_zero_denominator(self) -> None:
        result = current_ratio(D("300"), D("0"))
        assert result.status is MetricStatus.ZERO_DENOMINATOR
        assert result.value is None

    @pytest.mark.parametrize(("assets", "liabilities"), [(D("-1"), D("1")), (D("1"), D("-1"))])
    def test_negative_balance_is_invalid(self, assets: Decimal, liabilities: Decimal) -> None:
        assert current_ratio(assets, liabilities).status is MetricStatus.INVALID_INPUT

    @pytest.mark.parametrize(("assets", "liabilities"), [(None, D("1")), (D("1"), None)])
    def test_missing_input(self, assets: Decimal | None, liabilities: Decimal | None) -> None:
        assert current_ratio(assets, liabilities).status is MetricStatus.MISSING_INPUT


class TestQuickRatio:
    def test_value(self) -> None:
        # (50 + 30 + 70) / 100 = 1.5
        assert quick_ratio(D("50"), D("30"), D("70"), D("100")).value == D("1.5")

    def test_explicit_zero_investments_is_allowed(self) -> None:
        # (50 + 0 + 50) / 200 = 0.5
        assert quick_ratio(D("50"), D("0"), D("50"), D("200")).value == D("0.5")

    def test_missing_investments_is_not_treated_as_zero(self) -> None:
        result = quick_ratio(D("50"), None, D("50"), D("200"))
        assert result.status is MetricStatus.MISSING_INPUT
        assert result.reason is not None
        assert "short_term_investments" in result.reason

    def test_never_exceeds_current_ratio_for_same_company(self) -> None:
        # Quick assets are a subset of current assets (which also include inventory).
        cash, investments, receivables, inventory = D("50"), D("30"), D("70"), D("100")
        liabilities = D("200")
        quick = quick_ratio(cash, investments, receivables, liabilities).value
        current = current_ratio(cash + investments + receivables + inventory, liabilities).value
        assert quick is not None and current is not None
        assert quick <= current

    def test_zero_liabilities_is_zero_denominator(self) -> None:
        result = quick_ratio(D("50"), D("30"), D("70"), D("0"))
        assert result.status is MetricStatus.ZERO_DENOMINATOR

    @pytest.mark.parametrize("position", range(4))
    def test_negative_input_is_invalid(self, position: int) -> None:
        args = [D("10")] * 4
        args[position] = D("-1")
        assert quick_ratio(*args).status is MetricStatus.INVALID_INPUT

    @pytest.mark.parametrize("position", range(4))
    def test_missing_input(self, position: int) -> None:
        args: list[Decimal | None] = [D("10")] * 4
        args[position] = None
        assert quick_ratio(*args).status is MetricStatus.MISSING_INPUT


class TestWorkingCapital:
    @pytest.mark.parametrize(
        ("assets", "liabilities", "expected"),
        [(D("300"), D("200"), D("100")), (D("100"), D("250"), D("-150")), (D("0"), D("0"), D("0"))],
    )
    def test_values(self, assets: Decimal, liabilities: Decimal, expected: Decimal) -> None:
        result = working_capital(assets, liabilities)
        assert result.status is MetricStatus.OK
        assert result.value == expected

    def test_negative_balance_is_invalid(self) -> None:
        assert working_capital(D("-1"), D("1")).status is MetricStatus.INVALID_INPUT

    @pytest.mark.parametrize(("assets", "liabilities"), [(None, D("1")), (D("1"), None)])
    def test_missing_input(self, assets: Decimal | None, liabilities: Decimal | None) -> None:
        assert working_capital(assets, liabilities).status is MetricStatus.MISSING_INPUT
