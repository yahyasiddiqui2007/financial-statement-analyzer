from decimal import Decimal

import pytest

from fsa.analytics import MetricStatus, fcf_margin, free_cash_flow

D = Decimal


class TestFreeCashFlow:
    @pytest.mark.parametrize(
        ("ocf", "capex", "expected"),
        [
            (D("500"), D("120"), D("380")),
            (D("100"), D("150"), D("-50")),  # spending more than it generates
            (D("-40"), D("10"), D("-50")),  # operations burning cash
            (D("500"), D("0"), D("500")),  # no capital spending
        ],
    )
    def test_values(self, ocf: Decimal, capex: Decimal, expected: Decimal) -> None:
        result = free_cash_flow(ocf, capex)
        assert result.status is MetricStatus.OK
        assert result.value == expected

    def test_negative_capex_is_rejected_not_added(self) -> None:
        # If -120 were accepted, FCF would wrongly become 500 - (-120) = 620.
        result = free_cash_flow(D("500"), D("-120"))
        assert result.status is MetricStatus.INVALID_INPUT
        assert result.value is None

    @pytest.mark.parametrize(("ocf", "capex"), [(None, D("1")), (D("1"), None)])
    def test_missing_input(self, ocf: Decimal | None, capex: Decimal | None) -> None:
        assert free_cash_flow(ocf, capex).status is MetricStatus.MISSING_INPUT


class TestFcfMargin:
    def test_value(self) -> None:
        # (500 - 120) / 2000 = 0.19
        assert fcf_margin(D("500"), D("120"), D("2000")).value == D("0.19")

    def test_negative_fcf_gives_negative_margin(self) -> None:
        assert fcf_margin(D("100"), D("150"), D("1000")).value == D("-0.05")

    def test_consistent_with_free_cash_flow(self) -> None:
        fcf = free_cash_flow(D("500"), D("120")).value
        margin = fcf_margin(D("500"), D("120"), D("2000")).value
        assert fcf is not None and margin is not None
        assert margin == fcf / D("2000")

    def test_zero_revenue_is_zero_denominator(self) -> None:
        result = fcf_margin(D("500"), D("120"), D("0"))
        assert result.status is MetricStatus.ZERO_DENOMINATOR
        assert result.value is None

    @pytest.mark.parametrize(
        ("ocf", "capex", "revenue"),
        [(D("1"), D("-1"), D("100")), (D("1"), D("1"), D("-100"))],
    )
    def test_invalid_input(self, ocf: Decimal, capex: Decimal, revenue: Decimal) -> None:
        assert fcf_margin(ocf, capex, revenue).status is MetricStatus.INVALID_INPUT

    @pytest.mark.parametrize(
        "args",
        [(None, D("1"), D("1")), (D("1"), None, D("1")), (D("1"), D("1"), None)],
    )
    def test_missing_input(self, args: tuple[Decimal | None, ...]) -> None:
        assert fcf_margin(*args).status is MetricStatus.MISSING_INPUT
