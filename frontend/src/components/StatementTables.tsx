import { useId, useRef, useState, type KeyboardEvent } from "react";
import type { Cell, Financials, Metric, Period, Row, StatementData } from "../api/types";
import { isEmptyRow } from "../lib/data";
import { direction, formatMetric, formatMillions, formatPercentChange } from "../lib/format";
import { formatDate, shortPeriodLabel } from "../lib/periods";
import { lineItemTone } from "../lib/tone";
import { ChangeBadge } from "./ChangeBadge";
import { STATUS_LABEL } from "./MetricCards";

type TabId = StatementData["id"] | "ratios";

/** Statements and ratio history as tabs; columns run newest → oldest like a 10-K. */
export function StatementTables({ data, indexes }: { data: Financials; indexes: number[] }) {
  const tabs: { id: TabId; title: string }[] = [
    ...data.statements.map((s) => ({ id: s.id, title: s.title })),
    { id: "ratios", title: "Ratios" },
  ];
  const [active, setActive] = useState<TabId>("income_statement");
  const baseId = useId();
  const tabRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  const newestFirst = [...indexes].reverse();

  // Arrow keys move between tabs (standard tab-list keyboard behavior).
  const onKeyDown = (event: KeyboardEvent, index: number) => {
    const step = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
    if (!step) return;
    const next = tabs[(index + step + tabs.length) % tabs.length]!;
    setActive(next.id);
    tabRefs.current[next.id]?.focus();
  };

  return (
    <section className="panel statements" aria-labelledby={`${baseId}-heading`}>
      <h2 id={`${baseId}-heading`} className="visually-hidden">
        Financial statements
      </h2>
      <div className="tabs" role="tablist" aria-label="Financial statements">
        {tabs.map((tab, i) => (
          <button
            key={tab.id}
            ref={(el) => {
              tabRefs.current[tab.id] = el;
            }}
            role="tab"
            id={`${baseId}-tab-${tab.id}`}
            aria-selected={active === tab.id}
            aria-controls={`${baseId}-panel-${tab.id}`}
            tabIndex={active === tab.id ? 0 : -1}
            className="tab"
            onClick={() => setActive(tab.id)}
            onKeyDown={(e) => onKeyDown(e, i)}
          >
            {tab.title}
          </button>
        ))}
      </div>
      <div
        role="tabpanel"
        id={`${baseId}-panel-${active}`}
        aria-labelledby={`${baseId}-tab-${active}`}
        className="tabpanel"
      >
        {active === "ratios" ? (
          <RatioTable metrics={data.metrics} periods={data.periods} indexes={newestFirst} />
        ) : (
          <StatementTable
            statement={data.statements.find((s) => s.id === active)!}
            periods={data.periods}
            indexes={newestFirst}
          />
        )}
      </div>
    </section>
  );
}

function PeriodHeaders({ periods, indexes }: { periods: Period[]; indexes: number[] }) {
  return (
    <>
      {indexes.map((i) => {
        const p = periods[i]!;
        return (
          <th key={p.end} scope="col" className="num" title={p.label}>
            {shortPeriodLabel(p)}
            <span className="th__sub">{formatDate(p.end)}</span>
          </th>
        );
      })}
    </>
  );
}

function StatementTable({
  statement,
  periods,
  indexes,
}: {
  statement: StatementData;
  periods: Period[];
  indexes: number[];
}) {
  const [showEmpty, setShowEmpty] = useState(false);
  const emptyRows = statement.rows.filter((r) => isEmptyRow(r, indexes));
  const rows = showEmpty ? statement.rows : statement.rows.filter((r) => !isEmptyRow(r, indexes));

  return (
    <>
      <div className="table-scroll">
        <table className="fin-table">
          <caption className="visually-hidden">{statement.title}, USD millions</caption>
          <thead>
            <tr>
              <th scope="col" className="fin-table__stub">
                USD millions
              </th>
              <PeriodHeaders periods={periods} indexes={indexes} />
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <StatementRow key={row.item} row={row} periods={periods} indexes={indexes} />
            ))}
          </tbody>
        </table>
      </div>
      {emptyRows.length > 0 && (
        <button type="button" className="link-button" onClick={() => setShowEmpty((v) => !v)}>
          {showEmpty
            ? "Hide line items with no reported values"
            : `Show ${emptyRows.length} line item${emptyRows.length === 1 ? "" : "s"} not reported in these years`}
        </button>
      )}
    </>
  );
}

