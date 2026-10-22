import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";
import fixture from "./test/fixtures/financials_example.json";

function respondWith(status: number, body: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify(body), { status })),
  );
}

beforeEach(() => window.history.replaceState(null, "", "/"));
afterEach(() => vi.unstubAllGlobals());

async function search(ticker: string) {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Company ticker"), ticker);
  await user.click(screen.getByRole("button", { name: "Analyze" }));
}

describe("App", () => {
  it("starts with an empty state and example tickers", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: /analyze a u\.s\. public company/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /AAPL/ })).toBeInTheDocument();
  });

  it("validates the ticker before searching", async () => {
    respondWith(200, fixture);
    render(<App />);
    await search("$$$");
    expect(screen.getByRole("alert")).toHaveTextContent("Enter a ticker");
    expect(fetch).not.toHaveBeenCalled();
  });

  it("shows loading, then the dashboard with pipeline numbers", async () => {
    respondWith(200, fixture);
    render(<App />);
    await search("exmp");

    expect(await screen.findByRole("heading", { name: "Example Manufacturing Corp" })).toBeInTheDocument();
    expect(window.location.search).toBe("?ticker=EXMP");

    // Headline tile: FY2025 revenue 1,200,000,000 → $1.2B, up 20.0% vs FY2024.
    const tiles = screen.getByText("Revenue · FY2025").closest(".tile") as HTMLElement;
    expect(within(tiles).getByText("$1.2B")).toBeInTheDocument();
    expect(within(tiles).getByText(/\+20\.0% vs FY2024/)).toBeInTheDocument();

    // Ratio card: gross margin 42.5%, +2.5 pp vs prior year.
    const card = screen.getByText("Gross margin").closest(".card") as HTMLElement;
    expect(within(card).getByText("42.5%")).toBeInTheDocument();
    expect(within(card).getByText(/\+2\.5 pp/)).toBeInTheDocument();

    // Unreported inputs explain themselves instead of showing a number.
    const quick = screen.getByText("Quick ratio").closest(".card") as HTMLElement;
    expect(within(quick).getByText(/Not reported/)).toBeInTheDocument();
  });

  it("shows statement tables newest-first with filing links", async () => {
    respondWith(200, fixture);
    render(<App />);
    await search("EXMP");
    const table = await screen.findByRole("table", { name: /income statement/i });
    const headers = within(table).getAllByRole("columnheader").map((h) => h.textContent);
    expect(headers[1]).toMatch(/^FY2025/);
    const revenueRow = within(table).getByRole("rowheader", { name: "Revenue" }).closest("tr")!;
    const link = within(revenueRow).getByRole("link", { name: "1,200" });
    expect(link).toHaveAttribute("href", expect.stringContaining("sec.gov/Archives/edgar/data/1234567"));
  });

  it("switches to the balance sheet tab", async () => {
    respondWith(200, fixture);
    render(<App />);
    await search("EXMP");
    await userEvent.click(await screen.findByRole("tab", { name: "Balance Sheet" }));
    const table = screen.getByRole("table", { name: /balance sheet/i });
    expect(within(table).getByRole("rowheader", { name: "Total assets" })).toBeInTheDocument();
  });

  it("explains an unknown ticker", async () => {
    respondWith(404, { error: { code: "ticker_not_found", message: "No SEC-registered company has the ticker ZZZZ." } });
    render(<App />);
    await search("ZZZZ");
    expect(await screen.findByRole("heading", { name: "Ticker not found" })).toBeInTheDocument();
    expect(screen.getByText(/ZZZZ/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /try/i })).not.toBeInTheDocument();
  });

  it("offers a retry when SEC EDGAR is down, and recovers", async () => {
    respondWith(502, { error: { code: "sec_unavailable", message: "The SEC kept returning HTTP 503." } });
    render(<App />);
    await search("EXMP");
    const retry = await screen.findByRole("button", { name: "Try EXMP again" });

    respondWith(200, fixture);
    await userEvent.click(retry);
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Example Manufacturing Corp" })).toBeInTheDocument(),
    );
  });
});

