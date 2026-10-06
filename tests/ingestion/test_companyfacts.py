from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from factories import load_fixture

from fsa.ingestion.companyfacts import parse_company_facts
from fsa.ingestion.errors import DataFormatError
from fsa.ingestion.line_items import ALL_TAGS


@pytest.fixture
def payload() -> Any:
    return load_fixture("companyfacts_example.json")


def test_reads_company_identity(payload: Any) -> None:
    parsed = parse_company_facts(payload, tags=ALL_TAGS)
    assert parsed.cik == "0001234567"
    assert parsed.entity_name == "Example Manufacturing Corp"


def test_only_requested_tags_are_kept(payload: Any) -> None:
    parsed = parse_company_facts(payload, tags={"Assets"})
    assert {f.tag for f in parsed.facts} == {"Assets"}


def test_unused_tags_and_other_taxonomies_are_ignored(payload: Any) -> None:
    tags = {f.tag for f in parse_company_facts(payload, tags=ALL_TAGS).facts}
    assert "SomeTagWeDoNotUse" not in tags
    assert "EntityCommonStockSharesOutstanding" not in tags


def test_duration_fact_fields(payload: Any) -> None:
    parsed = parse_company_facts(payload, tags={"Revenues"})
    first = parsed.facts[0]
    assert first.value == Decimal("800000000")
    assert first.start == date(2022, 7, 1)
    assert first.end == date(2023, 6, 30)
    assert first.form == "10-K"
    assert first.accession_number == "0001234567-24-000010"
    assert first.filed == date(2024, 8, 14)
    assert first.filing_fiscal_year == 2024


def test_instant_fact_has_no_start(payload: Any) -> None:
    parsed = parse_company_facts(payload, tags={"Assets"})
    assert all(f.start is None for f in parsed.facts)


def test_malformed_fact_is_skipped_with_warning(payload: Any) -> None:
    parsed = parse_company_facts(payload, tags={"NetIncomeLoss"})
    assert len(parsed.facts) == 4  # the 5th entry has no "val"
    assert parsed.warnings == ("Skipped 1 malformed fact(s) in the SEC data.",)


def test_no_us_gaap_section_gives_no_facts() -> None:
    ifrs_filer = {"cik": 1, "entityName": "Foreign Co", "facts": {"ifrs-full": {}}}
    assert parse_company_facts(ifrs_filer, tags=ALL_TAGS).facts == ()


def _entry(**overrides: Any) -> dict[str, Any]:
    base = {"end": "2024-12-31", "val": 5, "accn": "a", "form": "10-K", "filed": "2025-02-01"}
    return {**base, **overrides}


@pytest.mark.parametrize(
    "bad_entry",
    [
        _entry(val=None),
        _entry(val="5"),
        _entry(val=True),
        _entry(end="not-a-date"),
        _entry(start="2025-06-30"),  # start after end
        "not an object",
    ],
)
def test_invalid_entries_are_skipped(bad_entry: Any) -> None:
    payload = {
        "cik": 1,
        "entityName": "X",
        "facts": {"us-gaap": {"Assets": {"units": {"USD": [bad_entry, _entry()]}}}},
    }
    parsed = parse_company_facts(payload, tags={"Assets"})
    assert len(parsed.facts) == 1
    assert len(parsed.warnings) == 1


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"entityName": "X", "facts": {}},
        {"cik": "1", "entityName": "X", "facts": {}},
        {"cik": 1, "facts": {}},
        {"cik": 1, "entityName": "X", "facts": {"us-gaap": []}},
        {"cik": 1, "entityName": "X", "facts": {"us-gaap": {"Assets": {"units": []}}}},
        {"cik": 1, "entityName": "X", "facts": {"us-gaap": {"Assets": {"units": {"USD": {}}}}}},
    ],
)
def test_bad_structure_raises(payload: Any) -> None:
    with pytest.raises(DataFormatError):
        parse_company_facts(payload, tags={"Assets"})
