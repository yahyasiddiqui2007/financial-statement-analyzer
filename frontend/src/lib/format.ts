// Display formatting. These functions only change how a pipeline value LOOKS
// (units, rounding, signs); they never compute new financial figures.

import type { DecimalString, MetricFormat, TrendValueFormat } from "../api/types";

export const MISSING = "—";
const MINUS = "−"; // typographic minus sign, same width as "+"

/** Parse an exact decimal string for display. Null stays null (never zero). */
export function toNumber(value: DecimalString | null | undefined): number | null {
  if (value === null || value === undefined) return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function grouped(n: number, digits: number): string {
  return n.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

/** Avoid showing "-0.0" when a tiny negative rounds to zero. */
function signed(n: number, digits: number): { sign: "" | "+" | typeof MINUS; text: string } {
  const text = grouped(Math.abs(n), digits);
  const roundsToZero = Number(text.replace(/,/g, "")) === 0;
  if (roundsToZero) return { sign: "", text };
  return { sign: n < 0 ? MINUS : "+", text };
}

/**
 * Statement-table style: USD millions, negatives in parentheses (accounting convention).
 * 391035000000 → "391,035"; -22354000000 → "(22,354)".
 */
export function formatMillions(value: DecimalString | null): string {
  const n = toNumber(value);
  if (n === null) return MISSING;
  const millions = n / 1e6;
  const abs = Math.abs(millions);
  const digits = abs === 0 || abs >= 100 ? 0 : abs >= 1 ? 1 : 2;
  const text = grouped(abs, digits);
  return millions < 0 && Number(text.replace(/,/g, "")) !== 0 ? `(${text})` : text;
}

/** Headline style: "$391.0B", "$512.3M", "−$1.2B". */
export function formatCompactUsd(value: DecimalString | number | null): string {
  const n = typeof value === "number" ? value : toNumber(value);
  if (n === null) return MISSING;
  const text = compactDollars(Math.abs(n), 1);
  return n < 0 ? `${MINUS}${text}` : text;
}

/** Chart-axis style: whole steps drop the decimal ("$600B", "$0"), others keep one ("$1.5T"). */
export function formatAxisUsd(n: number): string {
  const abs = Math.abs(n);
  const text = compactDollars(abs, 1).replace(/\.0(?=[KMBT]?$)/, "");
  return n < 0 ? `${MINUS}${text}` : text;
}

function compactDollars(abs: number, digits: number): string {
  if (abs < 1e3) return `$${grouped(abs, 0)}`;
  const [divisor, suffix] =
    abs >= 1e12 ? [1e12, "T"] : abs >= 1e9 ? [1e9, "B"] : abs >= 1e6 ? [1e6, "M"] : [1e3, "K"];
  return `$${grouped(abs / divisor, digits)}${suffix}`;
}

/** 0.4693 → "46.9%". */
export function formatPercent(value: DecimalString | number | null, digits = 1): string {
  const n = typeof value === "number" ? value : toNumber(value);
  if (n === null) return MISSING;
  const { sign, text } = signed(n * 100, digits);
  return `${sign === MINUS ? MINUS : ""}${text}%`;
}

/** 0.8932 → "0.89x". */
export function formatRatio(value: DecimalString | number | null): string {
  const n = typeof value === "number" ? value : toNumber(value);
  if (n === null) return MISSING;
  const { sign, text } = signed(n, 2);
  return `${sign === MINUS ? MINUS : ""}${text}x`;
}

export function formatMetric(value: DecimalString | null, format: MetricFormat): string {
  switch (format) {
    case "percent":
      return formatPercent(value);
    case "ratio":
      return formatRatio(value);
    case "usd":
      return formatCompactUsd(value);
  }
}

/** Year-over-year percent change: 0.064 → "+6.4%". */
export function formatPercentChange(value: DecimalString | null): string {
  const n = toNumber(value);
  if (n === null) return MISSING;
  const { sign, text } = signed(n * 100, 1);
  return `${sign}${text}%`;
}

/**
 * Change in a metric between two years, in the metric's own unit:
 * margins in percentage points ("+0.7 pp"), ratios in x ("+0.12x"), dollars compact.
 */
export function formatDifference(value: DecimalString | null, format: MetricFormat): string {
  const n = toNumber(value);
  if (n === null) return MISSING;
  if (format === "percent") {
    const { sign, text } = signed(n * 100, 1);
    return `${sign}${text} pp`;
  }
  if (format === "ratio") {
    const { sign, text } = signed(n, 2);
    return `${sign}${text}x`;
  }
  const compact = formatCompactUsd(Math.abs(n));
  return n === 0 ? compact : `${n < 0 ? MINUS : "+"}${compact}`;
}

/** Direction of a change after display rounding, for arrows and colors. */
export function direction(value: DecimalString | null, format: MetricFormat | "change"): -1 | 0 | 1 | null {
  const n = toNumber(value);
  if (n === null) return null;
  const scaled = format === "percent" || format === "change" ? n * 100 : n;
  const digits = format === "ratio" ? 2 : 1;
  if (Number(Math.abs(scaled).toFixed(digits)) === 0) return 0;
  return n > 0 ? 1 : -1;
}

/** Human-readable timestamp: "Oct 5, 2026, 10:12 PM". */
export function formatTimestamp(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? iso
    : date.toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" });
}

/**
 * Trend style: USD millions with a unit, matching the sentences the backend writes
 * ("$416,161M", "−$17,674M"). Under $100M keeps one decimal ("$12.5M").
 */
export function formatUsdMillions(value: DecimalString | null, withSign = false): string {
  const n = toNumber(value);
  if (n === null) return MISSING;
  const millions = n / 1e6;
  const digits = Math.abs(millions) >= 100 ? 0 : 1;
  const { sign, text } = signed(millions, digits);
  const prefix = sign === MINUS ? MINUS : withSign ? sign : "";
  return `${prefix}$${text}M`;
}

export function formatTrendValue(value: DecimalString | null, format: TrendValueFormat): string {
  switch (format) {
    case "usd":
      return formatUsdMillions(value);
    case "usd_change":
      return formatUsdMillions(value, true);
    case "percent":
      return formatPercent(value);
    case "percent_change":
      return formatPercentChange(value);
    case "pp_change":
      return formatDifference(value, "percent");
    case "ratio":
      return formatRatio(value);
    case "ratio_change":
      return formatDifference(value, "ratio");
  }
}
