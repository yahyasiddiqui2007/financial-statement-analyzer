"""Turn raw SEC facts into clean annual statements.

The raw data is messy in four ways, each handled here:

1. Duplicates. Each 10-K repeats the prior two years as comparisons, so one
   number appears in up to three filings. We keep one value per period, taken
   from the most recently filed annual report (which includes restatements).
2. Mixed periods. 10-Ks also contain quarterly numbers. We keep only
   durations of roughly one year.
3. Different fiscal year ends. Apple's year ends in late September, Microsoft's
   on June 30, many retailers' in late January. We never assume December 31:
   each period is identified by its actual start and end dates.
4. Different tags. We try each tag for a line item in priority order.

If none of this produces a trustworthy value, the line item is left out
(missing). We never fill gaps with guesses.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from datetime import date

from fsa.ingestion.companyfacts import RawFact
from fsa.ingestion.line_items import (
    DEFINITIONS,
    LineItem,
    LineItemDefinition,
    PeriodKind,
)
from fsa.ingestion.models import (
    AnnualPeriod,
    Company,
    FinancialHistory,
    LineItemValue,
    SourceFact,
)

ANNUAL_FORMS = frozenset({"10-K", "10-K/A"})
REPORTING_CURRENCY = "USD"

# A fiscal year is 52 or 53 weeks (363 or 370 days between start and end
# dates) or a calendar year (364 or 365). This range accepts all of those and
# rejects quarters, half-years and odd-length transition periods.
MIN_ANNUAL_DAYS = 350
MAX_ANNUAL_DAYS = 380

_DURATION_TAGS = frozenset(
    tag for d in DEFINITIONS.values() if d.kind is PeriodKind.DURATION for tag in d.tags
)


def build_financial_history(
    company: Company, facts: Iterable[RawFact], *, warnings: Sequence[str] = ()
) -> FinancialHistory:
    """Build normalized annual periods (oldest first) from raw facts."""
    notes = list(warnings)
    annual = [f for f in facts if f.form in ANNUAL_FORMS]
    notes.extend(_currency_warnings(annual))
    usd_facts = [f for f in annual if f.unit == REPORTING_CURRENCY]

    facts_by_tag: dict[str, list[RawFact]] = defaultdict(list)
    for fact in usd_facts:
        facts_by_tag[fact.tag].append(fact)

    bounds = _discover_periods(usd_facts)
    labels = _fiscal_year_labels(usd_facts, [end for _, end in bounds], notes)

    periods: list[AnnualPeriod] = []
    for start, end in bounds:
        label = f"Year ended {end.isoformat()}"
        values: dict[LineItem, LineItemValue] = {}
        for definition in DEFINITIONS.values():
            chosen = _select_value(definition, end, facts_by_tag, notes, label)
            if chosen is not None:
                values[definition.item] = chosen
        _derive_gross_profit(values)
        _derive_total_debt(values)
        periods.append(
            AnnualPeriod(start=start, end=end, fiscal_year=labels.get(end), values=values)
        )

    return FinancialHistory(company=company, periods=tuple(periods), warnings=tuple(notes))


def is_annual_duration(fact: RawFact) -> bool:
    if fact.start is None:
        return False
    return MIN_ANNUAL_DAYS <= (fact.end - fact.start).days <= MAX_ANNUAL_DAYS


def _discover_periods(facts: Sequence[RawFact]) -> list[tuple[date, date]]:
    """Find every fiscal year that has income statement or cash flow data.

    Returns (start, end) pairs sorted by end date. If facts disagree on the
    start date for one end date, the most common start wins.
    """
    starts_by_end: dict[date, Counter[date]] = defaultdict(Counter)
    for fact in facts:
        if fact.tag in _DURATION_TAGS and is_annual_duration(fact):
            assert fact.start is not None  # guaranteed by is_annual_duration
            starts_by_end[fact.end][fact.start] += 1

    bounds = []
    for end, starts in starts_by_end.items():
        # Highest count first; earliest date breaks ties so the result is stable.
        start = min(starts, key=lambda s: (-starts[s], s))
        bounds.append((start, end))
    return sorted(bounds, key=lambda b: b[1])


def _fiscal_year_labels(
    facts: Sequence[RawFact], ends: Sequence[date], notes: list[str]
) -> dict[date, int]:
    """Find the company's own fiscal-year label for each period end.

    The label comes from the 10-K that covers that year as its main year: the
    filing whose latest annual period ends on that date. Periods that only
    appear as prior-year comparisons get no label rather than a guess.
    """
    # For each filing: its main (latest) annual period end, filing date and "fy".
    filing_info: dict[str, tuple[date, date, int | None]] = {}
    for fact in facts:
        if not is_annual_duration(fact):
            continue
        current = filing_info.get(fact.accession_number)
        if current is None or fact.end > current[0]:
            filing_info[fact.accession_number] = (fact.end, fact.filed, fact.filing_fiscal_year)

    labels: dict[date, int] = {}
    for end in ends:
        originals = [info for info in filing_info.values() if info[0] == end]
        if not originals:
            continue
        _, _, fiscal_year = min(originals, key=lambda info: info[1])  # earliest filed
        if fiscal_year is not None:
            labels[end] = fiscal_year

    # If two periods claim the same label, at least one is wrong; drop both.
    counts = Counter(labels.values())
    ambiguous = sorted(fy for fy, count in counts.items() if count > 1)
    for fiscal_year in ambiguous:
        notes.append(f"Fiscal year label {fiscal_year} is ambiguous; showing end dates only.")
    return {end: fy for end, fy in labels.items() if fy not in ambiguous}


def _matches_period(fact: RawFact, kind: PeriodKind, end: date) -> bool:
    if fact.end != end:
        return False
    if kind is PeriodKind.INSTANT:
        return fact.start is None
    return is_annual_duration(fact)


def _select_value(
    definition: LineItemDefinition,
    end: date,
    facts_by_tag: dict[str, list[RawFact]],
    notes: list[str],
    period_label: str,
) -> LineItemValue | None:
    """Choose the value for one line item in one period.

    Tries each tag in priority order. For the first tag with data:
      - Keep facts from the most recently filed annual report.
      - If that report gives two different values, we can't tell which is
        right, so we skip this tag (with a warning) and try the next one.
      - Mark the value as restated if older filings reported something different.
    """
    for tag in definition.tags:
        candidates = [
            f for f in facts_by_tag.get(tag, []) if _matches_period(f, definition.kind, end)
        ]
        if not candidates:
            continue

        latest_filed = max(f.filed for f in candidates)
        latest = [f for f in candidates if f.filed == latest_filed]
        if len({f.value for f in latest}) > 1:
            notes.append(
                f"{period_label}: {tag} has conflicting values in filings dated "
                f"{latest_filed.isoformat()}; not used."
            )
            continue

        chosen = max(latest, key=lambda f: f.accession_number)  # stable tie-break
        return LineItemValue(
            item=definition.item,
            value=chosen.value,
            sources=(_source(chosen),),
            restated=len({f.value for f in candidates}) > 1,
        )
    return None


def _source(fact: RawFact) -> SourceFact:
    return SourceFact(
        tag=fact.tag,
        value=fact.value,
        accession_number=fact.accession_number,
        form=fact.form,
        filed=fact.filed,
    )


def _derive_gross_profit(values: dict[LineItem, LineItemValue]) -> None:
    """Gross profit = Revenue − Cost of revenue, when the company didn't report it."""
    if LineItem.GROSS_PROFIT in values:
        return
    revenue = values.get(LineItem.REVENUE)
    cost = values.get(LineItem.COST_OF_REVENUE)
    if revenue is None or cost is None:
        return
    values[LineItem.GROSS_PROFIT] = LineItemValue(
        item=LineItem.GROSS_PROFIT,
        value=revenue.value - cost.value,
        sources=revenue.sources + cost.sources,
        derivation="Revenue − Cost of revenue",
        restated=revenue.restated or cost.restated,
    )


