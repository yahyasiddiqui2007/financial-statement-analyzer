import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Financials } from "../api/types";
import type { ChartColors } from "../hooks/useChartColors";
import { chartRows, type ChartRow, type SeriesSpec } from "../lib/data";
import { formatAxisUsd, formatCompactUsd, formatPercent, MISSING } from "../lib/format";

type ValueFormat = "usd" | "percent";

interface ChartSpec {
  id: string;
  title: string;
  subtitle: string;
  kind: "bar" | "line";
  format: ValueFormat;
  series: SeriesSpec[]; // at most 3: the validated palette slots
}

const CHARTS: ChartSpec[] = [
  {
    id: "revenue-income",
    title: "Revenue and net income",
    subtitle: "USD, fiscal years",
    kind: "bar",
    format: "usd",
    series: [
      { key: "revenue", label: "Revenue", source: "item" },
      { key: "net_income", label: "Net income", source: "item" },
    ],
  },
  {
    id: "margins",
    title: "Profit margins",
    subtitle: "Share of revenue",
    kind: "line",
    format: "percent",
    series: [
      { key: "gross_margin", label: "Gross", source: "metric" },
      { key: "operating_margin", label: "Operating", source: "metric" },
      { key: "net_margin", label: "Net", source: "metric" },
    ],
  },
  {
    id: "cash-flow",
    title: "Operating and free cash flow",
    subtitle: "USD · free cash flow = operating cash flow − capital expenditures",
    kind: "bar",
    format: "usd",
    series: [
      { key: "operating_cash_flow", label: "Operating cash flow", source: "item" },
      { key: "free_cash_flow", label: "Free cash flow", source: "metric" },
    ],
  },
  {
    id: "balance-sheet",
    title: "Assets, liabilities and equity",
    subtitle: "USD, at fiscal year end",
    kind: "line",
    format: "usd",
    series: [
      { key: "total_assets", label: "Total assets", source: "item" },
      { key: "total_liabilities", label: "Total liabilities", source: "item" },
      { key: "total_equity", label: "Shareholders' equity", source: "item" },
    ],
  },
];

// Axis ticks are rounded steps; tooltips show the value at full display precision.
const axisFormatters: Record<ValueFormat, (v: number) => string> = {
  usd: formatAxisUsd,
  percent: (v) => formatPercent(v, 0),
};
const valueFormatters: Record<ValueFormat, (v: number) => string> = {
  usd: (v) => formatCompactUsd(v),
  percent: (v) => formatPercent(v, 1),
};

export function FinancialCharts({
  data,
  indexes,
  colors,
}: {
  data: Financials;
  indexes: number[];
  colors: ChartColors;
}) {
  return (
    <section aria-labelledby="charts-heading">
      <h2 id="charts-heading" className="section-title">
        Historical trends
      </h2>
      <div className="charts">
        {CHARTS.map((spec) => (
          <ChartCard key={spec.id} spec={spec} rows={chartRows(data, indexes, spec.series)} colors={colors} />
        ))}
      </div>
      <p className="section-note">
        Exact values for every point are in the statement and ratio tables below.
      </p>
    </section>
  );
}

function ChartCard({ spec, rows, colors }: { spec: ChartSpec; rows: ChartRow[]; colors: ChartColors }) {
  const hasData = rows.some((row) => spec.series.some((s) => typeof row[s.key] === "number"));
  const format = valueFormatters[spec.format];

  const axes = (
    <>
      <CartesianGrid vertical={false} stroke={colors.grid} />
      <XAxis
        dataKey="period"
        tick={{ fill: colors.tick, fontSize: 11 }}
        tickLine={false}
        axisLine={{ stroke: colors.axis }}
        interval="preserveStartEnd"
        minTickGap={8}
      />
      <YAxis
        tickFormatter={axisFormatters[spec.format]}
        tick={{ fill: colors.tick, fontSize: 11 }}
        tickLine={false}
        axisLine={false}
        width={64}
      />
    </>
  );
  const tooltip = (
    <Tooltip
      cursor={
        spec.kind === "line" ? { stroke: colors.axis, strokeWidth: 1 } : { fill: colors.grid, opacity: 0.5 }
      }
      isAnimationActive={false}
      content={(props) => (
        <ChartTooltip
          active={props.active}
          label={props.label}
          series={spec.series}
          row={props.payload?.[0]?.payload as ChartRow | undefined}
          colors={colors.series}
          format={format}
        />
      )}
    />
  );

  return (
    <figure className="panel chart">
      <figcaption>
        <h3 className="chart__title">{spec.title}</h3>
        <p className="chart__subtitle">{spec.subtitle}</p>
        <ul className="legend">
          {spec.series.map((s, i) => {
            const reported = rows.some((row) => typeof row[s.key] === "number");
            return (
              <li key={s.key} className={reported ? undefined : "legend__item--missing"}>
                <span
                  className={`legend__key legend__key--${spec.kind}`}
                  style={{ background: colors.series[i] }}
                  aria-hidden="true"
                />
                {s.label}
                {!reported && " (not reported)"}
              </li>
            );
          })}
        </ul>
      </figcaption>
      {hasData ? (
        <div className="chart__plot">
          <ResponsiveContainer width="100%" height="100%">
            {spec.kind === "bar" ? (
              <BarChart data={rows} barGap={2} barCategoryGap="25%" margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                {axes}
                {tooltip}
                {spec.series.map((s, i) => (
                  <Bar
                    key={s.key}
                    dataKey={s.key}
                    name={s.label}
                    fill={colors.series[i]}
                    radius={[4, 4, 0, 0]}
                    maxBarSize={24}
                    isAnimationActive={false}
                  />
                ))}
              </BarChart>
            ) : (
              <LineChart data={rows} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                {axes}
                {tooltip}
                {spec.series.map((s, i) => (
                  <Line
                    key={s.key}
                    dataKey={s.key}
                    name={s.label}
                    type="linear"
                    stroke={colors.series[i]}
                    strokeWidth={2}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    dot={{ r: 4, fill: colors.series[i], stroke: colors.surface, strokeWidth: 2 }}
                    activeDot={{ r: 5, fill: colors.series[i], stroke: colors.surface, strokeWidth: 2 }}
                    connectNulls={false}
                    isAnimationActive={false}
                  />
                ))}
              </LineChart>
            )}
          </ResponsiveContainer>
        </div>
      ) : (
        <p className="chart__empty">Not reported for the selected years.</p>
      )}
    </figure>
  );
}

function ChartTooltip({
  active,
  label,
  row,
  series,
  colors,
  format,
}: {
  active?: boolean;
  label?: string | number;
  row: ChartRow | undefined;
  series: SeriesSpec[];
  colors: string[];
  format: (v: number) => string;
}) {
  if (!active || !row) return null;
  return (
    <div className="tooltip">
      <p className="tooltip__label">{label}</p>
      <ul>
        {series.map((s, i) => {
          const value = row[s.key];
          return (
            <li key={s.key}>
              <span className="tooltip__key" style={{ background: colors[i] }} aria-hidden="true" />
              <strong className="tooltip__value">{typeof value === "number" ? format(value) : MISSING}</strong>
              <span className="tooltip__name">{s.label}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
