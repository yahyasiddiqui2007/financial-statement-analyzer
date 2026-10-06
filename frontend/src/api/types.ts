// TypeScript mirror of the backend's response schema (src/fsa/api/schemas.py).
// Keep the two in sync: the backend test `test_frontend_fixture_matches_api`
// fails if the example response used by frontend tests drifts from the API.

/** Exact decimal values arrive as strings, e.g. "391035000000" or "0.2022". */
export type DecimalString = string;

export type MetricStatus =
  | "ok"
  | "missing_input"
  | "invalid_input"
  | "zero_denominator"
  | "not_meaningful";

export type MetricFormat = "percent" | "ratio" | "usd";

export interface Company {
  cik: string;
  ticker: string;
  name: string;
  edgar_url: string;
}

export interface DataSource {
  provider: string;
  url: string;
  retrieved_at: string; // ISO 8601 timestamp
}

export interface Period {
  start: string; // ISO date
  end: string;
  fiscal_year: number | null;
  label: string;
  has_prior: boolean;
}

export interface SourceFact {
  tag: string;
  accession_number: string;
  form: string;
  filed: string;
  url: string;
}

export interface Change {
  value: DecimalString | null;
  status: MetricStatus;
  reason: string | null;
}

export interface Cell {
  value: DecimalString | null;
  derived: boolean;
  derivation: string | null;
  restated: boolean;
  sources: SourceFact[];
  change: Change | null;
}

export interface Row {
  item: string;
  label: string;
  cells: Cell[]; // aligned with Financials.periods
}

export interface StatementData {
  id: "income_statement" | "balance_sheet" | "cash_flow";
  title: string;
  rows: Row[];
}

export interface MetricValue {
  value: DecimalString | null;
  status: MetricStatus;
  reason: string | null;
  difference: DecimalString | null;
  inputs: Record<string, DecimalString | null>;
}

export interface Metric {
  name: string;
  label: string;
  format: MetricFormat;
  formula: string;
  values: MetricValue[]; // aligned with Financials.periods
}

export type TrendValueFormat =
  | "usd"
  | "usd_change"
  | "percent"
  | "percent_change"
  | "pp_change"
  | "ratio"
  | "ratio_change";

export type TrendDirection = "increasing" | "decreasing" | "stable" | "mixed" | "insufficient_data";

export interface TrendStatistic {
  key: string;
  label: string;
  format: TrendValueFormat;
  value: DecimalString | null;
  status: MetricStatus;
  reason: string | null;
  formula: string;
  inputs: Record<string, DecimalString | null>;
}

export interface TrendSeries {
  key: string;
  label: string;
  format: TrendValueFormat;
  points: { label: string; end: string; value: DecimalString | null }[];
}

export interface TrendFinding {
  topic: string;
  title: string;
  direction: TrendDirection;
  summary: string;
  details: string[];
  statistics: TrendStatistic[];
  series: TrendSeries[];
  method: string;
}

export interface TrendReport {
  requested_years: number;
  years: number;
  start_label: string | null;
  end_label: string | null;
  findings: TrendFinding[];
  notes: string[];
}

export interface Financials {
  company: Company;
  source: DataSource;
  periods: Period[]; // oldest first
  statements: StatementData[];
  metrics: Metric[];
  trends: TrendReport[];
  warnings: string[];
}

export type AISection = "strengths" | "concerns" | "trends" | "questions";

export interface AIEvidence {
  id: string;
  kind: "line_item" | "metric" | "trend" | "trend_statistic";
  label: string;
  period: string | null;
  value: string;
  note: string | null;
}

export interface AIClaim {
  statement: string;
  evidence: AIEvidence[];
}

export interface AIAnalysis {
  ticker: string;
  model: string;
  generated_at: string;
  disclaimer: string;
  evidence_count: number;
  strengths: AIClaim[];
  concerns: AIClaim[];
  trends: AIClaim[];
  questions: AIClaim[];
  rejected: { section: AISection; statement: string; reason: string }[];
}

export interface ApiErrorBody {
  error: { code: string; message: string };
}