_CURRENT_DEBT_PIECES = (
    LineItem.LONG_TERM_DEBT_CURRENT,
    LineItem.COMMERCIAL_PAPER,
    LineItem.SHORT_TERM_BORROWINGS,
)


def _derive_total_debt(values: dict[LineItem, LineItemValue]) -> None:
    """Total debt = non-current long-term debt + current debt.

    Current debt is "DebtCurrent" when reported (it already includes all the
    current pieces). Otherwise we add whichever current pieces are reported
    and list the missing ones in the derivation note.

    No total is produced if non-current debt is missing, or if no current
    debt figure of any kind is reported, because we can't tell whether the
    company has none or just tagged it differently.
    """
    noncurrent = values.get(LineItem.LONG_TERM_DEBT_NONCURRENT)
    if noncurrent is None:
        return

    debt_current = values.get(LineItem.DEBT_CURRENT)
    if debt_current is not None:
        parts = [noncurrent, debt_current]
        derivation = "Long-term debt (non-current) + Total current debt"
    else:
        present = [values[item] for item in _CURRENT_DEBT_PIECES if item in values]
        if not present:
            return
        missing = [DEFINITIONS[item].label for item in _CURRENT_DEBT_PIECES if item not in values]
        parts = [noncurrent, *present]
        derivation = " + ".join(DEFINITIONS[p.item].label for p in parts)
        if missing:
            derivation += f" (not reported, so not included: {', '.join(missing)})"

    values[LineItem.TOTAL_DEBT] = LineItemValue(
        item=LineItem.TOTAL_DEBT,
        value=sum((p.value for p in parts[1:]), start=parts[0].value),
        sources=tuple(s for p in parts for s in p.sources),
        derivation=derivation,
        restated=any(p.restated for p in parts),
    )


def _currency_warnings(facts: Iterable[RawFact]) -> list[str]:
    """Flag tags reported only in a currency other than USD (we don't convert currencies)."""
    units_by_tag: dict[str, set[str]] = defaultdict(set)
    for fact in facts:
        units_by_tag[fact.tag].add(fact.unit)
    return [
        f"{tag} is reported in {', '.join(sorted(units))}, not USD; currency conversion "
        "is not supported, so it is excluded."
        for tag, units in sorted(units_by_tag.items())
        if REPORTING_CURRENCY not in units
    ]
