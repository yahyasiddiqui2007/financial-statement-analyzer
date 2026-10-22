"""AI analysis tests. A fake model stands in for Claude, so nothing here calls the API."""

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2
import pytest
from fastapi.testclient import TestClient

from fsa.ai import (
    DISCLAIMER,
    MODEL,
    AIServiceError,
    AIUnavailableError,
    ClaudeCompleter,
    CompletionResult,
    build_evidence_pack,
    generate_analysis,
)
from fsa.ai.validation import RawClaim, check_claim, numbers_in
from fsa.api.app import create_app
from fsa.api.limits import DailyQuota
from fsa.ingestion import FinancialHistory
from fsa.ingestion.companyfacts import parse_company_facts
from fsa.ingestion.line_items import ALL_TAGS
from fsa.ingestion.models import Company
from fsa.ingestion.normalize import build_financial_history

FIXTURE = Path(__file__).parents[1] / "ingestion" / "fixtures" / "companyfacts_example.json"
FIXED_NOW = datetime(2026, 1, 15, tzinfo=UTC)


def example_history() -> FinancialHistory:
    payload = json.loads(FIXTURE.read_text(), parse_float=Decimal)
    parsed = parse_company_facts(payload, tags=ALL_TAGS)
    company = Company(cik="0001234567", ticker="EXMP", name="Example Manufacturing Corp")
    return build_financial_history(company, parsed.facts, warnings=parsed.warnings)


def claim(statement: str, *ids: str) -> dict[str, Any]:
    return {"statement": statement, "evidence_ids": list(ids)}


def model_output(**sections: list[dict[str, Any]]) -> str:
    base: dict[str, list[dict[str, Any]]] = {
        "strengths": [],
        "concerns": [],
        "trends": [],
        "questions": [],
    }
    return json.dumps({**base, **sections})


class FakeModel:
    """Records what it was sent and returns a scripted reply."""

    def __init__(self, reply: str, model: str = MODEL) -> None:
        self.reply, self.model = reply, model
        self.calls: list[tuple[str, str]] = []

    def __call__(self, system: str, user: str) -> CompletionResult:
        self.calls.append((system, user))
        return CompletionResult(text=self.reply, model=self.model)


# ---------------------------------------------------------------------------
# Evidence pack
# ---------------------------------------------------------------------------


class TestEvidencePack:
    def test_ids_are_unique(self) -> None:
        ids = [e.id for e in build_evidence_pack(example_history()).items]
        assert len(ids) == len(set(ids))

    def test_contains_formatted_metrics_and_line_items(self) -> None:
        evidence = build_evidence_pack(example_history()).by_id()
        assert evidence["metric:gross_margin:FY2025"].value == "42.5%"
        assert evidence["metric:gross_margin:FY2025"].note == "Gross profit / Revenue"
        assert evidence["item:revenue:FY2025"].value == "$1,200M"
        # A year without a company label is identified by its end date.
        assert evidence["item:revenue:2023-06-30"].value == "$800M"

    def test_unavailable_values_say_why(self) -> None:
        evidence = build_evidence_pack(example_history()).by_id()
        quick = evidence["metric:quick_ratio:FY2025"]
        assert quick.value == "not available"
        assert quick.note is not None and "Missing required input" in quick.note
        assert evidence["item:total_debt:FY2025"].value == "not reported"

    def test_includes_trend_findings_and_statistics(self) -> None:
        evidence = build_evidence_pack(example_history()).by_id()
        assert evidence["trend:revenue_growth"].value.startswith("Direction: increasing.")
        assert evidence["trend:revenue_growth:cagr"].value == "22.5%"

    def test_prompt_is_valid_json_with_company(self) -> None:
        data = json.loads(build_evidence_pack(example_history()).to_prompt_json())
        assert data["company"] == {"name": "Example Manufacturing Corp", "ticker": "EXMP"}
        assert data["fiscal_years"] == ["2023-06-30", "FY2024", "FY2025"]


