"""The evidence pack: the only information the AI model is given.

Every fact gets a short, stable ID (e.g. "metric:gross_margin:FY2025"). The
model must cite these IDs for each claim, and the validator checks that the
numbers in a claim actually appear in the evidence it cites.

Values are pre-formatted ("46.9%", "$416,161M") so the model can copy them
exactly instead of doing its own arithmetic or rounding.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Literal

from fsa.analysis import METRIC_DISPLAY, annual_metrics
from fsa.analytics import MetricResult
from fsa.ingestion import AnnualPeriod, FinancialHistory, LineItem
from fsa.trends import MIN_YEARS, analyze_trends
from fsa.trends import text as fmt
from fsa.trends.models import Statistic

EvidenceKind = Literal["line_item", "metric", "trend", "trend_statistic"]

PACK_YEARS = 5

# Statement lines worth giving the model; the rest are mostly components of these.
LINE_ITEMS = (
    LineItem.REVENUE,
    LineItem.GROSS_PROFIT,
    LineItem.OPERATING_INCOME,
    LineItem.NET_INCOME,
    LineItem.OPERATING_CASH_FLOW,
    LineItem.CAPITAL_EXPENDITURES,
    LineItem.CASH_AND_EQUIVALENTS,
    LineItem.CURRENT_ASSETS,
    LineItem.TOTAL_ASSETS,
    LineItem.CURRENT_LIABILITIES,
    LineItem.TOTAL_LIABILITIES,
    LineItem.TOTAL_DEBT,
    LineItem.TOTAL_EQUITY,
)

LINE_ITEM_LABELS = {
    LineItem.REVENUE: "Revenue",
    LineItem.GROSS_PROFIT: "Gross profit",
    LineItem.OPERATING_INCOME: "Operating income",
    LineItem.NET_INCOME: "Net income",
    LineItem.OPERATING_CASH_FLOW: "Operating cash flow",
    LineItem.CAPITAL_EXPENDITURES: "Capital expenditures",
    LineItem.CASH_AND_EQUIVALENTS: "Cash and cash equivalents",
    LineItem.CURRENT_ASSETS: "Current assets",
    LineItem.TOTAL_ASSETS: "Total assets",
    LineItem.CURRENT_LIABILITIES: "Current liabilities",
    LineItem.TOTAL_LIABILITIES: "Total liabilities",
    LineItem.TOTAL_DEBT: "Total debt",
    LineItem.TOTAL_EQUITY: "Shareholders' equity",
}


@dataclass(frozen=True, slots=True)
class Evidence:
    id: str
    kind: EvidenceKind
    label: str
    period: str | None  # "FY2025", or None for multi-year trend facts
    value: str  # formatted value, or a sentence for trend facts
    note: str | None = None  # formula, derivation, or why a value is unavailable


@dataclass(frozen=True, slots=True)
class EvidencePack:
    company_name: str
    ticker: str
    fiscal_years: tuple[str, ...]
    items: tuple[Evidence, ...]

    def by_id(self) -> dict[str, Evidence]:
        return {e.id: e for e in self.items}

    def to_prompt_json(self) -> str:
        """The exact text sent to the model. Sorted and stable, so it's easy to inspect."""
        return json.dumps(
            {
                "company": {"name": self.company_name, "ticker": self.ticker},
                "fiscal_years": list(self.fiscal_years),
                "evidence": [
                    {k: v for k, v in asdict(e).items() if v is not None} for e in self.items
                ],
            },
            ensure_ascii=False,
            indent=1,
        )


def _period_key(period: AnnualPeriod) -> str:
    return f"FY{period.fiscal_year}" if period.fiscal_year is not None else period.end.isoformat()


def _metric_value(result: MetricResult, fmt_name: str) -> str:
    if result.value is None:
        return "not available"
    if fmt_name == "percent":
        return fmt.percent(result.value)
    if fmt_name == "ratio":
        return fmt.ratio(result.value)
    return fmt.money(result.value)


def _signed_ratio(value: Decimal) -> str:
    return ("+" if value > 0 else "") + fmt.ratio(value)


_STAT_FORMATTERS: dict[str, Callable[[Decimal], str]] = {
    "usd": fmt.money,
    "usd_change": fmt.signed_money,
    "percent": fmt.percent,
    "percent_change": fmt.signed_percent,
    "pp_change": fmt.points,
    "ratio": fmt.ratio,
    "ratio_change": _signed_ratio,
}


def _statistic_value(stat: Statistic) -> str:
    if stat.result.value is None:
        return "not available"
    return _STAT_FORMATTERS[stat.format](stat.result.value)


def _trend_evidence(history: FinancialHistory, years: int) -> list[Evidence]:
    """Each trend finding, plus each statistic behind it, as citable evidence."""
    if years < MIN_YEARS:
        return []
    report = analyze_trends(history, years)
    items = []
    for finding in report.findings:
        sentences = " ".join((finding.summary, *finding.details))
        items.append(
            Evidence(
                id=f"trend:{finding.topic}",
                kind="trend",
                label=f"{finding.title} trend ({report.start_label} to {report.end_label})",
                period=None,
                value=f"Direction: {finding.direction.value}. {sentences}",
                note=finding.method,
            )
        )
        for stat in finding.statistics:
            result = stat.result
            items.append(
                Evidence(
                    id=f"trend:{finding.topic}:{stat.key}",
                    kind="trend_statistic",
                    label=f"{finding.title}: {stat.label}",
                    period=None,
                    value=_statistic_value(stat),
                    note=result.formula if result.value is not None else result.reason,
                )
            )
    return items


def build_evidence_pack(history: FinancialHistory, years: int = PACK_YEARS) -> EvidencePack:
    periods = list(history.periods[-years:])
    items: list[Evidence] = []

    for period in periods:
        key = _period_key(period)
        for item in LINE_ITEMS:
            line = period.values.get(item)
            notes = []
            if line is not None and line.derivation:
                notes.append(f"derived: {line.derivation}")
            if line is not None and line.restated:
                notes.append("restated in a later filing")
            items.append(
                Evidence(
                    id=f"item:{item.value}:{key}",
                    kind="line_item",
                    label=LINE_ITEM_LABELS[item],
                    period=key,
                    value=fmt.money(line.value) if line is not None else "not reported",
                    note="; ".join(notes) or None,
                )
            )

        for name, result in annual_metrics(history, period).items():
            label, fmt_name = METRIC_DISPLAY[name]
            items.append(
                Evidence(
                    id=f"metric:{name}:{key}",
                    kind="metric",
                    label=label,
                    period=key,
                    value=_metric_value(result, fmt_name),
                    note=result.formula if result.value is not None else result.reason,
                )
            )

    items.extend(_trend_evidence(history, len(periods)))

    ids = [e.id for e in items]
    if len(ids) != len(set(ids)):
        # Citations must point at exactly one fact; a duplicate id is a bug.
        raise ValueError("Evidence ids must be unique")

    return EvidencePack(
        company_name=history.company.name,
        ticker=history.company.ticker,
        fiscal_years=tuple(_period_key(p) for p in periods),
        items=tuple(items),
    )
