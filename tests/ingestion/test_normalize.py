"""Tests for turning raw facts into annual statements. All data is fictional."""

from datetime import date
from decimal import Decimal

from factories import COMPANY, calendar_year, fact, year_end

from fsa.ingestion.companyfacts import RawFact
from fsa.ingestion.line_items import LineItem
from fsa.ingestion.models import AnnualPeriod, FinancialHistory
from fsa.ingestion.normalize import build_financial_history

D = Decimal


def build(*facts: RawFact) -> FinancialHistory:
    return build_financial_history(COMPANY, facts)


def only_period(history: FinancialHistory) -> AnnualPeriod:
    assert len(history.periods) == 1
    return history.periods[0]


class TestDuplicates:
    def test_same_value_in_several_filings_is_kept_once(self) -> None:
        history = build(
            calendar_year("Revenues", 2023, 100, filed="2024-02-01", accession="a1"),
            calendar_year("Revenues", 2023, 100, filed="2025-02-01", accession="a2"),
            calendar_year("Revenues", 2023, 100, filed="2026-02-01", accession="a3"),
        )
        line = only_period(history).values[LineItem.REVENUE]
        assert line.value == D("100")
        assert line.restated is False
        assert line.sources[0].accession_number == "a3"  # most recent filing

    def test_restated_value_uses_latest_filing(self) -> None:
        history = build(
            calendar_year("NetIncomeLoss", 2023, 100, filed="2024-02-01"),
            calendar_year("NetIncomeLoss", 2023, 96, filed="2025-02-01"),
        )
        line = only_period(history).values[LineItem.NET_INCOME]
        assert line.value == D("96")
        assert line.restated is True

    def test_amendment_overrides_original(self) -> None:
        history = build(
            calendar_year("Revenues", 2023, 100, filed="2024-02-01"),
            calendar_year("Revenues", 2023, 105, form="10-K/A", filed="2024-05-01"),
        )
        line = only_period(history).values[LineItem.REVENUE]
        assert line.value == D("105")
        assert line.sources[0].form == "10-K/A"

    def test_conflicting_values_in_one_filing_fall_back_to_next_tag(self) -> None:
        history = build(
            calendar_year("Revenues", 2023, 100, accession="x"),
            calendar_year("Revenues", 2023, 999, accession="x"),
            calendar_year("RevenueFromContractWithCustomerExcludingAssessedTax", 2023, 100),
        )
        line = only_period(history).values[LineItem.REVENUE]
        assert line.sources[0].tag == "RevenueFromContractWithCustomerExcludingAssessedTax"
        assert any("conflicting values" in w for w in history.warnings)

    def test_conflict_without_fallback_leaves_value_missing(self) -> None:
        history = build(
            calendar_year("Revenues", 2023, 100),
            calendar_year("NetIncomeLoss", 2023, 10, accession="x"),
            calendar_year("NetIncomeLoss", 2023, 20, accession="x"),
        )
        assert only_period(history).get(LineItem.NET_INCOME) is None
        assert any("NetIncomeLoss" in w for w in history.warnings)


class TestPeriodSelection:
    def test_quarterly_facts_are_ignored(self) -> None:
        history = build(
            calendar_year("Revenues", 2023, 400),
            fact("Revenues", 120, "2023-12-31", "2023-10-01"),  # Q4 disclosed in the 10-K
        )
        assert only_period(history).get(LineItem.REVENUE) == D("400")

    def test_10q_filings_are_ignored(self) -> None:
        history = build(
            calendar_year("Revenues", 2023, 400),
            year_end("Assets", 2023, 999, form="10-Q", filed="2024-05-01"),
        )
        assert only_period(history).get(LineItem.TOTAL_ASSETS) is None

    def test_no_periods_from_quarterly_only_data(self) -> None:
        history = build(fact("Revenues", 120, "2023-12-31", "2023-10-01"))
        assert history.periods == ()

    def test_transition_period_is_excluded(self) -> None:
        # A company changing its year-end files a report covering ~7 months.
        history = build(fact("Revenues", 70, "2023-12-31", "2023-06-01"))
        assert history.periods == ()

    def test_balance_sheet_uses_instant_on_period_end(self) -> None:
        history = build(
            calendar_year("Revenues", 2023, 400),
            year_end("Assets", 2023, 1000),
            fact("Assets", 900, "2023-06-30"),  # mid-year balance, not a period end
        )
        assert only_period(history).get(LineItem.TOTAL_ASSETS) == D("1000")

    def test_periods_are_sorted_oldest_first(self) -> None:
        history = build(
            calendar_year("Revenues", 2024, 2),
            calendar_year("Revenues", 2022, 1),
            calendar_year("Revenues", 2023, 1),
        )
        assert [p.end.year for p in history.periods] == [2022, 2023, 2024]


