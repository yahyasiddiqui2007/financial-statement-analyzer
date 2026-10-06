import type { ApiError, ApiErrorCode } from "../api/client";

const EXAMPLES = [
  { ticker: "AAPL", note: "September fiscal year" },
  { ticker: "MSFT", note: "June fiscal year" },
  { ticker: "WMT", note: "January fiscal year" },
  { ticker: "MCD", note: "Negative equity" },
  { ticker: "JPM", note: "Bank" },
];

export function EmptyState({ onPick }: { onPick: (ticker: string) => void }) {
  return (
    <section className="panel empty">
      <h1 className="empty__title">Analyze a U.S. public company</h1>
      <p className="empty__text">
        Enter a ticker to see its income statement, balance sheet, cash flow statement and key
        ratios, built from the company's 10-K filings with the SEC.
      </p>
      <ul className="examples" aria-label="Example companies">
        {EXAMPLES.map((e) => (
          <li key={e.ticker}>
            <button type="button" className="chip" onClick={() => onPick(e.ticker)}>
              <span className="chip__ticker">{e.ticker}</span>
              <span className="chip__note">{e.note}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function LoadingState({ ticker }: { ticker: string }) {
  return (
    <section className="loading" aria-busy="true">
      <p className="loading__status" role="status">
        <span className="spinner" aria-hidden="true" />
        Fetching {ticker} filings from SEC EDGAR…
      </p>
      <div className="skeleton skeleton--header" />
      <div className="skeleton-grid">
        {Array.from({ length: 6 }, (_, i) => (
          <div key={i} className="skeleton skeleton--card" />
        ))}
      </div>
      <div className="skeleton skeleton--chart" />
    </section>
  );
}

const ERROR_COPY: Record<ApiErrorCode, { title: string; retry: boolean }> = {
  ticker_not_found: { title: "Ticker not found", retry: false },
  no_financial_data: { title: "No financial statements available", retry: false },
  sec_access_denied: { title: "SEC EDGAR refused the request", retry: true },
  sec_bad_data: { title: "SEC EDGAR returned unexpected data", retry: true },
  sec_unavailable: { title: "SEC EDGAR is not responding", retry: true },
  server_misconfigured: { title: "The server needs configuration", retry: false },
  ai_not_configured: { title: "AI analysis is not configured", retry: false },
  ai_unavailable: { title: "AI analysis failed", retry: true },
  network: { title: "Can't reach the analysis server", retry: true },
  unknown: { title: "Something went wrong", retry: true },
};

export function ErrorState({
  ticker,
  error,
  onRetry,
}: {
  ticker: string;
  error: ApiError;
  onRetry: () => void;
}) {
  const copy = ERROR_COPY[error.code];
  return (
    <section className="panel error" role="alert">
      <h2 className="error__title">{copy.title}</h2>
      <p className="error__message">{error.message}</p>
      {error.code === "network" && (
        <p className="error__hint">
          Make sure the backend is running: <code>uv run uvicorn fsa.api.app:app --port 8000</code>
        </p>
      )}
      {error.code === "server_misconfigured" && (
        <p className="error__hint">
          Set <code>FSA_SEC_USER_AGENT</code> to your name and email, then restart the backend.
        </p>
      )}
      {copy.retry && (
        <button type="button" className="button" onClick={onRetry}>
          Try {ticker} again
        </button>
      )}
    </section>
  );
}