# ---------------------------------------------------------------------------
# Claim verification
# ---------------------------------------------------------------------------


class TestNumbersIn:
    def test_normalizes_formats(self) -> None:
        assert numbers_in("$416,161M and 46.90% and 1.34x in FY2025") == {
            Decimal("416161"),
            Decimal("46.9"),
            Decimal("1.34"),
            Decimal("2025"),
        }

    def test_no_numbers(self) -> None:
        assert numbers_in("Margins expanded.") == set()


class TestCheckClaim:
    @pytest.fixture
    def evidence(self) -> dict[str, Any]:
        return build_evidence_pack(example_history()).by_id()

    def test_grounded_claim_passes(self, evidence: dict[str, Any]) -> None:
        ok = RawClaim(
            statement="Gross margin was 42.5% in FY2025.",
            evidence_ids=["metric:gross_margin:FY2025"],
        )
        assert check_claim(ok, evidence) is None

    def test_no_evidence(self, evidence: dict[str, Any]) -> None:
        reason = check_claim(RawClaim(statement="Margins are healthy.", evidence_ids=[]), evidence)
        assert reason == "It cites no evidence."

    def test_unknown_evidence_id(self, evidence: dict[str, Any]) -> None:
        bad = RawClaim(statement="Margins rose.", evidence_ids=["metric:made_up:FY2025"])
        assert "does not exist: metric:made_up:FY2025" in (check_claim(bad, evidence) or "")

    def test_invented_number(self, evidence: dict[str, Any]) -> None:
        bad = RawClaim(
            statement="Gross margin was 43% in FY2025.",
            evidence_ids=["metric:gross_margin:FY2025"],
        )
        assert "not found in its cited evidence: 43" in (check_claim(bad, evidence) or "")

    def test_reformatted_number_is_rejected(self, evidence: dict[str, Any]) -> None:
        # "$1.2B" is not how the evidence writes it ("$1,200M"), so it can't be verified.
        bad = RawClaim(statement="Revenue reached $1.2B.", evidence_ids=["item:revenue:FY2025"])
        assert check_claim(bad, evidence) is not None

    def test_year_must_be_supported_by_cited_evidence(self, evidence: dict[str, Any]) -> None:
        bad = RawClaim(
            statement="Gross margin was 42.5% in FY2024.",
            evidence_ids=["metric:gross_margin:FY2025"],
        )
        assert "2024" in (check_claim(bad, evidence) or "")

    def test_number_from_another_cited_item_is_fine(self, evidence: dict[str, Any]) -> None:
        ok = RawClaim(
            statement="Gross margin rose from 40.0% in FY2024 to 42.5% in FY2025.",
            evidence_ids=["metric:gross_margin:FY2024", "metric:gross_margin:FY2025"],
        )
        assert check_claim(ok, evidence) is None

    @pytest.mark.parametrize(
        "statement",
        [
            "The stock looks undervalued given 42.5% margins.",
            "Investors should buy on 42.5% gross margin.",
            "This is a good investment with 42.5% gross margin.",
        ],
    )
    def test_advice_language(self, evidence: dict[str, Any], statement: str) -> None:
        bad = RawClaim(statement=statement, evidence_ids=["metric:gross_margin:FY2025"])
        assert "investment-advice language" in (check_claim(bad, evidence) or "")


# ---------------------------------------------------------------------------
# generate_analysis
# ---------------------------------------------------------------------------


