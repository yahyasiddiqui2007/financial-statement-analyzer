"""Multi-year trend analysis built only on calculated metrics.

For the last 3–5 consecutive fiscal years, each analysis below:
  1. collects yearly values from the normalized statements or the metric engine,
  2. calculates summary statistics with the engine (CAGR, changes),
  3. picks a direction with a simple, stated threshold rule, and
  4. writes factual sentences using only those numbers.

The output describes what happened in the filings. It does not judge whether
a trend is good or bad for investors, and it never recommends anything.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal

from fsa.analysis import annual_metrics
from fsa.analytics import (
    MetricResult,
    absolute_change,
    compound_annual_growth_rate,
    percent_change,
    working_capital,
)
from fsa.ingestion import AnnualPeriod, FinancialHistory, LineItem
from fsa.trends import text
from fsa.trends.models import (
    Direction,
    Series,
    SeriesPoint,
    Statistic,
    TrendFinding,
    TrendReport,
    ValueFormat,
)

ROUNDING_NOTE = (
    " Changes are calculated from unrounded values, so they can differ by 0.1 from the "
    "difference between the rounded figures shown."
)

MIN_YEARS = 3
MAX_YEARS = 5

# Thresholds for calling something "stable" instead of increasing/decreasing.
# They are deliberately simple so anyone can check a conclusion by hand.
STABLE_GROWTH_RATE = Decimal("0.01")  # CAGR within ±1% a year
STABLE_MARGIN_CHANGE = Decimal("0.01")  # margin change within ±1 percentage point
STABLE_BALANCE_CHANGE = Decimal("0.05")  # debt or cash change within ±5% over the window
STABLE_WORKING_CAPITAL_SHARE = Decimal("0.01")  # change within ±1% of ending-year revenue


def trend_window(history: FinancialHistory, years: int) -> list[AnnualPeriod]:
    """The latest `years` consecutive fiscal years, oldest first.

    Stops early at a gap (a missing year), because a trend across a gap
    would compare years that aren't actually next to each other.
    """
    if history.latest is None:
        return []
    window = [history.latest]
    while len(window) < years:
        prior = history.prior_to(window[0])
        if prior is None:
            break
        window.insert(0, prior)
    return window


def analyze_trends(history: FinancialHistory, years: int = MAX_YEARS) -> TrendReport:
    if not MIN_YEARS <= years <= MAX_YEARS:
        raise ValueError(f"years must be between {MIN_YEARS} and {MAX_YEARS}")

    periods = trend_window(history, years)
    notes: list[str] = []
    if len(periods) < MIN_YEARS:
        notes.append(
            f"Trend analysis needs at least {MIN_YEARS} consecutive fiscal years; "
            f"only {len(periods)} {'is' if len(periods) == 1 else 'are'} available."
        )
        return TrendReport(
            requested_years=years,
            years=len(periods),
            start_label=text.period_label(periods[0]) if periods else None,
            end_label=text.period_label(periods[-1]) if periods else None,
            findings=(),
            notes=tuple(notes),
        )
    if len(periods) < years:
        notes.append(
            f"Only {len(periods)} consecutive fiscal years are available, "
            f"so this analysis covers {len(periods)} years instead of {years}."
        )

    w = _Window(history, periods)
    revenue = _level_trend(
        w,
        topic="revenue_growth",
        title="Revenue growth",
        label="Revenue",
        key=LineItem.REVENUE.value,
        values=w.items(LineItem.REVENUE),
    )
    findings = [
        _with_extra_details(revenue.finding, _revenue_pace_details(w, revenue)),
        _margin_trend(w),
        _level_trend(
            w,
            topic="net_income_growth",
            title="Net income growth",
            label="Net income",
            key=LineItem.NET_INCOME.value,
            values=w.items(LineItem.NET_INCOME),
        ).finding,
        _level_trend(
            w,
            topic="fcf_growth",
            title="Free cash flow growth",
            label="Free cash flow",
            key="free_cash_flow",
            values=w.metric("free_cash_flow"),
            definition="Free cash flow = operating cash flow − capital expenditures.",
        ).finding,
        _debt_trend(w),
        _cash_trend(w),
        _asset_trend(w, revenue.cagr),
        _working_capital_trend(w),
    ]
    return TrendReport(
        requested_years=years,
        years=len(periods),
        start_label=w.first_label,
        end_label=w.last_label,
        findings=tuple(findings),
        notes=tuple(notes),
    )


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


@dataclass
class _Window:
    history: FinancialHistory
    periods: list[AnnualPeriod]

    def __post_init__(self) -> None:
        self.labels = [text.period_label(p) for p in self.periods]
        self.metrics = [annual_metrics(self.history, p) for p in self.periods]

    @property
    def first_label(self) -> str:
        return self.labels[0]

    @property
    def last_label(self) -> str:
        return self.labels[-1]

    @property
    def steps(self) -> int:
        """Number of year-to-year steps (5 fiscal years → 4 steps)."""
        return len(self.periods) - 1

    def items(self, item: LineItem) -> list[Decimal | None]:
        return [p.get(item) for p in self.periods]

    def metric(self, name: str) -> list[Decimal | None]:
        return [m[name].value for m in self.metrics]

    def metric_results(self, name: str) -> list[MetricResult]:
        return [m[name] for m in self.metrics]

    def series(
        self, key: str, label: str, fmt: ValueFormat, values: Sequence[Decimal | None]
    ) -> Series:
        return Series(
            key=key,
            label=label,
            format=fmt,
            points=tuple(
                SeriesPoint(label=lbl, end=p.end, value=v)
                for lbl, p, v in zip(self.labels, self.periods, values, strict=True)
            ),
        )

    def yearly_changes(self, values: Sequence[Decimal | None]) -> list[MetricResult | None]:
        """Percent change for each year vs the year before (None for the first year)."""
        return [None] + [percent_change(values[i], values[i - 1]) for i in range(1, len(values))]


def _classify(value: Decimal, band: Decimal) -> Direction:
    if value > band:
        return Direction.INCREASING
    if value < -band:
        return Direction.DECREASING
    return Direction.STABLE


def _sign_direction(value: Decimal) -> Direction:
    return _classify(value, Decimal(0))


def _unavailable_reason(result: MetricResult) -> str:
    """Plain-English reason a metric has no value."""
    if result.status.value == "missing_input":
        return "an input is not reported in the filings."
    return result.reason or "not reported."


def _missing_years(labels: Sequence[str], values: Sequence[Decimal | None]) -> str:
    missing = [lbl for lbl, v in zip(labels, values, strict=True) if v is None]
    return ", ".join(missing)


def _insufficient(
    topic: str, title: str, summary: str, series: tuple[Series, ...], method: str
) -> TrendFinding:
    return TrendFinding(
        topic=topic,
        title=title,
        direction=Direction.INSUFFICIENT_DATA,
        summary=summary,
        details=(),
        statistics=(),
        series=series,
        method=method,
    )


def _with_extra_details(finding: TrendFinding, extra: Sequence[str]) -> TrendFinding:
    if not extra:
        return finding
    return TrendFinding(
        topic=finding.topic,
        title=finding.title,
        direction=finding.direction,
        summary=finding.summary,
        details=finding.details + tuple(extra),
        statistics=finding.statistics,
        series=finding.series,
        method=finding.method,
    )


def _consistency_sentence(w: _Window, label: str, values: Sequence[Decimal | None]) -> str | None:
    """'Revenue increased in 3 of 4 years.' Counts only years with both values reported."""
    pairs: list[tuple[Decimal, Decimal]] = []
    for before, after in zip(values, values[1:], strict=False):
        if before is not None and after is not None:
            pairs.append((before, after))
    if not pairs:
        return None
    ups = sum(1 for before, after in pairs if after > before)
    downs = sum(1 for before, after in pairs if after < before)
    parts = [f"{label} increased in {ups} of {len(pairs)} year-over-year comparisons"]
    if downs:
        parts.append(f"and decreased in {downs}")
    return " ".join(parts) + "."


def _range_sentence(w: _Window, changes: Sequence[MetricResult | None]) -> str | None:
    """'Yearly changes ranged from −2.8% (FY2023) to +7.8% (FY2022).'"""
    known = [
        (c.value, w.labels[i])
        for i, c in enumerate(changes)
        if c is not None and c.value is not None
    ]
    if len(known) < 2:
        return None
    low = min(known, key=lambda k: k[0])
    high = max(known, key=lambda k: k[0])
    return (
        f"Year-over-year changes ranged from {text.signed_percent(low[0])} ({low[1]}) "
        f"to {text.signed_percent(high[0])} ({high[1]})."
    )


# ---------------------------------------------------------------------------
# Growth of a level: revenue, net income, free cash flow, total assets
# ---------------------------------------------------------------------------

GROWTH_METHOD = (
    "Direction comes from the compound annual growth rate (CAGR) between the first and last "
    "year: above +1% a year is increasing, below −1% a year is decreasing, otherwise stable. "
    "When CAGR is not meaningful (a negative value at either end, such as a net loss), the "
    "direction follows the sign of the total change instead."
) + ROUNDING_NOTE


@dataclass(frozen=True)
class _LevelTrend:
    finding: TrendFinding
    cagr: MetricResult | None
    changes: list[MetricResult | None]


def _level_trend(
    w: _Window,
    *,
    topic: str,
    title: str,
    label: str,
    key: str,
    values: list[Decimal | None],
    definition: str | None = None,
    plural: bool = False,
) -> _LevelTrend:
    changes = w.yearly_changes(values)
    series = (
        w.series(key, label, "usd", values),
        w.series(
            f"{key}_yoy",
            "Year-over-year change",
            "percent_change",
            [c.value if c is not None else None for c in changes],
        ),
    )
    method = f"{definition} {GROWTH_METHOD}" if definition else GROWTH_METHOD
    start, end = values[0], values[-1]
    if start is None or end is None:
        missing = _missing_years(w.labels, values)
        return _LevelTrend(
            _insufficient(
                topic,
                title,
                f"Not enough data: {label.lower()} {'are' if plural else 'is'} not available "
                f"for {missing}.",
                series,
                method,
            ),
            None,
            changes,
        )

    cagr = compound_annual_growth_rate(start, end, w.steps)
    total = absolute_change(end, start)
    total_pct = percent_change(end, start)
    assert total.value is not None  # both inputs are present

    span = f"{text.money(start)} in {w.first_label} to {text.money(end)} in {w.last_label}"
    be = "were" if plural else "was"
    if cagr.value is not None:
        direction = _classify(cagr.value, STABLE_GROWTH_RATE)
        rate = f"a compound annual growth rate of {text.percent(cagr.value)} over {w.steps} years"
        summary = {
            Direction.INCREASING: f"{label} grew from {span}, {rate}.",
            Direction.DECREASING: f"{label} declined from {span}, {rate}.",
            Direction.STABLE: f"{label} {be} roughly flat, moving from {span}, {rate}.",
        }[direction]
    else:
        direction = _sign_direction(total.value)
        verb = {
            Direction.INCREASING: "rose",
            Direction.DECREASING: "fell",
            Direction.STABLE: "were unchanged" if plural else "was unchanged",
        }[direction]
        summary = (
            f"{label} {verb} from {span} ({text.signed_money(total.value)}). "
            "A growth rate is not meaningful because the value was negative in at least one "
            "of those years."
        )

    details = [
        s
        for s in (_consistency_sentence(w, label, values), _range_sentence(w, changes))
        if s is not None
    ]
    missing = _missing_years(w.labels, values)
    if missing:
        details.append(f"{label} {'are' if plural else 'is'} not available for {missing}.")

    finding = TrendFinding(
        topic=topic,
        title=title,
        direction=direction,
        summary=summary,
        details=tuple(details),
        statistics=(
            Statistic("cagr", f"CAGR, {w.first_label}–{w.last_label}", "percent", cagr),
            Statistic("total_change", "Total change", "usd_change", total),
            Statistic("total_change_pct", "Total change (%)", "percent_change", total_pct),
        ),
        series=series,
        method=method,
    )
    return _LevelTrend(finding, cagr, changes)


def _revenue_pace_details(w: _Window, revenue: _LevelTrend) -> list[str]:
    """Compare the latest year's growth with the multi-year compound rate (fact, not forecast)."""
    latest = revenue.changes[-1]
    cagr = revenue.cagr
    if latest is None or latest.value is None or cagr is None or cagr.value is None:
        return []
    # Compare the numbers as displayed, so the sentence never contradicts itself
    # (e.g. "3.7% was below 3.7%").
    shown_latest, shown_cagr = text.percent_value(latest.value), text.percent_value(cagr.value)
    relation = (
        "above"
        if shown_latest > shown_cagr
        else "below"
        if shown_latest < shown_cagr
        else "about the same as"
    )
    return [
        f"Growth in {w.last_label} ({text.signed_percent(latest.value)}) was {relation} "
        f"the {w.steps}-year compound rate ({text.percent(cagr.value)})."
    ]


