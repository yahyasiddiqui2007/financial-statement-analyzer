"""End-to-end ingestion tests: mock SEC responses → normalized history → metrics."""

from datetime import date
from decimal import Decimal
from typing import Any

import httpx
import pytest
from factories import load_fixture

from fsa.analysis import annual_metrics
from fsa.analytics import MetricStatus
from fsa.ingestion import (
    CompanyDataNotFoundError,
    DataFormatError,
    FinancialHistory,
    LineItem,
    SecClient,
    TickerNotFoundError,
    load_financial_history,
)
from fsa.ingestion.rate_limiter import RateLimiter

D = Decimal


def mock_client(companyfacts: Any) -> SecClient:
    """A client whose 'SEC' serves the ticker fixture and the given companyfacts."""

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/files/company_tickers.json":
            return httpx.Response(200, json=load_fixture("company_tickers_example.json"))
        if request.url.path == "/api/xbrl/companyfacts/CIK0001234567.json":
            return httpx.Response(200, json=companyfacts)
        return httpx.Response(404)

    return SecClient(
        "Test test@example.com",
        http_client=httpx.Client(transport=httpx.MockTransport(handle)),
        rate_limiter=RateLimiter(1000, sleep=lambda s: None),
    )


def example_facts() -> Any:
    # Re-serialize with plain numbers, as httpx's json= argument expects.
    raw = load_fixture("companyfacts_example.json")
    return _decimals_to_numbers(raw)


def _decimals_to_numbers(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _decimals_to_numbers(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_decimals_to_numbers(v) for v in value]
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else str(value)
    return value


@pytest.fixture
def history() -> FinancialHistory:
    with mock_client(example_facts()) as client:
        return load_financial_history("exmp", client)


class TestLoadFinancialHistory:
    def test_company_identity(self, history: FinancialHistory) -> None:
        assert history.company.ticker == "EXMP"
        assert history.company.cik == "0001234567"

    def test_three_june_fiscal_years(self, history: FinancialHistory) -> None:
        assert [p.end for p in history.periods] == [
            date(2023, 6, 30),
            date(2024, 6, 30),
            date(2025, 6, 30),
        ]
        assert [p.fiscal_year for p in history.periods] == [None, 2024, 2025]

    def test_statement_values(self, history: FinancialHistory) -> None:
        fy2025 = history.periods[-1]
        assert fy2025.get(LineItem.REVENUE) == D("1200000000")
        assert fy2025.get(LineItem.TOTAL_ASSETS) == D("2600000000")
        assert fy2025.get(LineItem.CAPITAL_EXPENDITURES) == D("60000000")

    def test_restatement_is_flagged(self, history: FinancialHistory) -> None:
        fy2024 = history.periods[1].values[LineItem.NET_INCOME]
        assert fy2024.value == D("96000000")
        assert fy2024.restated

    def test_quarterly_numbers_did_not_leak_in(self, history: FinancialHistory) -> None:
        assert history.periods[-1].get(LineItem.REVENUE) == D("1200000000")
        assert len(history.periods) == 3

    def test_malformed_fact_warning_reaches_history(self, history: FinancialHistory) -> None:
        assert "Skipped 1 malformed fact(s) in the SEC data." in history.warnings

    def test_source_links_to_sec_filing(self, history: FinancialHistory) -> None:
        source = history.periods[-1].values[LineItem.REVENUE].sources[0]
        assert source.filing_url(history.company.cik) == (
            "https://www.sec.gov/Archives/edgar/data/1234567/000123456725000012/"
        )

    def test_unknown_ticker(self) -> None:
        with mock_client(example_facts()) as client, pytest.raises(TickerNotFoundError):
            load_financial_history("NOPE", client)

    def test_company_without_us_gaap_data(self) -> None:
        ifrs = {"cik": 1234567, "entityName": "Example", "facts": {"ifrs-full": {}}}
        with mock_client(ifrs) as client, pytest.raises(CompanyDataNotFoundError, match="IFRS"):
            load_financial_history("EXMP", client)

    def test_response_for_wrong_company_is_rejected(self) -> None:
        wrong = {**example_facts(), "cik": 999}
        with mock_client(wrong) as client, pytest.raises(DataFormatError):
            load_financial_history("EXMP", client)


class TestMetricsFromHistory:
    """The calculation engine running on normalized data, checked by hand."""

    def test_latest_year(self, history: FinancialHistory) -> None:
        m = annual_metrics(history, history.periods[-1])
        assert m["revenue_growth"].value == D("0.2")  # (1200 − 1000) / 1000
        assert m["gross_margin"].value == D("0.425")  # (1200 − 690) / 1200, derived
        assert m["operating_margin"].value == D("0.175")  # 210 / 1200
        assert m["current_ratio"].value == D("1.6")  # 800 / 500
        assert m["free_cash_flow"].value == D("180000000")  # 240 − 60
        assert m["fcf_margin"].value == D("0.15")  # 180 / 1200
        roa = m["return_on_assets"].value  # 130 / ((2200 + 2600) / 2)
        assert roa is not None and round(roa, 6) == D("0.054167")
        roe = m["return_on_equity"].value  # 130 / ((1100 + 1300) / 2)
        assert roe is not None and round(roe, 6) == D("0.108333")

    def test_restated_value_feeds_metrics(self, history: FinancialHistory) -> None:
        m = annual_metrics(history, history.periods[1])
        assert m["return_on_assets"].value == D("0.048")  # 96 / ((1800 + 2200) / 2)

    def test_unreported_inputs_give_missing_not_zero(self, history: FinancialHistory) -> None:
        m = annual_metrics(history, history.periods[-1])
        # The fixture has no cash or debt tags.
        assert m["quick_ratio"].status is MetricStatus.MISSING_INPUT
        assert m["debt_to_equity"].status is MetricStatus.MISSING_INPUT

    def test_first_year_has_no_prior_year(self, history: FinancialHistory) -> None:
        m = annual_metrics(history, history.periods[0])
        assert m["revenue_growth"].status is MetricStatus.MISSING_INPUT
        assert m["return_on_assets"].status is MetricStatus.MISSING_INPUT
        assert m["gross_margin"].status is MetricStatus.OK

    def test_every_metric_is_present(self, history: FinancialHistory) -> None:
        assert len(annual_metrics(history, history.periods[-1])) == 11
