"""Trend analysis tests on small fictional histories (all numbers made up)."""

import re
from datetime import date
from decimal import Decimal

import pytest

from fsa.ingestion import AnnualPeriod, Company, FinancialHistory, LineItem, LineItemValue
from fsa.trends import Direction, TrendFinding, TrendReport, analyze_trends, trend_window

D = Decimal
M = 1_000_000  # values below are written in millions for readability
L = LineItem

Values = list[int | str | None]  # str for exact decimals like "133.1"

BASE: dict[LineItem, Values] = {
    L.REVENUE: [100, 110, 121, 133, 146],
    L.GROSS_PROFIT: [40, 45, 50, 56, 62],
    L.OPERATING_INCOME: [20, 22, 25, 28, 31],
    L.NET_INCOME: [10, 11, 12, 14, 15],
    L.OPERATING_CASH_FLOW: [18, 19, 21, 23, 26],
    L.CAPITAL_EXPENDITURES: [5, 5, 6, 6, 7],
    L.TOTAL_ASSETS: [200, 205, 210, 215, 220],
    L.CURRENT_ASSETS: [80, 82, 85, 88, 90],
    L.CURRENT_LIABILITIES: [50, 52, 55, 70, 80],
    L.CASH_AND_EQUIVALENTS: [30, 31, 30, 32, 31],
    L.TOTAL_DEBT: [60, 55, 50, 45, 40],
    L.TOTAL_EQUITY: [100, 105, 110, 115, 120],
}


def make_history(
    overrides: dict[LineItem, Values] | None = None,
    years: list[int] | None = None,
) -> FinancialHistory:
    """Calendar fiscal years 2021–2025 (by default) with the BASE values."""
    data = {**BASE, **(overrides or {})}
    years = years or [2021, 2022, 2023, 2024, 2025]
    periods = []
    for i, year in enumerate(years):
        values = {
            item: LineItemValue(item=item, value=D(raw) * M, sources=())
            for item, series in data.items()
            if (raw := series[i]) is not None
        }
        periods.append(
            AnnualPeriod(
                start=date(year, 1, 1), end=date(year, 12, 31), fiscal_year=year, values=values
            )
        )
    return FinancialHistory(
        company=Company(cik="0000000001", ticker="TEST", name="Test Co"), periods=tuple(periods)
    )


def finding(report: TrendReport, topic: str) -> TrendFinding:
    return next(f for f in report.findings if f.topic == topic)


def stat(f: TrendFinding, label_start: str) -> Decimal | None:
    return next(s.result.value for s in f.statistics if s.label.startswith(label_start))


class TestWindow:
    def test_uses_latest_five_years(self) -> None:
        history = make_history(
            {k: [v[0], *v] for k, v in BASE.items()}, years=[2020, 2021, 2022, 2023, 2024, 2025]
        )
        assert [p.end.year for p in trend_window(history, 5)] == [2021, 2022, 2023, 2024, 2025]

    def test_three_year_window(self) -> None:
        report = analyze_trends(make_history(), 3)
        assert (report.start_label, report.end_label, report.years) == ("FY2023", "FY2025", 3)

    def test_stops_at_a_gap(self) -> None:
        history = make_history(years=[2019, 2020, 2023, 2024, 2025])  # 2021–2022 missing
        report = analyze_trends(history, 5)
        assert report.years == 3
        assert "Only 3 consecutive fiscal years" in report.notes[0]

    def test_too_few_years(self) -> None:
        history = make_history({k: v[:2] for k, v in BASE.items()}, years=[2024, 2025])
        report = analyze_trends(history, 5)
        assert report.findings == ()
        assert "at least 3 consecutive fiscal years" in report.notes[0]

    @pytest.mark.parametrize("years", [2, 6])
    def test_rejects_out_of_range_years(self, years: int) -> None:
        with pytest.raises(ValueError):
            analyze_trends(make_history(), years)


