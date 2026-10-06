"""Command-line entry point: `python -m fsa AAPL`.

A plain-text preview of the data until the web frontend exists.
"""

from __future__ import annotations

import argparse
import sys
from decimal import Decimal

from fsa.analysis import annual_metrics
from fsa.analytics import MetricResult
from fsa.ingestion import (
    DEFINITIONS,
    AnnualPeriod,
    IngestionError,
    LineItem,
    SecClient,
    Statement,
    load_financial_history,
)

MILLION = Decimal(1_000_000)
PERCENT_METRICS = {
    "revenue_growth",
    "gross_margin",
    "operating_margin",
    "net_margin",
    "return_on_assets",
    "return_on_equity",
    "fcf_margin",
}
DOLLAR_METRICS = {"free_cash_flow"}
COLUMN_WIDTH = 14


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Show normalized SEC financial data.")
    parser.add_argument("ticker", help="Stock ticker, e.g. AAPL")
    parser.add_argument("--years", type=int, default=5, help="How many recent years to show")
    args = parser.parse_args(argv)

    try:
        with SecClient.from_env() as client:
            history = load_financial_history(args.ticker, client)
    except (IngestionError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    periods = list(history.periods[-args.years :])
    company = history.company
    print(f"\n{company.name} ({company.ticker}), CIK {company.cik}")
    print("Amounts in USD millions.  * = derived   † = restated in a later filing\n")

    for statement in Statement:
        _print_header(statement.value.replace("_", " ").title(), periods)
        for definition in DEFINITIONS.values():
            if definition.statement is statement:
                cells = [_money_cell(p, definition.item) for p in periods]
                print(f"{definition.label:<36}" + "".join(cells))
        print()

    _print_header("Metrics", periods)
    metrics_by_period = [annual_metrics(history, p) for p in periods]
    for name in metrics_by_period[0]:
        cells = [_metric_cell(m[name]) for m in metrics_by_period]
        print(f"{name:<36}" + "".join(cells))

    if history.warnings:
        print("\nData notes:")
        for warning in history.warnings:
            print(f"  - {warning}")
    return 0


def _print_header(title: str, periods: list[AnnualPeriod]) -> None:
    print(f"{title:<36}" + "".join(f"{p.end.isoformat():>{COLUMN_WIDTH}}" for p in periods))
    print("-" * (36 + COLUMN_WIDTH * len(periods)))


def _money_cell(period: AnnualPeriod, item: LineItem) -> str:
    line = period.values.get(item)
    if line is None:
        return f"{'—':>{COLUMN_WIDTH}}"
    marks = ("*" if line.is_derived else "") + ("†" if line.restated else "")
    return f"{line.value / MILLION:>{COLUMN_WIDTH - 2},.0f}{marks:<2}"


def _metric_cell(result: MetricResult) -> str:
    if result.value is None:
        return f"{'n/a':>{COLUMN_WIDTH}}"
    if result.name in PERCENT_METRICS:
        text = f"{result.value * 100:.1f}%"
    elif result.name in DOLLAR_METRICS:
        text = f"{result.value / MILLION:,.0f}"
    else:
        text = f"{result.value:.2f}x"
    return f"{text:>{COLUMN_WIDTH}}"


if __name__ == "__main__":
    raise SystemExit(main())
