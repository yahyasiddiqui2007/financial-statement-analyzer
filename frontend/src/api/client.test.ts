import { ApiError, fetchFinancials } from "./client";

function mockFetch(impl: () => Promise<Response>) {
  vi.stubGlobal("fetch", vi.fn(impl));
}

afterEach(() => vi.unstubAllGlobals());

describe("fetchFinancials", () => {
  it("requests the ticker's financials", async () => {
    mockFetch(async () => new Response(JSON.stringify({ ok: true }), { status: 200 }));
    await fetchFinancials("BRK.B");
    expect(fetch).toHaveBeenCalledWith(
      "/api/companies/BRK.B/financials",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("maps API error codes", async () => {
    mockFetch(
      async () =>
        new Response(JSON.stringify({ error: { code: "ticker_not_found", message: "No ZZZZ." } }), {
          status: 404,
        }),
    );
    await expect(fetchFinancials("ZZZZ")).rejects.toMatchObject({
      code: "ticker_not_found",
      message: "No ZZZZ.",
    });
  });

  it("reports an unreachable backend as a network error", async () => {
    mockFetch(async () => {
      throw new TypeError("Failed to fetch");
    });
    await expect(fetchFinancials("AAPL")).rejects.toMatchObject({ code: "network" });
  });

  it("treats a non-JSON 5xx (proxy page) as the backend being down", async () => {
    mockFetch(async () => new Response("Bad Gateway", { status: 502 }));
    await expect(fetchFinancials("AAPL")).rejects.toMatchObject({ code: "network" });
  });

  it("handles unknown error shapes", async () => {
    mockFetch(async () => new Response("nope", { status: 418 }));
    const error = await fetchFinancials("AAPL").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).code).toBe("unknown");
  });
});
