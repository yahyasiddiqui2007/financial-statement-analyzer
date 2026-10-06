import type { Financials, MetricStatus } from "../api/types";
import { direction, formatDifference, formatMetric } from "../lib/format";
import { shortPeriodLabel } from "../lib/periods";
import { metricTone } from "../lib/tone";
import { ChangeBadge } from "./ChangeBadge";

export const STATUS_LABEL: Record<MetricStatus, string> = {
  ok: "",
  missing_input: "Not reported",
  invalid_input: "Invalid data",
  zero_denominator: "Undefined",
  not_meaningful: "Not meaningful",
};

/** Ratio cards for the latest fiscal year, each with its change from the year before. */
export function MetricCards({ data }: { data: Financials }) {
  const index = data.periods.length - 1;
  const latest = data.periods[index]!;
  const prior = index > 0 && latest.has_prior ? data.periods[index - 1]! : null;

  return (
    <section aria-labelledby="ratios-heading">
      <div className="section-head">
        <h2 id="ratios-heading" className="section-title">
          Key ratios · {shortPeriodLabel(latest)}
        </h2>
        {prior && <p className="section-note">Change vs {shortPeriodLabel(prior)}</p>}
      </div>
      <ul className="cards">
        {data.metrics.map((metric) => {
          const current = metric.values[index]!;
          const dir = direction(current.difference, metric.format);
          return (
            <li className="card" key={metric.name}>
              <p className="card__label">{metric.label}</p>
              {current.value !== null ? (
                <p className="card__value">{formatMetric(current.value, metric.format)}</p>
              ) : (
                <p className="card__value card__value--na" title={current.reason ?? undefined}>
                  n/a <span className="card__status">{STATUS_LABEL[current.status]}</span>
                </p>
              )}
              {current.value === null ? (
                <p className="card__reason">{current.reason}</p>
              ) : current.difference !== null && prior ? (
                <ChangeBadge
                  text={formatDifference(current.difference, metric.format)}
                  dir={dir}
                  tone={metricTone(metric.name, dir)}
                  title={`Change vs ${shortPeriodLabel(prior)}`}
                />
              ) : (
                <span className="change change--na">No prior-year value</span>
              )}
              <p className="card__formula">{metric.formula}</p>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
