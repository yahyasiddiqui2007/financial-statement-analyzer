import type { Period } from "../api/types";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** Split "2024-09-28" ourselves: `new Date()` would shift it by the viewer's time zone. */
function parts(isoDate: string): { year: number; month: string; day: number } {
  const [y, m, d] = isoDate.split("-").map(Number);
  return { year: y ?? 0, month: MONTHS[(m ?? 1) - 1] ?? "", day: d ?? 0 };
}

/**
 * Column header for a fiscal year. Uses the company's own label when the
 * filings provide one ("FY2024"); otherwise the end date ("YE Sep 2008"),
 * never a guessed fiscal year.
 */
export function shortPeriodLabel(period: Period): string {
  if (period.fiscal_year !== null) return `FY${period.fiscal_year}`;
  const { year, month } = parts(period.end);
  return `YE ${month} ${year}`;
}

/** "Sep 28, 2024" */
export function formatDate(isoDate: string): string {
  const { year, month, day } = parts(isoDate);
  return `${month} ${day}, ${year}`;
}

/** Fiscal year end as month and day, e.g. "late September" companies show "Sep 27". */
export function fiscalYearEnd(period: Period): string {
  const { month, day } = parts(period.end);
  return `${month} ${day}`;
}

export type YearRange = 5 | 10 | "all";

/** Indexes of the periods to show (oldest first), e.g. the last 5 of 19. */
export function visibleIndexes(periodCount: number, range: YearRange): number[] {
  const count = range === "all" ? periodCount : Math.min(range, periodCount);
  return Array.from({ length: count }, (_, i) => periodCount - count + i);
}