class TestRevenue:
    def test_growing_revenue(self) -> None:
        f = finding(analyze_trends(make_history()), "revenue_growth")
        assert f.direction is Direction.INCREASING
        # (146 / 100)^(1/4) − 1 = 9.92%
        cagr = stat(f, "CAGR")
        assert cagr is not None and round(cagr, 4) == D("0.0992")
        assert f.summary == (
            "Revenue grew from $100M in FY2021 to $146M in FY2025, "
            "a compound annual growth rate of 9.9% over 4 years."
        )
        assert stat(f, "Total change") == D(46) * M
        assert "Revenue increased in 4 of 4 year-over-year comparisons." in f.details

    def test_flat_revenue_is_stable(self) -> None:
        f = finding(
            analyze_trends(make_history({L.REVENUE: [100, 101, 99, 100, 102]})), "revenue_growth"
        )
        assert f.direction is Direction.STABLE  # CAGR 0.5% is within ±1%
        assert "roughly flat" in f.summary

    def test_declining_revenue(self) -> None:
        f = finding(
            analyze_trends(make_history({L.REVENUE: [100, 95, 90, 85, 80]})), "revenue_growth"
        )
        assert f.direction is Direction.DECREASING
        assert "declined" in f.summary

    def test_consistency_and_range(self) -> None:
        f = finding(
            analyze_trends(make_history({L.REVENUE: [100, 110, 105, 120, 130]})), "revenue_growth"
        )
        assert (
            "Revenue increased in 3 of 4 year-over-year comparisons and decreased in 1."
            in f.details
        )
        assert "Year-over-year changes ranged from −4.5% (FY2023) to +14.3% (FY2024)." in f.details

    def test_latest_growth_vs_compound_rate(self) -> None:
        f = finding(
            analyze_trends(make_history({L.REVENUE: [100, 100, 100, 100, 120]})), "revenue_growth"
        )
        assert "Growth in FY2025 (+20.0%) was above the 4-year compound rate (4.7%)." in f.details

    def test_equal_after_rounding_is_not_called_above_or_below(self) -> None:
        # Both rates display as 10.0%; the sentence must not say "above" or "below".
        f = finding(
            analyze_trends(make_history({L.REVENUE: [100, 110, 121, "133.1", "146.41"]})),
            "revenue_growth",
        )
        assert any("about the same as" in d for d in f.details)

    def test_missing_end_year(self) -> None:
        f = finding(
            analyze_trends(make_history({L.REVENUE: [100, 110, 121, 133, None]})), "revenue_growth"
        )
        assert f.direction is Direction.INSUFFICIENT_DATA
        assert "FY2025" in f.summary


class TestNetIncomeAndFcf:
    def test_loss_to_profit_uses_sign_not_cagr(self) -> None:
        f = finding(
            analyze_trends(make_history({L.NET_INCOME: [-10, -5, 0, 5, 12]})), "net_income_growth"
        )
        assert f.direction is Direction.INCREASING
        assert "not meaningful" in f.summary
        assert "−$10.0M in FY2021 to $12.0M in FY2025 (+$22.0M)" in f.summary
        assert stat(f, "CAGR") is None

    def test_free_cash_flow_comes_from_the_metric_engine(self) -> None:
        f = finding(analyze_trends(make_history()), "fcf_growth")
        values = [p.value for p in f.series[0].points]
        assert values == [D(v) * M for v in (13, 14, 15, 17, 19)]  # OCF − capex each year
        assert f.direction is Direction.INCREASING


class TestMargins:
    def test_all_margins_expanding(self) -> None:
        history = make_history(
            {
                L.GROSS_PROFIT: [40, 41, 42, 44, 45],
                L.OPERATING_INCOME: [10, 12, 14, 15, 17],
                L.NET_INCOME: [5, 6, 8, 9, 10],
                L.REVENUE: [100] * 5,
            }
        )
        f = finding(analyze_trends(history), "margins")
        assert f.direction is Direction.INCREASING
        assert f.summary == "All three margins expanded between FY2021 and FY2025."
        assert "Gross margin expanded, from 40.0% to 45.0% (+5.0 pp)." in f.details

    def test_mixed(self) -> None:
        history = make_history(
            {
                L.GROSS_PROFIT: [40, 41, 42, 44, 45],
                L.OPERATING_INCOME: [20, 19, 18, 17, 15],
                L.NET_INCOME: [10, 10, 10, 10, 10],
                L.REVENUE: [100] * 5,
            }
        )
        f = finding(analyze_trends(history), "margins")
        assert f.direction is Direction.MIXED
        assert "Net margin was stable, from 10.0% to 10.0% (0.0 pp)." in f.details

    def test_only_one_margin_available(self) -> None:
        history = make_history({L.GROSS_PROFIT: [None] * 5, L.OPERATING_INCOME: [None] * 5})
        f = finding(analyze_trends(history), "margins")
        assert f.summary.startswith("The only available margin, net margin,")
        assert (
            "Gross margin is not available: an input is not reported in the filings." in f.details
        )

    def test_no_margins(self) -> None:
        history = make_history({L.REVENUE: [None] * 5})
        assert finding(analyze_trends(history), "margins").direction is Direction.INSUFFICIENT_DATA