def _asset_trend(w: _Window, revenue_cagr: MetricResult | None) -> TrendFinding:
    trend = _level_trend(
        w,
        topic="asset_growth",
        title="Asset growth",
        label="Total assets",
        key=LineItem.TOTAL_ASSETS.value,
        values=w.items(LineItem.TOTAL_ASSETS),
        plural=True,
    )
    extra: list[str] = []
    if (
        trend.cagr is not None
        and trend.cagr.value is not None
        and revenue_cagr is not None
        and revenue_cagr.value is not None
    ):
        extra.append(
            f"Over the same years, total assets grew at {text.percent(trend.cagr.value)} a year "
            f"and revenue at {text.percent(revenue_cagr.value)} a year."
        )
    return _with_extra_details(trend.finding, extra)


# ---------------------------------------------------------------------------
# Margins
# ---------------------------------------------------------------------------

_MARGINS = (("gross_margin", "Gross"), ("operating_margin", "Operating"), ("net_margin", "Net"))

MARGIN_METHOD = (
    "Each margin is compared between the first and last year. A change of more than +1 "
    "percentage point is expansion, less than −1 point is contraction, otherwise stable. "
    "The overall direction is mixed when the margins moved differently."
) + ROUNDING_NOTE


def _margin_trend(w: _Window) -> TrendFinding:
    series = tuple(w.series(name, label, "percent", w.metric(name)) for name, label in _MARGINS)
    stats: list[Statistic] = []
    details: list[str] = []
    directions: list[Direction] = []
    labels: list[str] = []
    for name, label in _MARGINS:
        results = w.metric_results(name)
        start, end = results[0], results[-1]
        if start.value is None or end.value is None:
            reason = _unavailable_reason(end if end.value is None else start)
            details.append(f"{label} margin is not available: {reason}")
            continue
        change = absolute_change(end.value, start.value)
        assert change.value is not None
        direction = _classify(change.value, STABLE_MARGIN_CHANGE)
        directions.append(direction)
        labels.append(label.lower())
        verb = {
            Direction.INCREASING: "expanded",
            Direction.DECREASING: "contracted",
            Direction.STABLE: "was stable",
        }[direction]
        details.append(
            f"{label} margin {verb}, from {text.percent(start.value)} to "
            f"{text.percent(end.value)} ({text.points(change.value)})."
        )
        stats.append(Statistic(f"{name}_change", f"{label} margin change", "pp_change", change))

    if not directions:
        return _insufficient(
            "margins",
            "Margins",
            "Not enough data: no profit margin is available for both the first and last year.",
            series,
            MARGIN_METHOD,
        )

    overall = directions[0] if all(d is directions[0] for d in directions) else Direction.MIXED
    between = f"between {w.first_label} and {w.last_label}"
    subject = (
        f"The only available margin, {labels[0]} margin,"
        if len(directions) == 1
        else "Both available margins"
        if len(directions) == 2
        else "All three margins"
    )
    plural_verb = len(directions) > 1
    summary = {
        Direction.INCREASING: f"{subject} expanded {between}.",
        Direction.DECREASING: f"{subject} contracted {between}.",
        Direction.STABLE: (
            f"{subject} {'were' if plural_verb else 'was'} stable (within ±1 point) {between}."
        ),
        Direction.MIXED: f"Margins moved in different directions {between}.",
    }[overall]
    return TrendFinding(
        topic="margins",
        title="Margins",
        direction=overall,
        summary=summary,
        details=tuple(details),
        statistics=tuple(stats),
        series=series,
        method=MARGIN_METHOD,
    )