class TestFiscalYearEnds:
    def test_september_52_and_53_week_years(self) -> None:
        history = build(
            fact("Revenues", 383, "2023-09-30", "2022-09-25"),  # 53 weeks
            fact("Revenues", 391, "2024-09-28", "2023-10-01"),  # 52 weeks
        )
        assert [(p.start, p.end) for p in history.periods] == [
            (date(2022, 9, 25), date(2023, 9, 30)),
            (date(2023, 10, 1), date(2024, 9, 28)),
        ]

    def test_june_fiscal_year(self) -> None:
        history = build(fact("Revenues", 245, "2024-06-30", "2023-07-01"))
        assert only_period(history).end == date(2024, 6, 30)

    def test_january_fiscal_year(self) -> None:
        history = build(fact("Revenues", 648, "2024-01-31", "2023-02-01"))
        assert only_period(history).end == date(2024, 1, 31)

    def test_fiscal_year_label_comes_from_original_filing(self) -> None:
        # The FY2024 10-K (filed Mar 2024) reports both years; the FY2023 year
        # appears only as a comparison, so it gets no label.
        history = build(
            fact("Revenues", 600, "2023-01-31", "2022-02-01", fiscal_year=2024, filed="2024-03-15"),
            fact("Revenues", 648, "2024-01-31", "2023-02-01", fiscal_year=2024, filed="2024-03-15"),
        )
        older, newer = history.periods
        assert newer.fiscal_year == 2024
        assert newer.label == "FY2024 (ended 2024-01-31)"
        assert older.fiscal_year is None
        assert older.label == "Year ended 2023-01-31"

    def test_ambiguous_fiscal_year_labels_are_dropped(self) -> None:
        history = build(
            calendar_year("Revenues", 2023, 1, fiscal_year=2024, filed="2024-02-01", accession="a"),
            calendar_year("Revenues", 2024, 1, fiscal_year=2024, filed="2025-02-01", accession="b"),
        )
        assert all(p.fiscal_year is None for p in history.periods)
        assert any("ambiguous" in w for w in history.warnings)


class TestTagFallbacks:
    def test_tag_change_between_years(self) -> None:
        history = build(
            calendar_year("SalesRevenueNet", 2017, 100),
            calendar_year("RevenueFromContractWithCustomerExcludingAssessedTax", 2018, 110),
        )
        old, new = history.periods
        assert old.get(LineItem.REVENUE) == D("100")
        assert new.get(LineItem.REVENUE) == D("110")
        assert old.values[LineItem.REVENUE].sources[0].tag == "SalesRevenueNet"

    def test_higher_priority_tag_wins(self) -> None:
        history = build(
            calendar_year("RevenueFromContractWithCustomerExcludingAssessedTax", 2023, 90),
            calendar_year("Revenues", 2023, 100),  # total incl. non-contract revenue
        )
        assert only_period(history).get(LineItem.REVENUE) == D("100")


