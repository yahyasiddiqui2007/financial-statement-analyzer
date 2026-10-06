// Read-only lookups into the API response. Nothing here calculates new
// financial figures; it only finds values the pipeline already produced.

import type { Cell, Financials, Metric, Row } from "../api/types";
import { toNumber } from "./format";
import { shortPeriodLabel } from "./periods";

export function findRow(data: Financials, item: string): Row | undefined {
  for (const statement of data.statements) {
    const row = statement.rows.find((r) => r.item === item);
    if (row) return row;
  }
  return undefined;
}

export function findMetric(data: Financials, name: string): Metric | undefined {
  return data.metrics.find((m) => m.name === name);
}

export function cellAt(data: Financials, item: string, index: number): Cell | undefined {
  return findRow(data, item)?.cells[index];
}

/** A row with no reported value in any of the given periods. */
export function isEmptyRow(row: Row, indexes: number[]): boolean {
  return indexes.every((i) => row.cells[i]?.value == null);
}

export interface SeriesSpec {
  key: string; // line item or metric name
  label: string;
  source: "item" | "metric";
}

export type ChartRow = { period: string } & Record<string, number | null | string>;

/**
 * Chart-ready rows: one per visible period, holding the pipeline's values
 * (null stays null, so the chart shows a gap instead of a fake zero).
 */
export function chartRows(data: Financials, indexes: number[], series: SeriesSpec[]): ChartRow[] {
  return indexes.map((i) => {
    const period = data.periods[i];
    const row: ChartRow = { period: period ? shortPeriodLabel(period) : "" };
    for (const s of series) {
      const raw =
        s.source === "item"
          ? cellAt(data, s.key, i)?.value
          : findMetric(data, s.key)?.values[i]?.value;
      row[s.key] = toNumber(raw);
    }
    return row;
  });
}