# ---------------------------------------------------------------------------
# Balances: debt and cash
# ---------------------------------------------------------------------------

BALANCE_METHOD = (
    "Direction comes from the percentage change between the first and last year-end: more "
    "than +5% is increasing, less than −5% is decreasing, otherwise stable. If the starting "
    "balance was zero, the direction follows the sign of the dollar change."
) + ROUNDING_NOTE


def _balance_trend(
    w: _Window,
    *,
    topic: str,
    title: str,
    label: str,
    key: str,
    values: list[Decimal | None],
    extra_series: tuple[Series, ...] = (),
    extra_details: Callable[[], list[str]] = list,
    extra_stats: Callable[[], list[Statistic]] = list,
    definition: str | None = None,
    plural: bool = False,
) -> TrendFinding:
    series = (w.series(key, label, "usd", values), *extra_series)
    method = f"{definition} {BALANCE_METHOD}" if definition else BALANCE_METHOD
    start, end = values[0], values[-1]
    if start is None or end is None:
        missing = _missing_years(w.labels, values)
        return _insufficient(
            topic,
            title,
            f"Not enough data: {label.lower()} {'are' if plural else 'is'} not available "
            f"for {missing}.",
            series,
            method,
        )

    change = absolute_change(end, start)
    change_pct = percent_change(end, start)
    assert change.value is not None
    direction = (
        _classify(change_pct.value, STABLE_BALANCE_CHANGE)
        if change_pct.value is not None
        else _sign_direction(change.value)
    )
    verb = {
        Direction.INCREASING: "increased",
        Direction.DECREASING: "decreased",
        Direction.STABLE: "were roughly unchanged" if plural else "was roughly unchanged",
    }[direction]
    pct = f", {text.signed_percent(change_pct.value)}" if change_pct.value is not None else ""
    summary = (
        f"{label} {verb} from {text.money(start)} at the end of {w.first_label} to "
        f"{text.money(end)} at the end of {w.last_label} ({text.signed_money(change.value)}{pct})."
    )
    return TrendFinding(
        topic=topic,
        title=title,
        direction=direction,
        summary=summary,
        details=tuple(extra_details()),
        statistics=(
            Statistic("change", "Change", "usd_change", change),
            Statistic("change_pct", "Change (%)", "percent_change", change_pct),
            *extra_stats(),
        ),
        series=series,
        method=method,
    )


