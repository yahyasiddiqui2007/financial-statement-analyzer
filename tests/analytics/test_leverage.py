from decimal import Decimal

import pytest

from fsa.analytics import MetricStatus, debt_to_equity

D = Decimal


class TestDebtToEquity:
    @pytest.mark.parametrize(
        ("debt", "equity", "expected"),
        [
            (D("150"), D("100"), D("1.5")),
            (D("50"), D("200"), D("0.25")),
            (D("0"), D("100"), D("0")),  # debt-free company
        ],
    )
    def test_values(self, debt: Decimal, equity: Decimal, expected: Decimal) -> None:
        result = debt_to_equity(debt, equity)
        assert result.status is MetricStatus.OK
        assert result.value == expected

    def test_zero_equity_is_zero_denominator(self) -> None:
        result = debt_to_equity(D("100"), D("0"))
        assert result.status is MetricStatus.ZERO_DENOMINATOR
        assert result.value is None

    def test_negative_equity_is_not_meaningful(self) -> None:
        result = debt_to_equity(D("100"), D("-50"))
        assert result.status is MetricStatus.NOT_MEANINGFUL
        assert result.value is None

    def test_negative_debt_is_invalid(self) -> None:
        assert debt_to_equity(D("-1"), D("100")).status is MetricStatus.INVALID_INPUT

    @pytest.mark.parametrize(("debt", "equity"), [(None, D("1")), (D("1"), None)])
    def test_missing_input(self, debt: Decimal | None, equity: Decimal | None) -> None:
        assert debt_to_equity(debt, equity).status is MetricStatus.MISSING_INPUT