describe("Trend analysis", () => {
  it("shows findings with their supporting numbers", async () => {
    respondWith(200, fixture);
    render(<App />);
    await search("EXMP");
    const section = (await screen.findByRole("heading", { name: /trend analysis/i })).closest("section")!;
    const revenue = within(section).getByRole("heading", { name: "Revenue growth" }).closest("li")!;

    // The summary sentence, the direction, and the evidence agree.
    expect(within(revenue).getByText(/Revenue grew from \$800M/)).toBeInTheDocument();
    expect(within(revenue).getByText("Increasing")).toBeInTheDocument();
    const evidence = within(revenue).getByRole("table");
    expect(within(evidence).getByText("$1,200M")).toBeInTheDocument();
    // CAGR (1200 / 800)^(1/2) − 1 = 22.5%, shown with its formula and inputs.
    expect(within(revenue).getByText("22.5%")).toBeInTheDocument();
    expect(
      within(revenue).getByText(/beginning value \$800M · ending value \$1,200M · years 2/),
    ).toBeInTheDocument();
  });

  it("explains findings that lack data", async () => {
    respondWith(200, fixture);
    render(<App />);
    await search("EXMP");
    const debt = (await screen.findByRole("heading", { name: "Debt" })).closest("li")!;
    expect(within(debt).getByText("Insufficient data")).toBeInTheDocument();
    expect(within(debt).getByText(/total debt is not available/i)).toBeInTheDocument();
  });
});

describe("AI analysis", () => {
  const aiAnalysis = {
    ticker: "EXMP",
    model: "claude-opus-5-5",
    generated_at: "2026-01-15T12:00:00Z",
    disclaimer: "Educational analysis generated by an AI model. Not financial or investment advice.",
    evidence_count: 99,
    strengths: [
      {
        statement: "Gross margin was 42.5% in FY2025.",
        evidence: [
          {
            id: "metric:gross_margin:FY2025",
            kind: "metric",
            label: "Gross margin",
            period: "FY2025",
            value: "42.5%",
            note: "Gross profit / Revenue",
          },
        ],
      },
    ],
    concerns: [],
    trends: [],
    questions: [],
    rejected: [{ section: "concerns", statement: "Revenue fell 12%.", reason: "It contains numbers not found in its cited evidence: 12." }],
  };

  function route(ai: { status: number; body: unknown }) {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) =>
        url.endsWith("/ai-analysis")
          ? new Response(JSON.stringify(ai.body), { status: ai.status })
          : new Response(JSON.stringify(fixture), { status: 200 }),
      ),
    );
  }

  it("does nothing until asked, then shows verified claims with their figures", async () => {
    route({ status: 200, body: aiAnalysis });
    render(<App />);
    await search("EXMP");
    const panel = (await screen.findByRole("heading", { name: "AI analysis" })).closest("section")!;
    expect(within(panel).getByRole("note")).toHaveTextContent(/not financial or investment advice/i);
    expect(fetch).toHaveBeenCalledTimes(1); // only the financials so far

    await userEvent.click(within(panel).getByRole("button", { name: "Generate AI analysis" }));
    expect(await within(panel).findByText("Gross margin was 42.5% in FY2025.")).toBeInTheDocument();
    const chips = within(panel).getByRole("list", { name: "Supporting figures" });
    expect(chips).toHaveTextContent("Gross margin · FY2025");
    expect(chips).toHaveTextContent("42.5%");
    expect(within(panel).getByText(/1 claim was removed/)).toBeInTheDocument();
    expect(within(panel).getByText("No concerns passed verification.")).toBeInTheDocument();
  });

  it("explains the daily limit without offering a retry", async () => {
    route({
      status: 429,
      body: { error: { code: "ai_rate_limited", message: "You've reached the limit of 5 AI analyses per day." } },
    });
    render(<App />);
    await search("EXMP");
    await userEvent.click(await screen.findByRole("button", { name: "Generate AI analysis" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Daily AI limit reached");
    expect(within(alert).queryByRole("button")).not.toBeInTheDocument();
  });

  it("explains how to enable AI when no API key is configured", async () => {
    route({
      status: 503,
      body: { error: { code: "ai_not_configured", message: "AI analysis is not configured." } },
    });
    render(<App />);
    await search("EXMP");
    await userEvent.click(await screen.findByRole("button", { name: "Generate AI analysis" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("ANTHROPIC_API_KEY");
  });
});