class TestGenerateAnalysis:
    def test_model_only_receives_the_evidence_pack(self) -> None:
        fake = FakeModel(model_output())
        generate_analysis(example_history(), fake, now=lambda: FIXED_NOW)
        system, user = fake.calls[0]
        assert user == build_evidence_pack(example_history()).to_prompt_json()
        assert "Use only the evidence list" in system
        assert "Do not give investment advice" in system

    def test_valid_claims_are_kept_with_their_evidence(self) -> None:
        fake = FakeModel(
            model_output(
                strengths=[
                    claim("Gross margin was 42.5% in FY2025.", "metric:gross_margin:FY2025")
                ],
                questions=[
                    claim("Why is total debt not reported for FY2025?", "item:total_debt:FY2025")
                ],
            )
        )
        result = generate_analysis(example_history(), fake, now=lambda: FIXED_NOW)
        strength = result.sections["strengths"][0]
        assert strength.statement == "Gross margin was 42.5% in FY2025."
        assert [e.id for e in strength.evidence] == ["metric:gross_margin:FY2025"]
        assert len(result.sections["questions"]) == 1
        assert result.rejected == ()
        assert result.disclaimer == DISCLAIMER
        assert result.generated_at == FIXED_NOW

    def test_ungrounded_claims_are_rejected_not_shown(self) -> None:
        fake = FakeModel(
            model_output(
                concerns=[
                    claim("Revenue fell 12% in FY2025.", "item:revenue:FY2025"),
                    claim("Competition is intensifying.", "metric:made_up"),
                ]
            )
        )
        result = generate_analysis(example_history(), fake, now=lambda: FIXED_NOW)
        assert result.sections["concerns"] == ()
        assert [r.section for r in result.rejected] == ["concerns", "concerns"]

    def test_section_is_capped(self) -> None:
        many = [claim("Gross margin was 42.5% in FY2025.", "metric:gross_margin:FY2025")] * 7
        result = generate_analysis(
            example_history(), FakeModel(model_output(trends=many)), now=lambda: FIXED_NOW
        )
        assert len(result.sections["trends"]) == 5
        assert len(result.rejected) == 2

    def test_reports_the_model_that_answered(self) -> None:
        fake = FakeModel(model_output(), model="claude-opus-4-8")  # e.g. a fallback model
        assert generate_analysis(example_history(), fake).model == "claude-opus-4-8"

    @pytest.mark.parametrize("reply", ["not json", '{"strengths": []}', '{"x": 1}'])
    def test_malformed_output(self, reply: str) -> None:
        with pytest.raises(AIServiceError, match="expected format"):
            generate_analysis(example_history(), FakeModel(reply))


# ---------------------------------------------------------------------------
# ClaudeCompleter (with a fake SDK client)
# ---------------------------------------------------------------------------


class FakeMessages:
    def __init__(self, response: Any = None, error: Exception | None = None) -> None:
        self.response, self.error = response, error
        self.kwargs: dict[str, Any] = {}

    def create(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return self.response


def fake_client(messages: FakeMessages) -> Any:
    return SimpleNamespace(beta=SimpleNamespace(messages=messages))


def response(stop_reason: str = "end_turn", text: str | None = "{}") -> Any:
    content = [SimpleNamespace(type="thinking", thinking="")]
    if text is not None:
        content.append(SimpleNamespace(type="text", text=text))
    return SimpleNamespace(stop_reason=stop_reason, content=content, model=MODEL)


class TestClaudeCompleter:
    def test_request_shape(self) -> None:
        messages = FakeMessages(response(text='{"ok": 1}'))
        result = ClaudeCompleter(fake_client(messages))("SYSTEM", "EVIDENCE")
        assert result == CompletionResult(text='{"ok": 1}', model=MODEL)
        kw = messages.kwargs
        assert kw["model"] == "claude-opus-5-5"
        assert kw["fallbacks"] == "default"
        assert kw["betas"] == ["server-side-fallback-2026-07-01"]
        assert kw["output_config"]["effort"] == "medium"
        assert kw["output_config"]["format"]["type"] == "json_schema"
        assert kw["system"] == "SYSTEM"
        assert kw["messages"] == [{"role": "user", "content": "EVIDENCE"}]

    def test_refusal(self) -> None:
        with pytest.raises(AIServiceError, match="declined"):
            ClaudeCompleter(fake_client(FakeMessages(response("refusal", None))))("s", "u")

    def test_truncated(self) -> None:
        with pytest.raises(AIServiceError, match="cut off"):
            ClaudeCompleter(fake_client(FakeMessages(response("max_tokens"))))("s", "u")

    def test_connection_error(self) -> None:
        error = anthropic.APIConnectionError(
            request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
        )
        with pytest.raises(AIServiceError, match="Could not reach"):
            ClaudeCompleter(fake_client(FakeMessages(error=error)))("s", "u")

    def test_not_configured(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        for var in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_PROFILE"):
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))  # no saved login profile either
        with pytest.raises(AIUnavailableError, match="ANTHROPIC_API_KEY"):
            ClaudeCompleter()("s", "u")