class TestMissingValues:
    def test_unreported_item_is_absent_not_zero(self) -> None:
        period = only_period(build(calendar_year("Revenues", 2023, 100)))
        assert LineItem.INVENTORY not in period.values
        assert period.get(LineItem.INVENTORY) is None

    def test_non_usd_values_are_excluded_with_warning(self) -> None:
        history = build(
            calendar_year("Revenues", 2023, 100),
            calendar_year("NetIncomeLoss", 2023, 10, unit="EUR"),
        )
        assert only_period(history).get(LineItem.NET_INCOME) is None
        assert any("EUR" in w for w in history.warnings)

    def test_parser_warnings_are_carried_through(self) -> None:
        history = build_financial_history(
            COMPANY, [calendar_year("Revenues", 2023, 1)], warnings=["parser note"]
        )
        assert "parser note" in history.warnings


class TestDerivedGrossProfit:
    def test_derived_when_not_reported(self) -> None:
        period = only_period(
            build(calendar_year("Revenues", 2023, 1000), calendar_year("CostOfRevenue", 2023, 600))
        )
        line = period.values[LineItem.GROSS_PROFIT]
        assert line.value == D("400")
        assert line.is_derived
        assert line.derivation == "Revenue − Cost of revenue"
        assert {s.tag for s in line.sources} == {"Revenues", "CostOfRevenue"}

    def test_reported_value_is_preferred(self) -> None:
        period = only_period(
            build(
                calendar_year("Revenues", 2023, 1000),
                calendar_year("CostOfRevenue", 2023, 600),
                calendar_year("GrossProfit", 2023, 401),
            )
        )
        assert period.get(LineItem.GROSS_PROFIT) == D("401")
        assert not period.values[LineItem.GROSS_PROFIT].is_derived

    def test_not_derived_without_cost_of_revenue(self) -> None:
        period = only_period(build(calendar_year("Revenues", 2023, 1000)))
        assert period.get(LineItem.GROSS_PROFIT) is None


class TestDerivedTotalDebt:
    def _period(self, *debt_facts: RawFact) -> AnnualPeriod:
        return only_period(build(calendar_year("Revenues", 2023, 1), *debt_facts))

    def test_uses_debt_current_when_reported(self) -> None:
        period = self._period(
            year_end("LongTermDebtNoncurrent", 2023, 800),
            year_end("DebtCurrent", 2023, 150),
            year_end("LongTermDebtCurrent", 2023, 100),  # already inside DebtCurrent
        )
        line = period.values[LineItem.TOTAL_DEBT]
        assert line.value == D("950")
        assert line.derivation == "Long-term debt (non-current) + Total current debt"

    def test_sums_current_pieces_and_names_missing_ones(self) -> None:
        period = self._period(
            year_end("LongTermDebtNoncurrent", 2023, 800),
            year_end("LongTermDebtCurrent", 2023, 100),
            year_end("CommercialPaper", 2023, 50),
        )
        line = period.values[LineItem.TOTAL_DEBT]
        assert line.value == D("950")
        assert line.derivation is not None
        assert "not included: Short-term borrowings" in line.derivation
        assert len(line.sources) == 3

    def test_missing_without_noncurrent_debt(self) -> None:
        period = self._period(year_end("DebtCurrent", 2023, 150))
        assert period.get(LineItem.TOTAL_DEBT) is None

    def test_missing_without_any_current_debt_figure(self) -> None:
        period = self._period(year_end("LongTermDebtNoncurrent", 2023, 800))
        assert period.get(LineItem.TOTAL_DEBT) is None


class TestPriorPeriod:
    def test_finds_adjacent_year(self) -> None:
        history = build(calendar_year("Revenues", 2022, 1), calendar_year("Revenues", 2023, 1))
        older, newer = history.periods
        assert history.prior_to(newer) is older
        assert history.prior_to(older) is None

    def test_gap_year_is_not_treated_as_prior(self) -> None:
        history = build(calendar_year("Revenues", 2021, 1), calendar_year("Revenues", 2023, 1))
        assert history.prior_to(history.periods[1]) is None

    def test_latest(self) -> None:
        history = build(calendar_year("Revenues", 2022, 1), calendar_year("Revenues", 2023, 1))
        assert history.latest is history.periods[-1]
        assert build().latest is None
