# Financial Statement Analyzer

A web app that turns a public company's SEC filings into a financial analysis dashboard. Enter a
ticker to see its income statement, balance sheet, cash flow statement, key ratios, historical
charts, a multi-year trend analysis and an optional AI-written analysis, all built from the
company's own 10-K filings.

**Every number is traceable.** Each statement value links to the SEC filing it came from, each
ratio shows its formula and inputs, and each trend finding shows the yearly values, statistics
and rule behind its conclusion. Missing data is shown as missing; it is never estimated or
filled with zero.

## Features

- **Statements:** income statement, balance sheet and cash flow, normalized across companies
  that use different XBRL tags, fiscal year-ends (September, June, January, ...) and 52/53-week years
- **Ratios:** revenue growth, gross/operating/net margin, ROA, ROE, current and quick ratio,
  debt-to-equity, free cash flow and FCF margin, with year-over-year changes
- **Trend analysis (3 or 5 years):** revenue, margins, net income, free cash flow, debt, cash,
  assets and working capital, described factually with stated thresholds
- **AI analysis (optional, Claude):** strengths, concerns, trends and questions to investigate,
  where every claim cites the app's own figures and is verified against them before it is shown
- **Data quality handling:** duplicate filings, restatements, amendments, derived values and
  edge cases such as negative shareholders' equity and banks without current/non-current splits
- Light and dark themes, responsive down to phone width, shareable URLs (`?ticker=AAPL`)
- Installable as an app on phones and computers (Progressive Web App)

## Architecture

```
SEC EDGAR API ──▶ ingestion ──▶ normalization ──▶ calculation engine ──▶ FastAPI ──▶ React
 (companyfacts)   (rate-limited,  (XBRL tags →      (Decimal math,         (JSON with  (dashboard)
                   retries)        line items)       explicit failures)     lineage)
```

| Layer | Location | Responsibility |
|---|---|---|
| Ingestion | `src/fsa/ingestion/` | Fetch SEC data (rate limiting, retries), parse and normalize it |
| Calculation engine | `src/fsa/analytics/` | Pure functions returning `MetricResult` (value, or a reason there isn't one) |
| Trend analysis | `src/fsa/trends/` | Multi-year findings built only from engine results |
| AI analysis | `src/fsa/ai/` | Evidence pack → Claude (structured output) → claim verification |
| API | `src/fsa/api/` | FastAPI endpoint, response schemas, in-memory cache |
| Frontend | `frontend/` | React + TypeScript + Vite dashboard, Recharts charts |

**Tech:** Python 3.12, FastAPI, Pydantic, httpx, Anthropic SDK (Claude Opus 5.5) · React 19, TypeScript, Vite, Recharts ·
pytest, mypy (strict), ruff, Vitest, Testing Library.

## Correctness principles

1. **Exact arithmetic.** Money is `Decimal` end to end and travels to the browser as strings.
   Floats are rejected by the engine.
2. **No fabricated data.** A missing input produces `MISSING_INPUT`, never zero. Values that
   would mislead (e.g. ROE with negative equity) return `NOT_MEANINGFUL` with a reason.
3. **Lineage.** Every value records its XBRL tag, filing accession number and filing date.
4. **Stated rules.** Trend directions come from simple thresholds printed next to each finding.
5. **No investment advice.** The app describes reported figures; it makes no recommendations.

## How the AI analysis stays grounded

1. **Evidence pack.** The model receives only a list of facts produced by this app (line items,
   metrics and trend findings), each with an ID such as `metric:gross_margin:FY2025` and a
   pre-formatted value. It never sees filings, the web, or anything else.
2. **Structured output.** Claude must answer in a strict JSON schema: four sections of claims,
   each with the evidence IDs it relies on.
3. **Verification.** Before anything is shown, each claim is rejected if it cites no evidence,
   cites an unknown ID, contains a number that does not appear in its cited evidence, or uses
   investment-advice language. Rejected claims are listed with the reason, not silently dropped.
4. **Disclaimer.** The output is labeled as educational analysis, not financial advice.

Analyses run only when the user clicks **Generate AI analysis** (each costs roughly $0.05–$0.15 in API
usage at current Opus 5.5 prices) and are cached for an hour per company.

## Running locally

Requirements: [uv](https://docs.astral.sh/uv/) and Node.js 22+.

```bash
# 1. Install dependencies
uv sync
(cd frontend && npm ci)

# 2. Build the frontend
(cd frontend && npm run build)

# 3. Start the server. The SEC requires a User-Agent with your name and email.
export FSA_SEC_USER_AGENT="Your Name your.email@example.com"
export ANTHROPIC_API_KEY="..."   # optional: enables the AI analysis
uv run uvicorn fsa.api.app:app --port 8000
```

Open http://localhost:8000. API docs are at http://localhost:8000/docs.

For frontend development with live reload, keep the server running and start
`npm run dev` in `frontend/`, then open http://localhost:5173.

There is also a command-line preview: `uv run python -m fsa AAPL --years 5`.

## Deploying

The repository includes a `Dockerfile` (one container serves the API and the website) and a
`render.yaml` blueprint for [Render](https://render.com):

1. In Render, choose **New → Blueprint** and select this repository.
2. Fill in `FSA_SEC_USER_AGENT` (your name and email, required by the SEC) and, optionally,
   `ANTHROPIC_API_KEY` to enable the AI analysis.
3. Render builds the image and gives you a public URL. Every push to `main` redeploys.

On a public deployment, new AI analyses are limited per visitor and site-wide per day
(`FSA_AI_PER_CLIENT_DAILY`, default 5; `FSA_AI_TOTAL_DAILY`, default 50) so the API bill stays
bounded. Cached analyses don't count toward the limits.

## Tests

```bash
uv run pytest            # backend: engine, ingestion, trends, AI, API
uv run mypy src tests    # strict type checking
uv run ruff check .      # lint
(cd frontend && npm test && npx tsc --noEmit)
```

Tests use fictional fixture companies and a stand-in for Claude, so they run offline and free. A contract test keeps the frontend's
example API response identical to what the backend produces.

## Limitations

- U.S. companies filing 10-Ks in US GAAP only; foreign IFRS filers (Form 20-F) are not supported.
- Annual data only (no quarterly figures yet).
- Total debt is derived from reported debt components; unreported components are listed in the
  derivation note shown with the value.
- Data is cached in memory for an hour; there is no database yet. Caches and AI limits reset
  when the server restarts (on Render's free plan, after it sleeps from inactivity).

## Data source and disclaimer

Data comes from the SEC's public [EDGAR XBRL APIs](https://www.sec.gov/edgar/sec-api-documentation).
Figures are as reported by companies. This project is for education and is not investment advice.
