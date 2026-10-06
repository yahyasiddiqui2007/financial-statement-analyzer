import type { Financials } from "../api/types";

export function DataNotes({ data }: { data: Financials }) {
  return (
    <section className="panel notes" aria-labelledby="notes-heading">
      <h2 id="notes-heading" className="section-title">
        About this data
      </h2>
      <ul className="notes__list">
        <li>
          Every figure comes from the company's annual reports (Form 10-K and amendments) as filed with
          the SEC in XBRL. Click a statement value to open its filing.
        </li>
        <li>
          <strong>—</strong> means the company did not report the item. Missing values are never
          estimated or filled with zero.
        </li>
        <li>
          <strong>*</strong> Derived from other reported items (hover to see how).{" "}
          <strong>†</strong> Restated: a later filing changed the value; the latest version is shown.
        </li>
        <li>
          <strong>n/m</strong> means a percentage change is not meaningful (for example, when the prior
          year was negative). Hover for the reason.
        </li>
      </ul>
      {data.warnings.length > 0 && (
        <>
          <h3 className="notes__subtitle">Data-quality notes for {data.company.ticker}</h3>
          <ul className="notes__list notes__list--warnings">
            {data.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
