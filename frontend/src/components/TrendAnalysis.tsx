import { useState } from "react";
import type {
  TrendDirection,
  TrendFinding,
  TrendReport,
  TrendStatistic,
  TrendValueFormat,
} from "../api/types";
import { formatTrendValue, formatUsdMillions, formatPercent, formatRatio } from "../lib/format";

// Directions are shown in neutral ink: the analysis describes what changed,
// not whether that is good or bad for anyone holding the stock.
const DIRECTION: Record<TrendDirection, { glyph: string; label: string }> = {
  increasing: { glyph: "↗", label: "Increasing" },
  decreasing: { glyph: "↘", label: "Decreasing" },
  stable: { glyph: "→", label: "Stable" },
  mixed: { glyph: "⇅", label: "Mixed" },
  insufficient_data: { glyph: "–", label: "Insufficient data" },
};

/** How a statistic's inputs are displayed (e.g. a CAGR's inputs are dollar amounts). */
const INPUT_FORMAT: Record<TrendValueFormat, (v: string | null) => string> = {
  usd: (v) => formatUsdMillions(v),
  usd_change: (v) => formatUsdMillions(v),
  percent: (v) => formatUsdMillions(v),
  percent_change: (v) => formatUsdMillions(v),
  pp_change: (v) => formatPercent(v),
  ratio: (v) => formatRatio(v),
  ratio_change: (v) => formatRatio(v),
};

function inputText(key: string, value: string | null, format: TrendValueFormat): string {
  const label = key.replace(/_/g, " ");
  return `${label} ${key === "years" ? (value ?? "—") : INPUT_FORMAT[format](value)}`;
}

export function TrendAnalysis({ reports }: { reports: TrendReport[] }) {
  const [selected, setSelected] = useState(reports.length - 1); // longest window first
  const report = reports[Math.min(selected, reports.length - 1)];
  if (!report) return null;

  return (
    <section className="trends" aria-labelledby="trends-heading">
      <div className="section-head">
        <h2 id="trends-heading" className="section-title">
          Trend analysis
          {report.start_label && report.end_label && (
            <span className="section-title__range">
              {" "}
              · {report.start_label} – {report.end_label}
            </span>
          )}
        </h2>
        {reports.length > 1 && (
          <div className="range" role="group" aria-label="Trend window">
            {reports.map((r, i) => (
              <button
                key={r.years}
                type="button"
                className="range__option"
                aria-pressed={i === selected}
                onClick={() => setSelected(i)}
              >
                {r.years}Y
              </button>
            ))}
          </div>
        )}
      </div>
      <p className="section-note trends__intro">
        Descriptive findings calculated from the reported figures. Each one shows the yearly values,
        the statistics behind it and the rule used, so every conclusion can be checked. Not
        investment advice.
      </p>
      {report.notes.map((note) => (
        <p key={note} className="trends__note" role="note">
          {note}
        </p>
      ))}
      <ul className="findings">
        {report.findings.map((f) => (
          <FindingCard key={f.topic} finding={f} />
        ))}
      </ul>
    </section>
  );
}

function FindingCard({ finding }: { finding: TrendFinding }) {
  const dir = DIRECTION[finding.direction];
  const headingId = `finding-${finding.topic}`;
  return (
    <li className="panel finding" aria-labelledby={headingId}>
      <div className="finding__head">
        <h3 id={headingId} className="finding__title">
          {finding.title}
        </h3>
        <span className={`direction direction--${finding.direction}`}>
          <span aria-hidden="true">{dir.glyph}</span> {dir.label}
        </span>
      </div>
      <p className="finding__summary">{finding.summary}</p>
      {finding.details.length > 0 && (
        <ul className="finding__details">
          {finding.details.map((d) => (
            <li key={d}>{d}</li>
          ))}
        </ul>
      )}

      {finding.series.length > 0 && <EvidenceTable finding={finding} />}

      {finding.statistics.length > 0 && (
        <dl className="stats">
          {finding.statistics.map((s) => (
            <StatisticRow key={s.label} stat={s} />
          ))}
        </dl>
      )}

      <details className="finding__method">
        <summary>How this was determined</summary>
        <p>{finding.method}</p>
      </details>
    </li>
  );
}

function EvidenceTable({ finding }: { finding: TrendFinding }) {
  const columns = finding.series[0]!.points;
  return (
    <div className="table-scroll finding__evidence">
      <table className="fin-table fin-table--compact">
        <caption className="visually-hidden">Yearly values behind the {finding.title} finding</caption>
        <thead>
          <tr>
            <th scope="col" className="fin-table__stub">
              Year
            </th>
            {columns.map((p) => (
              <th key={p.end} scope="col" className="num">
                {p.label.replace("the year ended ", "YE ")}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {finding.series.map((series) => (
            <tr key={series.key}>
              <th scope="row" className="fin-table__stub">
                {series.label}
              </th>
              {series.points.map((p) => (
                <td key={p.end} className="num">
                  {p.value === null ? (
                    <span className="cell__missing">—</span>
                  ) : (
                    formatTrendValue(p.value, series.format)
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function StatisticRow({ stat }: { stat: TrendStatistic }) {
  const inputs = Object.entries(stat.inputs)
    .map(([k, v]) => inputText(k, v, stat.format))
    .join(" · ");
  return (
    <div className="stats__row">
      <dt>{stat.label}</dt>
      <dd>
        <span className="stats__value">
          {stat.value !== null ? formatTrendValue(stat.value, stat.format) : "n/a"}
        </span>
        <span className="stats__formula">
          {stat.value !== null ? `${stat.formula} · ${inputs}` : stat.reason}
        </span>
      </dd>
    </div>
  );
}