function StatementRow({ row, periods, indexes }: { row: Row; periods: Period[]; indexes: number[] }) {
  const isTotal = /^(total|gross profit|operating income|net income)/i.test(row.label);
  return (
    <tr className={isTotal ? "fin-table__total" : undefined}>
      <th scope="row" className="fin-table__stub">
        {row.label}
      </th>
      {indexes.map((i) => (
        <td key={periods[i]!.end} className="num">
          <ValueCell cell={row.cells[i]!} item={row.item} />
        </td>
      ))}
    </tr>
  );
}

/** One statement value: links to its SEC filing and explains derived or restated numbers. */
function ValueCell({ cell, item }: { cell: Cell; item: string }) {
  if (cell.value === null) {
    return (
      <span className="cell__missing" title="Not reported in the company's filings">
        —
      </span>
    );
  }
  const source = cell.sources[0];
  const tooltip = [
    cell.derived ? `Derived: ${cell.derivation}` : `Reported as us-gaap:${source?.tag}`,
    cell.restated ? "Restated: a later filing changed this value; the latest is shown." : null,
    ...cell.sources.map((s) => `${s.form} filed ${s.filed} (${s.accession_number})`),
  ]
    .filter(Boolean)
    .join("\n");

  const text = formatMillions(cell.value);
  const dir = direction(cell.change?.value ?? null, "change");
  return (
    <span className="cell">
      <span className="cell__value">
        {cell.sources.length === 1 && source ? (
          <a href={source.url} target="_blank" rel="noreferrer" title={tooltip}>
            {text}
          </a>
        ) : (
          <span title={tooltip}>{text}</span>
        )}
        {cell.derived && (
          <sup className="mark" title={cell.derivation ?? undefined}>
            *
          </sup>
        )}
        {cell.restated && (
          <sup className="mark" title="Restated in a later filing">
            †
          </sup>
        )}
      </span>
      {cell.change &&
        (cell.change.value !== null ? (
          <ChangeBadge
            className="cell__change"
            text={formatPercentChange(cell.change.value)}
            dir={dir}
            tone={lineItemTone(item, dir)}
          />
        ) : (
          <span className="change change--na cell__change" title={cell.change.reason ?? undefined}>
            n/m
          </span>
        ))}
    </span>
  );
}

function RatioTable({ metrics, periods, indexes }: { metrics: Metric[]; periods: Period[]; indexes: number[] }) {
  return (
    <div className="table-scroll">
      <table className="fin-table">
        <caption className="visually-hidden">Financial ratios by fiscal year</caption>
        <thead>
          <tr>
            <th scope="col" className="fin-table__stub">
              Ratio
            </th>
            <PeriodHeaders periods={periods} indexes={indexes} />
          </tr>
        </thead>
        <tbody>
          {metrics.map((m) => (
            <tr key={m.name}>
              <th scope="row" className="fin-table__stub" title={m.formula}>
                {m.label}
                <span className="th__sub">{m.formula}</span>
              </th>
              {indexes.map((i) => {
                const v = m.values[i]!;
                return (
                  <td key={periods[i]!.end} className="num">
                    {v.value !== null ? (
                      formatMetric(v.value, m.format)
                    ) : (
                      <span className="cell__missing" title={v.reason ?? STATUS_LABEL[v.status]}>
                        n/a
                      </span>
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
