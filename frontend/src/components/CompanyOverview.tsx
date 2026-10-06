import type { Financials } from "../api/types";
import { cellAt } from "../lib/data";
import { direction, formatCompactUsd, formatPercentChange, formatTimestamp } from "../lib/format";
import { fiscalYearEnd, formatDate, shortPeriodLabel } from "../lib/periods";
import { lineItemTone } from "../lib/tone";
import { ChangeBadge } from "./ChangeBadge";

const HEADLINES = [
  { item: "revenue", label: "Revenue" },
  { item: "net_income", label: "Net income" },
  { item: "operating_cash_flow", label: "Operating cash flow" },
  { item: "total_assets", label: "Total assets" },
];

export function CompanyOverview({ data }: { data: Financials }) {
  const { company, periods } = data;
  const latestIndex = periods.length - 1;
  const latest = periods[latestIndex]!;
  const first = periods[0]!;
  const priorLabel = latestIndex > 0 ? shortPeriodLabel(periods[latestIndex - 1]!) : null;

  return (
    <section className="panel overview" aria-labelledby="company-name">
      <div className="overview__identity">
        <div>
          <p className="eyebrow">
            <span className="ticker-badge">{company.ticker}</span>
            <span>CIK {company.cik}</span>
          </p>
          <h1 id="company-name" className="overview__name">
            {company.name}
          </h1>
        </div>
        <dl className="facts">
          <div>
            <dt>Latest fiscal year</dt>
            <dd>
              {shortPeriodLabel(latest)} · ended {formatDate(latest.end)}
            </dd>
          </div>
          <div>
            <dt>Fiscal year ends</dt>
            <dd>{fiscalYearEnd(latest)}</dd>
          </div>
          <div>
            <dt>History</dt>
            <dd>
              {periods.length} years since {formatDate(first.end)}
            </dd>
          </div>
          <div>
            <dt>Source</dt>
            <dd>
              <a href={company.edgar_url} target="_blank" rel="noreferrer">
                SEC 10-K filings
              </a>
              {" · "}
              <a href={data.source.url} target="_blank" rel="noreferrer">
                raw data
              </a>
            </dd>
          </div>
        </dl>
      </div>

      <div className="tiles">
        {HEADLINES.map(({ item, label }) => {
          const cell = cellAt(data, item, latestIndex);
          const change = cell?.change;
          const dir = direction(change?.value ?? null, "change");
          return (
            <div className="tile" key={item}>
              <p className="tile__label">
                {label} · {shortPeriodLabel(latest)}
              </p>
              <p className="tile__value">{formatCompactUsd(cell?.value ?? null)}</p>
              {change && priorLabel ? (
                <ChangeBadge
                  text={
                    change.value !== null
                      ? `${formatPercentChange(change.value)} vs ${priorLabel}`
                      : `n/a vs ${priorLabel}`
                  }
                  dir={dir}
                  tone={lineItemTone(item, dir)}
                  title={change.reason ?? undefined}
                />
              ) : (
                <span className="change change--na">No prior year</span>
              )}
            </div>
          );
        })}
      </div>

      <p className="overview__retrieved">
        Data retrieved {formatTimestamp(data.source.retrieved_at)} from {data.source.provider}.
      </p>
    </section>
  );
}
