"""Parse the SEC's companyfacts JSON into a flat list of typed facts.

The response is deeply nested:

    {"cik": 320193, "entityName": "Apple Inc.",
     "facts": {"us-gaap": {"Assets": {"units": {"USD": [
         {"end": "2024-09-28", "val": 364980000000, "accn": "0000320193-24-000123",
          "fy": 2024, "fp": "FY", "form": "10-K", "filed": "2024-11-01"},
         ...]}}}}}

Duration facts (revenue) also have a "start" date; instant facts (assets) don't.

Watch out: "fy" and "fp" describe the FILING, not the period of the number.
Apple's FY2024 10-K reports FY2022, FY2023 and FY2024 revenue, all with
fy=2024. That's why later steps identify periods by their start/end dates.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from fsa.ingestion.errors import DataFormatError

US_GAAP = "us-gaap"


@dataclass(frozen=True, slots=True)
class RawFact:
    """One number from one filing, exactly as the SEC reported it."""

    tag: str
    unit: str
    value: Decimal
    start: date | None  # None for instant (balance sheet) facts
    end: date
    form: str
    accession_number: str
    filed: date
    filing_fiscal_year: int | None  # the "fy" field: the filing's year, not the fact's


@dataclass(frozen=True, slots=True)
class ParsedCompanyFacts:
    cik: str
    entity_name: str
    facts: tuple[RawFact, ...]
    warnings: tuple[str, ...]


def parse_company_facts(payload: Any, *, tags: Collection[str]) -> ParsedCompanyFacts:
    """Extract the US GAAP facts for `tags`.

    Raises DataFormatError if the overall structure is wrong. Individual
    malformed facts are skipped and reported in `warnings`, so one bad entry
    doesn't hide twenty years of good data.
    """
    if not isinstance(payload, dict):
        raise DataFormatError("companyfacts response should be a JSON object.")
    cik, name, all_facts = payload.get("cik"), payload.get("entityName"), payload.get("facts")
    if isinstance(cik, bool) or not isinstance(cik, int):
        raise DataFormatError("companyfacts response is missing an integer 'cik'.")
    if not isinstance(name, str) or not isinstance(all_facts, dict):
        raise DataFormatError("companyfacts response is missing 'entityName' or 'facts'.")

    # Companies filing under IFRS (most foreign companies) have no us-gaap section.
    gaap = all_facts.get(US_GAAP, {})
    if not isinstance(gaap, dict):
        raise DataFormatError("'us-gaap' section should be a JSON object.")

    facts: list[RawFact] = []
    skipped = 0
    for tag in sorted(tags):  # sorted so results are always in the same order
        concept = gaap.get(tag)
        if concept is None:
            continue
        units = concept.get("units") if isinstance(concept, dict) else None
        if not isinstance(units, dict):
            raise DataFormatError(f"Tag {tag} has no 'units' object.")
        for unit, entries in units.items():
            if not isinstance(entries, list):
                raise DataFormatError(f"Tag {tag} unit {unit} should be a list.")
            for entry in entries:
                fact = _parse_fact(tag, unit, entry)
                if fact is None:
                    skipped += 1
                else:
                    facts.append(fact)

    warnings = [f"Skipped {skipped} malformed fact(s) in the SEC data."] if skipped else []
    return ParsedCompanyFacts(
        cik=f"{cik:010d}", entity_name=name, facts=tuple(facts), warnings=tuple(warnings)
    )


def _parse_fact(tag: str, unit: str, entry: Any) -> RawFact | None:
    """Convert one JSON entry, or return None if a required field is missing or invalid."""
    if not isinstance(entry, dict):
        return None
    try:
        value = _to_decimal(entry["val"])
        start = date.fromisoformat(entry["start"]) if "start" in entry else None
        end = date.fromisoformat(entry["end"])
        filed = date.fromisoformat(entry["filed"])
        form, accession = entry["form"], entry["accn"]
    except (KeyError, TypeError, ValueError):
        return None
    if value is None or not isinstance(form, str) or not isinstance(accession, str):
        return None
    if start is not None and start > end:
        return None

    fy = entry.get("fy")
    return RawFact(
        tag=tag,
        unit=unit,
        value=value,
        start=start,
        end=end,
        form=form,
        accession_number=accession,
        filed=filed,
        filing_fiscal_year=fy if isinstance(fy, int) and not isinstance(fy, bool) else None,
    )


def _to_decimal(raw: Any) -> Decimal | None:
    # The client parses JSON decimals as Decimal; whole numbers arrive as int.
    if isinstance(raw, bool) or not isinstance(raw, (int, Decimal)):
        return None
    value = Decimal(raw)
    return value if value.is_finite() else None