# ---------------------------------------------------------------------------
# API endpoint
# ---------------------------------------------------------------------------


class TestEndpoint:
    def make_client(
        self, reply: str | Exception, quota: DailyQuota | None = None
    ) -> tuple[TestClient, list[int]]:
        calls: list[int] = []

        def analyst(history: FinancialHistory) -> Any:
            calls.append(1)
            if isinstance(reply, Exception):
                raise reply
            return generate_analysis(history, FakeModel(reply), now=lambda: FIXED_NOW)

        app = create_app(
            lambda t: example_history(), analyst=analyst, ai_quota=quota, frontend_dist=None
        )
        return TestClient(app), calls

    def test_returns_claims_with_evidence_and_disclaimer(self) -> None:
        client, _ = self.make_client(
            model_output(
                strengths=[
                    claim("Gross margin was 42.5% in FY2025.", "metric:gross_margin:FY2025")
                ],
                concerns=[claim("Debt rose 50%.", "item:total_debt:FY2025")],
            )
        )
        body = client.post("/api/companies/exmp/ai-analysis").json()
        assert body["ticker"] == "EXMP"
        assert body["disclaimer"] == DISCLAIMER
        assert body["strengths"][0]["evidence"][0] == {
            "id": "metric:gross_margin:FY2025",
            "kind": "metric",
            "label": "Gross margin",
            "period": "FY2025",
            "value": "42.5%",
            "note": "Gross profit / Revenue",
        }
        assert body["concerns"] == []
        assert body["rejected"][0]["section"] == "concerns"

    def test_cached_per_company(self) -> None:
        client, calls = self.make_client(model_output())
        client.post("/api/companies/EXMP/ai-analysis")
        client.post("/api/companies/exmp/ai-analysis")
        assert len(calls) == 1

    def test_not_configured(self) -> None:
        client, _ = self.make_client(AIUnavailableError("Set ANTHROPIC_API_KEY."))
        response = client.post("/api/companies/EXMP/ai-analysis")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "ai_not_configured"

    def test_service_error_is_not_cached(self) -> None:
        client, calls = self.make_client(AIServiceError("busy"))
        assert client.post("/api/companies/EXMP/ai-analysis").status_code == 502
        client.post("/api/companies/EXMP/ai-analysis")
        assert len(calls) == 2

    def test_daily_limit(self) -> None:
        client, calls = self.make_client(model_output(), DailyQuota(per_client=1, total=10))
        assert client.post("/api/companies/EXMP/ai-analysis").status_code == 200
        # Same company again: served from cache, so it doesn't count.
        assert client.post("/api/companies/EXMP/ai-analysis").status_code == 200
        assert len(calls) == 1

    def test_limit_reached(self) -> None:
        client, _ = self.make_client(model_output(), DailyQuota(per_client=0, total=10))
        response = client.post("/api/companies/EXMP/ai-analysis")
        assert response.status_code == 429
        assert response.json()["error"]["code"] == "ai_rate_limited"

    def test_failed_attempts_do_not_use_quota(self) -> None:
        quota = DailyQuota(per_client=1, total=10)
        client, calls = self.make_client(AIServiceError("busy"), quota)
        client.post("/api/companies/EXMP/ai-analysis")
        client.post("/api/companies/EXMP/ai-analysis")
        assert len(calls) == 2  # the second try was allowed, not rate limited
