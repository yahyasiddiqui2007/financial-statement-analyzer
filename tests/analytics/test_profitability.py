from collections.abc import Callable
from decimal import Decimal

import pytest

from fsa.analytics import (
    MetricResult,
    MetricStatus,
    gross_margin,
    net_margin,
    operating_margin,
    return_on_assets,
    return_on_equity,
)

D = Decimal

MarginFn = Callable[[Decimal | None, Decimal | None], MetricResult]
ALL_MARGINS = [gross_margin, operating_margin, net_margin]


class TestMargins:
    def test_gross_margin(self) -> None:
        assert gross_margin(D("400"), D("1000")).value == D("0.4")

    def test_operating_margin(self) -> None:
        assert operating_margin(D("150"), D("1000")).value == D("0.15")

    def test_net_margin(self) -> None:
        assert net_margin(D("80"), D("1000")).value == D("0.08")

    @pytest.mark.parametrize("margin", ALL_MARGINS)
    def test_loss_gives_negative_margin(self, margin: MarginFn) -> None:
        result = margin(D("-50"), D("1000"))
        assert result.status is MetricStatus.OK
        assert result.value == D("-0.05")

    @pytest.mark.parametrize("margin", ALL_MARGINS)
    def test_zero_profit_gives_zero_margin(self, margin: MarginFn) -> None:
        assert margin(D("0"), D("1000")).value == D("0")

    @pytest.mark.parametrize("margin", ALL_MARGINS)
    def test_zero_revenue_is_zero_denominator(self, margin: MarginFn) -> None:
        result = margin(D("10"), D("0"))
        assert result.status is MetricStatus.ZERO_DENOMINATOR
        assert result.value is None

    @pytest.mark.parametrize("margin", ALL_MARGINS)
    def test_negative_revenue_is_invalid(self, margin: MarginFn) -> None:
        assert margin(D("10"), D("-100")).status is MetricStatus.INVALID_INPUT

    @pytest.mark.parametrize("margin", ALL_MARGINS)
    @pytest.mark.parametrize(("profit", "revenue"), [(None, D("100")), (D("10"), None)])
    def test_missing_input(
        self, margin: MarginFn, profit: Decimal | None, revenue: Decimal | None
    ) -> None:
        assert margin(profit, revenue).status is MetricStatus.MISSING_INPUT

    def test_metric_names(self) -> None:
        assert gross_margin(D("1"), D("2")).name == "gross_margin"
        assert operating_margin(D("1"), D("2")).name == "operating_margin"
        assert net_margin(D("1"), D("2")).name == "net_margin"

    def test_repeating_decimal(self) -> None:
        # 1/3 can't be written exactly; we keep 28 significant digits.
        result = net_margin(D("1"), D("3"))
        assert result.value is not None
        assert round(result.value, 10) == D("0.3333333333")


class TestReturnOnAssets:
    def test_uses_average_assets(self) -> None:
        # Average assets = (900 + 1100) / 2 = 1000; 50 / 1000 = 0.05
        assert return_on_assets(D("50"), D("900"), D("1100")).value == D("0.05")

    def test_differs_from_ending_balance_ratio(self) -> None:
        # Guards against accidentally using only ending assets (50/1100).
        assert return_on_assets(D("50"), D("900"), D("1100")).value != D("50") / D("1100")

    def test_net_loss_gives_negative_roa(self) -> None:
        assert return_on_assets(D("-20"), D("1000"), D("1000")).value == D("-0.02")

    def test_zero_average_assets_is_zero_denominator(self) -> None:
        result = return_on_assets(D("10"), D("0"), D("0"))
        assert result.status is MetricStatus.ZERO_DENOMINATOR

    def test_one_zero_balance_still_works(self) -> None:
        # A newly formed company may start the year with zero assets.
        assert return_on_assets(D("10"), D("0"), D("200")).value == D("0.1")

    @pytest.mark.parametrize(("begin", "end"), [(D("-1"), D("100")), (D("100"), D("-1"))])
    def test_negative_assets_is_invalid(self, begin: Decimal, end: Decimal) -> None:
        assert return_on_assets(D("10"), begin, end).status is MetricStatus.INVALID_INPUT

    @pytest.mark.parametrize(
        "args",
        [(None, D("1"), D("1")), (D("1"), None, D("1")), (D("1"), D("1"), None)],
    )
    def test_missing_input(self, args: tuple[Decimal | None, ...]) -> None:
        # No fallback to ending assets when beginning assets are missing.
        assert return_on_assets(*args).status is MetricStatus.MISSING_INPUT


class TestReturnOnEquity:
    def test_uses_average_equity(self) -> None:
        # Average equity = (180 + 220) / 2 = 200; 30 / 200 = 0.15
        assert return_on_equity(D("30"), D("180"), D("220")).value == D("0.15")

    def test_net_loss_gives_negative_roe(self) -> None:
        assert return_on_equity(D("-10"), D("100"), D("100")).value == D("-0.1")

    @pytest.mark.parametrize(
        ("begin", "end"),
        [(D("-100"), D("-50")), (D("-100"), D("50")), (D("100"), D("-50"))],
    )
    def test_negative_equity_is_not_meaningful(self, begin: Decimal, end: Decimal) -> None:
        result = return_on_equity(D("30"), begin, end)
        assert result.status is MetricStatus.NOT_MEANINGFUL
        assert result.value is None

    def test_negative_equity_with_profit_is_not_shown_as_negative_roe(self) -> None:
        # The trap this rule prevents: +30 / -200 would show "-15%" for a profitable company.
        assert return_on_equity(D("30"), D("-200"), D("-200")).value is None

    def test_zero_average_equity_is_zero_denominator(self) -> None:
        result = return_on_equity(D("30"), D("0"), D("0"))
        assert result.status is MetricStatus.ZERO_DENOMINATOR

    @pytest.mark.parametrize(
        "args",
        [(None, D("1"), D("1")), (D("1"), None, D("1")), (D("1"), D("1"), None)],
    )
    def test_missing_input(self, args: tuple[Decimal | None, ...]) -> None:
        assert return_on_equity(*args).status is MetricStatus.MISSING_INPUT
