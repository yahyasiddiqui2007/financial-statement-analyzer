import { useCallback, useEffect, useState } from "react";
import { ApiError, fetchFinancials } from "../api/client";
import type { Financials } from "../api/types";

export type FetchState =
  | { status: "idle" }
  | { status: "loading"; ticker: string; previous: Financials | null }
  | { status: "success"; ticker: string; data: Financials }
  | { status: "error"; ticker: string; error: ApiError; previous: Financials | null };

/**
 * Loads financials whenever `ticker` changes. While a new company loads, the
 * previous company's data stays available so the page doesn't flash empty.
 */
export function useFinancials(ticker: string | null): { state: FetchState; retry: () => void } {
  const [state, setState] = useState<FetchState>({ status: "idle" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!ticker) {
      setState({ status: "idle" });
      return;
    }
    const controller = new AbortController();
    setState((prev) => ({ status: "loading", ticker, previous: lastData(prev) }));

    fetchFinancials(ticker, controller.signal)
      .then((data) => setState({ status: "success", ticker, data }))
      .catch((err: unknown) => {
        if (controller.signal.aborted) return; // a newer search replaced this one
        const error =
          err instanceof ApiError ? err : new ApiError("unknown", "Something went wrong.");
        setState((prev) => ({ status: "error", ticker, error, previous: lastData(prev) }));
      });

    return () => controller.abort();
  }, [ticker, attempt]);

  const retry = useCallback(() => setAttempt((n) => n + 1), []);
  return { state, retry };
}

function lastData(state: FetchState): Financials | null {
  switch (state.status) {
    case "success":
      return state.data;
    case "loading":
    case "error":
      return state.previous;
    default:
      return null;
  }
}