def _debt_trend(w: _Window) -> TrendFinding:
    de_results = w.metric_results("debt_to_equity")

    def details() -> list[str]:
        out = []
        start, end = de_results[0], de_results[-1]
        if start.value is not None and end.value is not None:
            out.append(
                f"Debt-to-equity went from {text.ratio(start.value)} to {text.ratio(end.value)}."
            )
        else:
            missing = end if end.value is None else start
            out.append(f"Debt-to-equity is not available: {_unavailable_reason(missing)}")
        latest_debt = w.periods[-1].values.get(LineItem.TOTAL_DEBT)
        if latest_debt is not None and latest_debt.derivation:
            out.append(f"Total debt is calculated as {latest_debt.derivation}.")
        return out

    def stats() -> list[Statistic]:
        change = absolute_change(de_results[-1].value, de_results[0].value)
        return [Statistic("debt_to_equity_change", "Debt-to-equity change", "ratio_change", change)]

    return _balance_trend(
        w,
        topic="debt_changes",
        title="Debt",
        label="Total debt",
        key=LineItem.TOTAL_DEBT.value,
        values=w.items(LineItem.TOTAL_DEBT),
        extra_series=(
            w.series("debt_to_equity", "Debt-to-equity", "ratio", w.metric("debt_to_equity")),
        ),
        extra_details=details,
        extra_stats=stats,
        definition="Total debt is borrowings only (not all liabilities).",
    )


