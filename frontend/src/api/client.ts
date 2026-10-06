import type { AIAnalysis, ApiErrorBody, Financials } from "./types";

/** Error codes the UI knows how to explain. "network" means the backend didn't answer. */
export type ApiErrorCode =
  | "ticker_not_found"
  | "no_financial_data"
  | "sec_access_denied"
  | "sec_bad_data"
  | "sec_unavailable"
  | "server_misconfigured"
  | "ai_not_configured"
  | "ai_unavailable"
  | "network"
  | "unknown";

const KNOWN_CODES = new Set<string>([
  "ticker_not_found",
  "no_financial_data",
  "sec_access_denied",
  "sec_bad_data",
  "sec_unavailable",
  "server_misconfigured",
  "ai_not_configured",
  "ai_unavailable",
]);

export class ApiError extends Error {
  readonly code: ApiErrorCode;

  constructor(code: ApiErrorCode, message: string) {
    super(message);
    this.name = "ApiError";
    this.code = code;
  }
}

/** Fetch normalized statements and metrics for one ticker from our backend. */
export function fetchFinancials(ticker: string, signal?: AbortSignal): Promise<Financials> {
  return request<Financials>(`/api/companies/${encodeURIComponent(ticker)}/financials`, "GET", signal);
}

/** Ask the backend for an AI analysis (calls Claude; results are cached for an hour). */
export function requestAIAnalysis(ticker: string, signal?: AbortSignal): Promise<AIAnalysis> {
  return request<AIAnalysis>(`/api/companies/${encodeURIComponent(ticker)}/ai-analysis`, "POST", signal);
}

async function request<T>(url: string, method: "GET" | "POST", signal?: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url, { method, signal, headers: { Accept: "application/json" } });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw new ApiError("network", "Could not reach the analysis server.");
  }

  if (response.ok) {
    return (await response.json()) as T;
  }

  const body = await readErrorBody(response);
  if (body && KNOWN_CODES.has(body.error.code)) {
    throw new ApiError(body.error.code as ApiErrorCode, body.error.message);
  }
  if (!body && response.status >= 500) {
    // No JSON error body: the dev proxy or a gateway answered because our backend didn't.
    throw new ApiError("network", "The analysis server is not responding.");
  }
  throw new ApiError("unknown", `The server returned an unexpected error (HTTP ${response.status}).`);
}

async function readErrorBody(response: Response): Promise<ApiErrorBody | null> {
  try {
    const body: unknown = await response.json();
    if (
      typeof body === "object" &&
      body !== null &&
      "error" in body &&
      typeof (body as ApiErrorBody).error?.code === "string"
    ) {
      return body as ApiErrorBody;
    }
  } catch {
    // Not JSON (e.g. a proxy error page); fall through.
  }
  return null;
}
