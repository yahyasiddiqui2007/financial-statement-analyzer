import { lazy, Suspense, useEffect, useState } from "react";
import type { Financials } from "./api/types";
import { AIAnalysisPanel } from "./components/AIAnalysisPanel";
import { CompanyOverview } from "./components/CompanyOverview";
import { DataNotes } from "./components/DataNotes";
import { MetricCards } from "./components/MetricCards";
import { RangeControl } from "./components/RangeControl";
import { StatementTables } from "./components/StatementTables";
import { EmptyState, ErrorState, LoadingState } from "./components/States";
import { TopBar } from "./components/TopBar";
import { TrendAnalysis } from "./components/TrendAnalysis";
import { useChartColors } from "./hooks/useChartColors";
import { useFinancials } from "./hooks/useFinancials";
import { useTheme } from "./hooks/useTheme";
import { visibleIndexes, type YearRange } from "./lib/periods";

// The chart library is large, so it loads separately and the search page appears faster.
const FinancialCharts = lazy(() =>
  import("./components/Charts").then((m) => ({ default: m.FinancialCharts })),
);

function tickerFromUrl(): string | null {
  const value = new URLSearchParams(window.location.search).get("ticker");
  return value ? value.toUpperCase() : null;
}

export default function App() {
  const [ticker, setTicker] = useState<string | null>(tickerFromUrl);
  const [range, setRange] = useState<YearRange>(5);
  const { state, retry } = useFinancials(ticker);
  const theme = useTheme();
  const colors = useChartColors(theme.resolved);

  // The ticker lives in the URL (?ticker=AAPL) so results can be shared and the back button works.
  useEffect(() => {
    const onPop = () => setTicker(tickerFromUrl());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const search = (next: string) => {
    if (next === ticker) {
      retry();
      return;
    }
    window.history.pushState(null, "", `?ticker=${encodeURIComponent(next)}`);
    setTicker(next);
  };

  useEffect(() => {
    document.title =
      state.status === "success"
        ? `${state.data.company.ticker} · ${state.data.company.name} · Financial Statement Analyzer`
        : "Financial Statement Analyzer";
  }, [state]);

  // While a new search loads, keep showing the previous company (dimmed) instead of a blank page.
  const shown: Financials | null =
    state.status === "success" ? state.data : state.status === "idle" ? null : state.previous;
  const loading = state.status === "loading";

  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <TopBar
        ticker={ticker}
        loading={loading}
        onSearch={search}
        theme={theme.choice}
        onThemeChange={theme.setChoice}
      />
      <main id="main" className="page">
        {state.status === "idle" && <EmptyState onPick={search} />}
        {loading && !shown && <LoadingState ticker={state.ticker} />}
        {loading && shown && (
          <p className="refetch-bar" role="status">
            <span className="spinner" aria-hidden="true" /> Loading {state.ticker}…
          </p>
        )}
        {state.status === "error" && (
          <ErrorState ticker={state.ticker} error={state.error} onRetry={retry} />
        )}
        {shown && state.status !== "error" && (
          <Dashboard data={shown} range={range} onRangeChange={setRange} colors={colors} dimmed={loading} />
        )}
      </main>
      <footer className="footer">
        Data: SEC EDGAR. Not investment advice. Figures are as reported by companies; verify against the
        original filings before relying on them.
      </footer>
    </>
  );
}

function Dashboard({
  data,
  range,
  onRangeChange,
  colors,
  dimmed,
}: {
  data: Financials;
  range: YearRange;
  onRangeChange: (r: YearRange) => void;
  colors: ReturnType<typeof useChartColors>;
  dimmed: boolean;
}) {
  const indexes = visibleIndexes(data.periods.length, range);
  return (
    <div className={`dashboard${dimmed ? " dashboard--dimmed" : ""}`} aria-busy={dimmed}>
      <CompanyOverview data={data} />
      <MetricCards data={data} />
      <TrendAnalysis reports={data.trends} />
      {/* key: start fresh for each company */}
      <AIAnalysisPanel key={data.company.ticker} ticker={data.company.ticker} />
      <RangeControl value={range} available={data.periods.length} onChange={onRangeChange} />
      <Suspense fallback={<div className="skeleton skeleton--chart" aria-label="Loading charts" />}>
        <FinancialCharts data={data} indexes={indexes} colors={colors} />
      </Suspense>
      <StatementTables data={data} indexes={indexes} />
      <DataNotes data={data} />
    </div>
  );
}