class TestDebtAndCash:
    def test_debt_decrease_with_leverage(self) -> None:
        f = finding(analyze_trends(make_history()), "debt_changes")
        assert f.direction is Direction.DECREASING
        assert f.summary == (
            "Total debt decreased from $60.0M at the end of FY2021 to $40.0M at the end of "
            "FY2025 (−$20.0M, −33.3%)."
        )
        assert "Debt-to-equity went from 0.60x to 0.33x." in f.details

    def test_negative_equity_explained(self) -> None:
        f = finding(
            analyze_trends(make_history({L.TOTAL_EQUITY: [-10, -10, -10, -10, -10]})),
            "debt_changes",
        )
        assert any("equity is negative" in d for d in f.details)

    def test_missing_debt(self) -> None:
        f = finding(analyze_trends(make_history({L.TOTAL_DEBT: [None] * 5})), "debt_changes")
        assert f.direction is Direction.INSUFFICIENT_DATA

    def test_cash_within_five_percent_is_stable(self) -> None:
        f = finding(analyze_trends(make_history()), "cash_changes")
        assert f.direction is Direction.STABLE  # 30 → 31 is +3.3%
        assert f.summary.startswith("Cash and cash equivalents were roughly unchanged")

    def test_cash_from_zero_uses_sign(self) -> None:
        f = finding(
            analyze_trends(make_history({L.CASH_AND_EQUIVALENTS: [0, 1, 2, 3, 4]})), "cash_changes"
        )
        assert f.direction is Direction.INCREASING
        assert stat(f, "Change (%)") is None


class TestAssetsAndWorkingCapital:
    def test_assets_compared_with_revenue(self) -> None:
        f = finding(analyze_trends(make_history()), "asset_growth")
        assert f.direction is Direction.INCREASING  # 200 → 220 is 2.4% a year
        assert (
            "Over the same years, total assets grew at 2.4% a year and revenue at 9.9% a year."
            in f.details
        )

    def test_working_capital_is_calculated_each_year(self) -> None:
        f = finding(analyze_trends(make_history()), "working_capital")
        values = [p.value for p in f.series[0].points]
        assert values == [
            D(v) * M for v in (30, 30, 30, 18, 10)
        ]  # current assets − current liabilities
        assert f.direction is Direction.DECREASING
        assert stat(f, "Change") == D(-20) * M

    def test_small_change_relative_to_revenue_is_stable(self) -> None:
        # Change of 1 (million) vs ending revenue 146: under the 1% band.
        history = make_history(
            {L.CURRENT_ASSETS: [80] * 5, L.CURRENT_LIABILITIES: [50, 50, 50, 50, 49]}
        )
        f = finding(analyze_trends(history), "working_capital")
        assert f.direction is Direction.STABLE

    def test_negative_working_capital_noted(self) -> None:
        history = make_history({L.CURRENT_LIABILITIES: [100] * 5})
        f = finding(analyze_trends(history), "working_capital")
        assert any("negative in 5 of 5 years" in d for d in f.details)

    def test_bank_without_current_items(self) -> None:
        history = make_history({L.CURRENT_ASSETS: [None] * 5, L.CURRENT_LIABILITIES: [None] * 5})
        f = finding(analyze_trends(history), "working_capital")
        assert f.direction is Direction.INSUFFICIENT_DATA
        assert "Banks" in f.summary


class TestEvidenceAndLanguage:
    def test_all_eight_topics(self) -> None:
        topics = [f.topic for f in analyze_trends(make_history()).findings]
        assert topics == [
            "revenue_growth",
            "margins",
            "net_income_growth",
            "fcf_growth",
            "debt_changes",
            "cash_changes",
            "asset_growth",
            "working_capital",
        ]

    def test_every_statistic_has_a_formula(self) -> None:
        for f in analyze_trends(make_history()).findings:
            assert f.method
            for s in f.statistics:
                assert s.result.formula

    def test_series_cover_every_year_in_the_window(self) -> None:
        for f in analyze_trends(make_history(), 4).findings:
            for series in f.series:
                assert [p.label for p in series.points] == ["FY2022", "FY2023", "FY2024", "FY2025"]

    @pytest.mark.parametrize(
        "overrides",
        [
            {},
            {L.NET_INCOME: [-10, -5, 0, 5, 12]},
            {L.REVENUE: [100, 90, 80, 70, 60]},
            {L.TOTAL_EQUITY: [-10] * 5, L.TOTAL_DEBT: [None] * 5},
        ],
    )
    def test_no_investment_language(self, overrides: dict[LineItem, Values]) -> None:
        forbidden = re.compile(
            # "Short-term investments" is a balance-sheet line, so only advice-style
            # uses of "invest" are flagged.
            r"\b(buy|sell|hold|investors?|invest in|investment (?:case|thesis)|"
            r"recommend\w*|should|undervalued|overvalued|attractive|bullish|bearish|"
            r"outperform\w*|price target|opportunity)\b",
            re.IGNORECASE,
        )
        report = analyze_trends(make_history(overrides))
        texts = [*report.notes]
        for f in report.findings:
            texts += [f.summary, *f.details, f.method]
        for t in texts:
            assert not forbidden.search(t), t
