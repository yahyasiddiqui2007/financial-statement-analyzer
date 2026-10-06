// Whether a change is good news, bad news, or neither. Colors always come
// with an arrow and a signed number, so meaning never depends on color alone.

export type Tone = "positive" | "negative" | "neutral";

/** Line items where an increase is generally favorable. */
const UP_IS_GOOD = new Set([
  "revenue",
  "gross_profit",
  "operating_income",
  "net_income",
  "operating_cash_flow",
  "total_equity",
  "cash_and_equivalents",
]);

/** Line items where an increase is generally unfavorable. */
const UP_IS_BAD = new Set([
  "cost_of_revenue",
  "total_liabilities",
  "current_liabilities",
  "total_debt",
  "debt_current",
  "long_term_debt_current",
  "long_term_debt_noncurrent",
  "commercial_paper",
  "short_term_borrowings",
]);

const METRIC_UP_IS_GOOD = new Set([
  "revenue_growth",
  "gross_margin",
  "operating_margin",
  "net_margin",
  "return_on_assets",
  "return_on_equity",
  "current_ratio",
  "quick_ratio",
  "free_cash_flow",
  "fcf_margin",
]);
const METRIC_UP_IS_BAD = new Set(["debt_to_equity"]);

function toneFor(dir: -1 | 0 | 1 | null, good: boolean, bad: boolean): Tone {
  if (dir === null || dir === 0) return "neutral";
  if (good) return dir > 0 ? "positive" : "negative";
  if (bad) return dir > 0 ? "negative" : "positive";
  return "neutral";
}

export function lineItemTone(item: string, dir: -1 | 0 | 1 | null): Tone {
  return toneFor(dir, UP_IS_GOOD.has(item), UP_IS_BAD.has(item));
}

export function metricTone(name: string, dir: -1 | 0 | 1 | null): Tone {
  return toneFor(dir, METRIC_UP_IS_GOOD.has(name), METRIC_UP_IS_BAD.has(name));
}
