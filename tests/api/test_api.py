"""API tests. A fake loader serves the fictional fixture company, so no network is used."""

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from fsa.api.app import ServerMisconfiguredError, create_app
from fsa.ingestion import (
    CompanyDataNotFoundError,
    DataFormatError,
    FinancialHistory,
    IngestionError,
    SecAccessDeniedError,
    SecApiError,
    TickerNotFoundError,
)
from fsa.ingestion.companyfacts import parse_company_facts
from fsa.ingestion.line_items import ALL_TAGS
from fsa.ingestion.models import Company
from fsa.ingestion.normalize import build_financial_history

FIXTURE = Path(__file__).parents[1] / "ingestion" / "fixtures" / "companyfacts_example.json"


def example_history() -> FinancialHistory:
    payload = json.loads(FIXTURE.read_text(), parse_float=Decimal)
    parsed = parse_company_facts(payload, tags=ALL_TAGS)
    company = Company(cik="0001234567", ticker="EXMP", name="Example Manufacturing Corp")
    return build_financial_history(company, parsed.facts, warnings=parsed.warnings)


class FakeLoader:
    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[str] = []
        self.error = error

    def __call__(self, ticker: str) -> FinancialHistory:
        self.calls.append(ticker)
        if self.error:
            raise self.error
        return example_history()


def client_for(loader: FakeLoader) -> TestClient:
    return TestClient(create_app(loader, frontend_dist=None))


@pytest.fixture
def body() -> Any:
    response = client_for(FakeLoader()).get("/api/companies/exmp/financials")
    assert response.status_code == 200
    return response.json()


def row(body: Any, statement: str, item: str) -> Any:
    stmt = next(s for s in body["statements"] if s["id"] == statement)
    return next(r for r in stmt["rows"] if r["item"] == item)


def metric(body: Any, name: str) -> Any:
    return next(m for m in body["metrics"] if m["name"] == name)


class TestFinancialsEndpoint:
    def test_health(self) -> None:
        assert client_for(FakeLoader()).get("/api/health").json() == {"status": "ok"}

    def test_company_and_source(self, body: Any) -> None:
        assert body["company"]["ticker"] == "EXMP"
        assert body["company"]["cik"] == "0001234567"
        assert "CIK0001234567" in body["source"]["url"]
        assert body["source"]["retrieved_at"]

    def test_periods_oldest_first(self, body: Any) -> None:
        assert [p["end"] for p in body["periods"]] == ["2023-06-30", "2024-06-30", "2025-06-30"]
        assert [p["has_prior"] for p in body["periods"]] == [False, True, True]

    def test_values_are_exact_strings(self, body: Any) -> None:
        revenue = row(body, "income_statement", "revenue")
        assert [c["value"] for c in revenue["cells"]] == ["800000000", "1000000000", "1200000000"]

    def test_unreported_value_is_null(self, body: Any) -> None:
        cell = row(body, "balance_sheet", "inventory")["cells"][-1]
        assert cell["value"] is None
        assert cell["sources"] == []

    def test_year_over_year_change(self, body: Any) -> None:
        cells = row(body, "income_statement", "revenue")["cells"]
        assert cells[0]["change"] is None  # no prior year in the data
        assert cells[2]["change"] == {"value": "0.2", "status": "ok", "reason": None}

    def test_derived_and_restated_flags(self, body: Any) -> None:
        gross = row(body, "income_statement", "gross_profit")["cells"][-1]
        assert gross["derived"] is True
        assert gross["derivation"] == "Revenue − Cost of revenue"
        net_income_fy2024 = row(body, "income_statement", "net_income")["cells"][1]
        assert net_income_fy2024["restated"] is True

    def test_sources_link_to_filings(self, body: Any) -> None:
        source = row(body, "income_statement", "revenue")["cells"][-1]["sources"][0]
        assert source["tag"] == "Revenues"
        assert source["url"].startswith("https://www.sec.gov/Archives/edgar/data/1234567/")

    def test_metrics(self, body: Any) -> None:
        gross_margin = metric(body, "gross_margin")
        assert gross_margin["format"] == "percent"
        assert gross_margin["formula"] == "Gross profit / Revenue"
        latest = gross_margin["values"][-1]
        assert latest["value"] == "0.425"
        assert latest["difference"] == "0.025"  # 42.5% − 40.0% = +2.5 points
        assert latest["inputs"] == {"gross_profit": "510000000", "revenue": "1200000000"}

    def test_metric_failure_has_reason(self, body: Any) -> None:
        quick = metric(body, "quick_ratio")["values"][-1]
        assert quick["value"] is None
        assert quick["status"] == "missing_input"
        assert "cash_and_equivalents" in quick["reason"]
        assert quick["difference"] is None

    def test_every_metric_is_listed(self, body: Any) -> None:
        assert len(body["metrics"]) == 11
        assert all(len(m["values"]) == 3 for m in body["metrics"])

    def test_warnings(self, body: Any) -> None:
        assert "Skipped 1 malformed fact(s) in the SEC data." in body["warnings"]


