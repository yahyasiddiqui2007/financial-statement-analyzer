from typing import Any

import pytest
from factories import load_fixture

from fsa.ingestion.errors import DataFormatError, TickerNotFoundError
from fsa.ingestion.tickers import find_company, normalize_ticker


@pytest.fixture
def tickers() -> Any:
    return load_fixture("company_tickers_example.json")


class TestNormalizeTicker:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [("AAPL", "AAPL"), (" aapl ", "AAPL"), ("brk.b", "BRK-B"), ("BRK-B", "BRK-B")],
    )
    def test_cleans_input(self, raw: str, expected: str) -> None:
        assert normalize_ticker(raw) == expected

    @pytest.mark.parametrize("raw", ["", "   ", "AAPL; DROP TABLE", "A" * 11, "$AAPL"])
    def test_rejects_invalid(self, raw: str) -> None:
        with pytest.raises(TickerNotFoundError):
            normalize_ticker(raw)


class TestFindCompany:
    def test_finds_company_and_pads_cik(self, tickers: Any) -> None:
        company = find_company(tickers, "aapl")
        assert company.cik == "0000320193"
        assert company.ticker == "AAPL"
        assert company.name == "Apple Inc."

    def test_class_shares_with_dot(self, tickers: Any) -> None:
        assert find_company(tickers, "BRK.B").cik == "0001067983"

    def test_unknown_ticker(self, tickers: Any) -> None:
        with pytest.raises(TickerNotFoundError, match="ZZZZ"):
            find_company(tickers, "ZZZZ")

    @pytest.mark.parametrize(
        "payload",
        [
            [],
            {"0": "not an object"},
            {"0": {"ticker": "AAPL", "cik_str": "320193", "title": "Apple"}},
            {"0": {"ticker": "AAPL", "cik_str": 320193}},
        ],
    )
    def test_malformed_payload(self, payload: Any) -> None:
        with pytest.raises(DataFormatError):
            find_company(payload, "AAPL")
