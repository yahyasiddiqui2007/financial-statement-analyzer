"""The HTTP API the frontend calls.

Run locally with:
    uv run uvicorn fsa.api.app:app --reload --port 8000
Then open http://localhost:8000/docs for interactive documentation.
"""

from __future__ import annotations

import os
import threading
from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response
from starlette.types import Scope

from fsa.ai import (
    AIAnalysis,
    AIServiceError,
    AIUnavailableError,
    ClaudeCompleter,
    generate_analysis,
)
from fsa.api.cache import TTLCache
from fsa.api.presenter import present_ai_analysis, present_financials
from fsa.api.schemas import AIAnalysisOut, ErrorOut, FinancialsOut
from fsa.ingestion import (
    CompanyDataNotFoundError,
    DataFormatError,
    FinancialHistory,
    IngestionError,
    SecAccessDeniedError,
    SecApiError,
    SecClient,
    TickerNotFoundError,
    load_financial_history,
)
from fsa.ingestion.tickers import normalize_ticker

HistoryLoader = Callable[[str], FinancialHistory]
Analyst = Callable[[FinancialHistory], AIAnalysis]

CACHE_TTL_SECONDS = 60 * 60
# The built frontend, served by this app in production. In development the
# Vite dev server serves the frontend instead and forwards /api here.
DEFAULT_FRONTEND_DIST = Path(__file__).resolve().parents[3] / "frontend" / "dist"

# (HTTP status, machine-readable code) for each kind of failure.
ERROR_RESPONSES: list[tuple[type[IngestionError], int, str]] = [
    (TickerNotFoundError, 404, "ticker_not_found"),
    (CompanyDataNotFoundError, 404, "no_financial_data"),
    (SecAccessDeniedError, 502, "sec_access_denied"),
    (DataFormatError, 502, "sec_bad_data"),
    (SecApiError, 502, "sec_unavailable"),
]


class ServerMisconfiguredError(Exception):
    pass


class FrontendFiles(StaticFiles):
    """Serves the built frontend.

    index.html must be re-checked on every visit, otherwise browsers keep an old
    copy that points at JavaScript files from a previous build. The JS/CSS files
    have content hashes in their names, so they can be cached normally.
    """

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        if response.media_type == "text/html":
            response.headers["Cache-Control"] = "no-cache"
        return response


def _sec_loader() -> HistoryLoader:
    """Default loader: one shared SecClient, created on first use."""
    client: SecClient | None = None
    lock = threading.Lock()

    def load(ticker: str) -> FinancialHistory:
        nonlocal client
        with lock:
            if client is None:
                try:
                    client = SecClient.from_env()
                except ValueError as exc:
                    raise ServerMisconfiguredError(str(exc)) from exc
        return load_financial_history(ticker, client)

    return load


def _claude_analyst() -> Analyst:
    completer = ClaudeCompleter()  # creates the Anthropic client on first use
    return lambda history: generate_analysis(history, completer)


def create_app(
    load_history: HistoryLoader | None = None,
    *,
    analyst: Analyst | None = None,
    frontend_dist: Path | None = DEFAULT_FRONTEND_DIST,
) -> FastAPI:
    """Build the app. Tests pass fakes for `load_history` and `analyst`, so nothing
    touches the network or costs money."""
    loader = load_history or _sec_loader()
    analyze = analyst or _claude_analyst()
    cache: TTLCache[FinancialHistory] = TTLCache(CACHE_TTL_SECONDS)
    ai_cache: TTLCache[AIAnalysis] = TTLCache(CACHE_TTL_SECONDS)
    app = FastAPI(title="Financial Statement Analyzer API", version="0.1.0")

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get(
        "/api/companies/{ticker}/financials",
        response_model=FinancialsOut,
        responses={404: {"model": ErrorOut}, 502: {"model": ErrorOut}, 500: {"model": ErrorOut}},
    )
    def financials(ticker: str) -> FinancialsOut:
        """Normalized annual statements and metrics for one company."""
        key = normalize_ticker(ticker)
        cached = cache.get_or_load(key, lambda: loader(key))
        return present_financials(cached.value, retrieved_at=cached.retrieved_at)

    @app.post(
        "/api/companies/{ticker}/ai-analysis",
        response_model=AIAnalysisOut,
        responses={404: {"model": ErrorOut}, 502: {"model": ErrorOut}, 503: {"model": ErrorOut}},
    )
    def ai_analysis(ticker: str) -> AIAnalysisOut:
        """AI-written analysis grounded in this app's metrics. Each call may cost money,
        so results are cached per company and data version."""
        key = normalize_ticker(ticker)
        history = cache.get_or_load(key, lambda: loader(key))
        ai_key = f"{key}:{history.retrieved_at.isoformat()}"
        analysis = ai_cache.get_or_load(ai_key, lambda: analyze(history.value))
        return present_ai_analysis(analysis.value)

    for error_type, status, code in ERROR_RESPONSES:
        app.add_exception_handler(error_type, _error_handler(status, code))
    app.add_exception_handler(ServerMisconfiguredError, _error_handler(500, "server_misconfigured"))
    app.add_exception_handler(AIUnavailableError, _error_handler(503, "ai_not_configured"))
    app.add_exception_handler(AIServiceError, _error_handler(502, "ai_unavailable"))

    env_dist = os.environ.get("FSA_FRONTEND_DIST")
    dist = Path(env_dist) if env_dist else frontend_dist
    if dist is not None and (dist / "index.html").is_file():
        app.mount("/", FrontendFiles(directory=dist, html=True), name="frontend")

    return app


def _error_handler(status: int, code: str) -> Callable[[Request, Exception], JSONResponse]:
    def handle(request: Request, exc: Exception) -> JSONResponse:
        body = ErrorOut.model_validate({"error": {"code": code, "message": str(exc)}})
        return JSONResponse(status_code=status, content=body.model_dump())

    return handle


app = create_app()