def _cash_trend(w: _Window) -> TrendFinding:
    return _balance_trend(
        w,
        topic="cash_changes",
        title="Cash",
        label="Cash and cash equivalents",
        key=LineItem.CASH_AND_EQUIVALENTS.value,
        values=w.items(LineItem.CASH_AND_EQUIVALENTS),
        plural=True,
        definition="Cash excludes short-term investments, which are reported separately.",
    )


# ---------------------------------------------------------------------------
# Working capital
# ---------------------------------------------------------------------------

WORKING_CAPITAL_METHOD = (
    "Working capital = current assets − current liabilities, calculated for each year-end. "
    "A change smaller than 1% of the last year's revenue counts as stable; otherwise the "
    "direction follows the sign of the change. Without revenue, any change counts."
) + ROUNDING_NOTE


def _working_capital_trend(w: _Window) -> TrendFinding:
    results = [
        working_capital(p.get(LineItem.CURRENT_ASSETS), p.get(LineItem.CURRENT_LIABILITIES))
        for p in w.periods
    ]
    values = [r.value for r in results]
    current_ratios = w.metric_results("current_ratio")
    series = (
        w.series("working_capital", "Working capital", "usd", values),
        w.series("current_ratio", "Current ratio", "ratio", [r.value for r in current_ratios]),
    )
    start, end = values[0], values[-1]
    if start is None or end is None:
        missing = _missing_years(w.labels, values)
        return _insufficient(
            "working_capital",
            "Working capital",
            "Not enough data: current assets or current liabilities are not reported for "
            f"{missing}. "
            "(Banks and insurers usually don't split their balance sheet into current and "
            "non-current items.)",
            series,
            WORKING_CAPITAL_METHOD,
        )

    change = absolute_change(end, start)
    assert change.value is not None
    revenue = w.periods[-1].get(LineItem.REVENUE)
    if revenue is not None and revenue > 0:
        band = revenue * STABLE_WORKING_CAPITAL_SHARE
        direction = _classify(change.value, band)
    else:
        direction = _sign_direction(change.value)
    verb = {
        Direction.INCREASING: "increased",
        Direction.DECREASING: "decreased",
        Direction.STABLE: "was roughly unchanged",
    }[direction]
    summary = (
        f"Working capital {verb}, from {text.money(start)} at the end of {w.first_label} to "
        f"{text.money(end)} at the end of {w.last_label} ({text.signed_money(change.value)})."
    )

    details = []
    if current_ratios[0].value is not None and current_ratios[-1].value is not None:
        details.append(
            f"The current ratio went from {text.ratio(current_ratios[0].value)} to "
            f"{text.ratio(current_ratios[-1].value)}."
        )
    negative_years = [
        lbl for lbl, v in zip(w.labels, values, strict=True) if v is not None and v < 0
    ]
    if negative_years:
        details.append(
            f"Working capital was negative in {len(negative_years)} of {len(values)} years "
            f"({', '.join(negative_years)}), meaning current liabilities exceeded current assets."
        )

    return TrendFinding(
        topic="working_capital",
        title="Working capital",
        direction=direction,
        summary=summary,
        details=tuple(details),
        statistics=(
            Statistic("start", f"Working capital, {w.first_label}", "usd", results[0]),
            Statistic("end", f"Working capital, {w.last_label}", "usd", results[-1]),
            Statistic("change", "Change", "usd_change", change),
            Statistic(
                "current_ratio_change",
                "Current ratio change",
                "ratio_change",
                absolute_change(current_ratios[-1].value, current_ratios[0].value),
            ),
        ),
        series=series,
        method=WORKING_CAPITAL_METHOD,
    )
