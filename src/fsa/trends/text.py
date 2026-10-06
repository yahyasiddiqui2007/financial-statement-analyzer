"""Number formatting for the sentences in trend findings.

These only round and add units. Values are rounded half-up, the way most
people round by hand, so a sentence and its statistic always agree.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from fsa.ingestion import AnnualPeriod

MINUS = "−"  # typographic minus sign
MILLION = Decimal(1_000_000)


def _round(value: Decimal, places: int) -> Decimal:
    return value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def _grouped(value: Decimal, places: int) -> str:
    return f"{_round(abs(value), places):,.{places}f}"


def _is_zero_when_rounded(value: Decimal, places: int) -> bool:
    return _round(abs(value), places) == 0


def money(value: Decimal) -> str:
    """391035000000 → "$391,035M"; negatives get a minus sign."""
    millions = value / MILLION
    places = 0 if abs(millions) >= 100 else 1
    text = f"${_grouped(millions, places)}M"
    return f"{MINUS}{text}" if value < 0 and not _is_zero_when_rounded(millions, places) else text


def signed_money(value: Decimal) -> str:
    """+$903M / −$21,412M."""
    text = money(abs(value))
    millions = value / MILLION
    places = 0 if abs(millions) >= 100 else 1
    if _is_zero_when_rounded(millions, places):
        return text
    return f"+{text}" if value > 0 else f"{MINUS}{text}"


def percent(value: Decimal) -> str:
    """0.0328 → "3.3%"."""
    scaled = value * 100
    sign = MINUS if scaled < 0 and not _is_zero_when_rounded(scaled, 1) else ""
    return f"{sign}{_grouped(scaled, 1)}%"


def percent_value(value: Decimal) -> Decimal:
    """The percentage as displayed, for comparisons: 0.03749 → 3.7."""
    return _round(value * 100, 1)


def signed_percent(value: Decimal) -> str:
    """0.064 → "+6.4%"."""
    scaled = value * 100
    if _is_zero_when_rounded(scaled, 1):
        return "0.0%"
    return f"{'+' if scaled > 0 else MINUS}{_grouped(scaled, 1)}%"


def points(value: Decimal) -> str:
    """Change between two percentages: 0.022 → "+2.2 pp"."""
    scaled = value * 100
    if _is_zero_when_rounded(scaled, 1):
        return "0.0 pp"
    return f"{'+' if scaled > 0 else MINUS}{_grouped(scaled, 1)} pp"


def ratio(value: Decimal) -> str:
    """1.3412 → "1.34x"."""
    sign = MINUS if value < 0 and not _is_zero_when_rounded(value, 2) else ""
    return f"{sign}{_grouped(value, 2)}x"


def period_label(period: AnnualPeriod) -> str:
    """The company's own label ("FY2025"), or the end date when the filings don't give one."""
    if period.fiscal_year is not None:
        return f"FY{period.fiscal_year}"
    return f"the year ended {period.end.isoformat()}"