class TestCaching:
    def test_repeat_requests_use_cache(self) -> None:
        loader = FakeLoader()
        client = client_for(loader)
        client.get("/api/companies/EXMP/financials")
        client.get("/api/companies/exmp/financials")
        assert loader.calls == ["EXMP"]

    def test_failures_are_not_cached(self) -> None:
        loader = FakeLoader(error=SecApiError("down", 503))
        client = client_for(loader)
        client.get("/api/companies/EXMP/financials")
        client.get("/api/companies/EXMP/financials")
        assert len(loader.calls) == 2


class TestErrors:
    @pytest.mark.parametrize(
        ("error", "status", "code"),
        [
            (TickerNotFoundError("nope"), 404, "ticker_not_found"),
            (CompanyDataNotFoundError("none"), 404, "no_financial_data"),
            (SecAccessDeniedError("denied"), 502, "sec_access_denied"),
            (DataFormatError("bad"), 502, "sec_bad_data"),
            (SecApiError("down", 503), 502, "sec_unavailable"),
            (ServerMisconfiguredError("set env"), 500, "server_misconfigured"),
        ],
    )
    def test_error_mapping(self, error: Exception, status: int, code: str) -> None:
        response = client_for(FakeLoader(error=error)).get("/api/companies/EXMP/financials")
        assert response.status_code == status
        assert response.json() == {"error": {"code": code, "message": str(error)}}

    def test_invalid_ticker_never_reaches_loader(self) -> None:
        loader = FakeLoader()
        response = client_for(loader).get("/api/companies/$$$/financials")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "ticker_not_found"
        assert loader.calls == []

    def test_all_ingestion_errors_are_mapped(self) -> None:
        from fsa.api.app import ERROR_RESPONSES

        mapped = {e for e, _, _ in ERROR_RESPONSES}
        subclasses = set(IngestionError.__subclasses__())
        assert subclasses <= mapped


class TestTrends:
    def test_trend_report_included(self, body: Any) -> None:
        # The fixture company has 3 fiscal years, so the 5-year window collapses into
        # the 3-year one and only one report is sent.
        assert [r["years"] for r in body["trends"]] == [3]
        report = body["trends"][0]
        assert (report["start_label"], report["end_label"]) == (
            "the year ended 2023-06-30",
            "FY2025",
        )
        assert len(report["findings"]) == 8

    def test_finding_evidence_is_exact(self, body: Any) -> None:
        revenue = body["trends"][0]["findings"][0]
        assert revenue["topic"] == "revenue_growth"
        assert revenue["direction"] == "increasing"
        cagr = revenue["statistics"][0]
        assert cagr["formula"] == "(Ending value / Beginning value)^(1 / Years) − 1"
        assert cagr["inputs"] == {
            "beginning_value": "800000000",
            "ending_value": "1200000000",
            "years": "2",
        }
        assert [p["value"] for p in revenue["series"][0]["points"]] == [
            "800000000",
            "1000000000",
            "1200000000",
        ]


class TestFrontendServing:
    def test_index_html_is_never_stale(self, tmp_path: Path) -> None:
        (tmp_path / "index.html").write_text("<!doctype html><title>x</title>")
        (tmp_path / "app-abc123.js").write_text("console.log(1)")
        client = TestClient(create_app(FakeLoader(), frontend_dist=tmp_path))
        assert client.get("/").headers["cache-control"] == "no-cache"
        assert "cache-control" not in client.get("/app-abc123.js").headers
        assert client.get("/api/health").json() == {"status": "ok"}
