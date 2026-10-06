import type { YearRange } from "../lib/periods";

const OPTIONS: { value: YearRange; label: string }[] = [
  { value: 5, label: "5Y" },
  { value: 10, label: "10Y" },
  { value: "all", label: "All" },
];

/** Year-range filter. It scopes the charts and tables below it, so they always agree. */
export function RangeControl({
  value,
  available,
  onChange,
}: {
  value: YearRange;
  available: number;
  onChange: (value: YearRange) => void;
}) {
  return (
    <div className="range" role="group" aria-label="Years shown">
      <span className="range__label">Years</span>
      {OPTIONS.map((o) => (
        <button
          key={o.label}
          type="button"
          className="range__option"
          aria-pressed={value === o.value}
          onClick={() => onChange(o.value)}
        >
          {o.label}
        </button>
      ))}
      <span className="range__note">{available} available</span>
    </div>
  );
}
