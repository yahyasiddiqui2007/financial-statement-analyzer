"""Convert pipeline objects (FinancialHistory, MetricResult) into API responses.

No new financial numbers are invented here. Every value is either a number
from the normalized SEC data, a MetricResult from the calculation engine, or
a simple difference between two of those results.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fsa.ai import AIAnalysis, Claim
from fsa.ai.validation import Section
from fsa.analysis import METRIC_DISPLAY, annual_metrics
from fsa.analytics import MetricResult, percent_change
from fsa.api.schemas import (
    AIAnalysisOut,
    AIClaimOut,
    AIEvidenceOut,
    AIRejectedClaimOut,
    CellOut,
    ChangeOut,
    CompanyOut,
    DataSourceOut,
    FinancialsOut,
    MetricOut,
    MetricValueOut,
    PeriodOut,
    RowOut,
    SourceFactOut,
    StatementOut,
    TrendFindingOut,
    TrendPointOut,
    TrendReportOut,
    TrendSeriesOut,
    TrendStatisticOut,
)
from fsa.ingestion import DEFINITIONS, AnnualPeriod, FinancialHistory, LineItem, Statement
from fsa.trends import TrendReport, analyze_trends

STATEMENT_TITLES = {
    Statement.INCOME: "Income Statement",
    Statement.BALANCE: "Balance Sheet",
    Statement.CASH_FLOW: "Cash Flow Statement",
}


TREND_WINDOWS = (3, 5)

PROVIDER = "SEC EDGAR XBRL company facts (10-K and 10-K/A filings)"


def decimal_str(value: Decimal | None) -> str | None:
    """Exact string form, never scientific notation ("1E+9" → "1000000000")."""
    return None if value is None else format(value, "f")


def present_financials(
    history: FinancialHistory, *, retrieved_at: datetime, max_periods: int | None = None
) -> FinancialsOut:
    all_periods = list(history.periods)
    periods = all_periods[-max_periods:] if max_periods else all_periods
    priors = [history.prior_to(p) for p in periods]
    metrics_by_period = [annual_metrics(history, p) for p in periods]
    prior_metrics = [annual_metrics(history, p) if p else None for p in priors]

    cik = history.company.cik
    return FinancialsOut(
        company=CompanyOut(
            cik=cik,
            ticker=history.company.ticker,
            name=history.company.name,
            edgar_url=(
                "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
                f"&CIK={cik}&type=10-K&dateb=&owner=include&count=40"
            ),
        ),
        source=DataSourceOut(
            provider=PROVIDER,
            url=f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
            retrieved_at=retrieved_at,
        ),
        periods=[
            PeriodOut(
                start=p.start,
                end=p.end,
                fiscal_year=p.fiscal_year,
                label=p.label,
                has_prior=prior is not None,
            )
            for p, prior in zip(periods, priors, strict=True)
        ],
        statements=[
            StatementOut(
                id=statement.value,
                title=STATEMENT_TITLES[statement],
                rows=[
                    RowOut(
                        item=d.item.value,
                        label=d.label,
                        cells=[
                            _cell(cik, p, prior, d.item)
                            for p, prior in zip(periods, priors, strict=True)
                        ],
                    )
                    for d in DEFINITIONS.values()
                    if d.statement is statement
                ],
            )
            for statement in Statement
        ],
        metrics=[
            MetricOut(
                name=name,
                label=label,
                format=fmt,
                formula=metrics_by_period[0][name].formula if metrics_by_period else "",
                values=[
                    _metric_value(current[name], prior[name] if prior else None)
                    for current, prior in zip(metrics_by_period, prior_metrics, strict=True)
                ],
            )
            for name, (label, fmt) in METRIC_DISPLAY.items()
        ],
        trends=_trend_reports(history),
        warnings=list(history.warnings),
    )


def _trend_reports(history: FinancialHistory) -> list[TrendReportOut]:
    """One report per window; skips a window that would repeat a shorter one's years."""
    reports: list[TrendReportOut] = []
    seen_lengths: set[int] = set()
    for years in TREND_WINDOWS:
        report = analyze_trends(history, years)
        if report.years in seen_lengths:
            continue
        seen_lengths.add(report.years)
        reports.append(_trend_report(report))
    return reports


def _trend_report(report: TrendReport) -> TrendReportOut:
    return TrendReportOut(
        requested_years=report.requested_years,
        years=report.years,
        start_label=report.start_label,
        end_label=report.end_label,
        notes=list(report.notes),
        findings=[
            TrendFindingOut(
                topic=f.topic,
                title=f.title,
                direction=f.direction.value,
                summary=f.summary,
                details=list(f.details),
                method=f.method,
                statistics=[
                    TrendStatisticOut(
                        key=s.key,
                        label=s.label,
                        format=s.format,
                        value=decimal_str(s.result.value),
                        status=s.result.status.value,
                        reason=s.result.reason,
                        formula=s.result.formula,
                        inputs={k: decimal_str(v) for k, v in s.result.inputs.items()},
                    )
                    for s in f.statistics
                ],
                series=[
                    TrendSeriesOut(
                        key=series.key,
                        label=series.label,
                        format=series.format,
                        points=[
                            TrendPointOut(label=p.label, end=p.end, value=decimal_str(p.value))
                            for p in series.points
                        ],
                    )
                    for series in f.series
                ],
            )
            for f in report.findings
        ],
    )


def _cell(cik: str, period: AnnualPeriod, prior: AnnualPeriod | None, item: LineItem) -> CellOut:
    line = period.values.get(item)
    change = None
    if prior is not None:
        result = percent_change(period.get(item), prior.get(item))
        change = ChangeOut(
            value=decimal_str(result.value), status=result.status.value, reason=result.reason
        )
    if line is None:
        return CellOut(
            value=None, derived=False, derivation=None, restated=False, sources=[], change=change
        )
    return CellOut(
        value=decimal_str(line.value),
        derived=line.is_derived,
        derivation=line.derivation,
        restated=line.restated,
        sources=[
            SourceFactOut(
                tag=s.tag,
                accession_number=s.accession_number,
                form=s.form,
                filed=s.filed,
                url=s.filing_url(cik),
            )
            for s in line.sources
        ],
        change=change,
    )


def _metric_value(current: MetricResult, prior: MetricResult | None) -> MetricValueOut:
    difference = None
    if prior is not None and current.value is not None and prior.value is not None:
        difference = current.value - prior.value
    return MetricValueOut(
        value=decimal_str(current.value),
        status=current.status.value,
        reason=current.reason,
        difference=decimal_str(difference),
        inputs={k: decimal_str(v) for k, v in current.inputs.items()},
    )


def present_ai_analysis(analysis: AIAnalysis) -> AIAnalysisOut:
    def claims(section: Section) -> list[AIClaimOut]:
        return [_claim(c) for c in analysis.sections.get(section, ())]

    return AIAnalysisOut(
        ticker=analysis.company_ticker,
        model=analysis.model,
        generated_at=analysis.generated_at,
        disclaimer=analysis.disclaimer,
        evidence_count=analysis.evidence_count,
        strengths=claims("strengths"),
        concerns=claims("concerns"),
        trends=claims("trends"),
        questions=claims("questions"),
        rejected=[
            AIRejectedClaimOut(section=r.section, statement=r.statement, reason=r.reason)
            for r in analysis.rejected
        ],
    )


def _claim(claim: Claim) -> AIClaimOut:
    return AIClaimOut(
        statement=claim.statement,
        evidence=[
            AIEvidenceOut(
                id=e.id, kind=e.kind, label=e.label, period=e.period, value=e.value, note=e.note
            )
            for e in claim.evidence
        ],
    )
