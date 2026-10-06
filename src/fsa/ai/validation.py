"""Checks every AI claim against the evidence before anyone sees it.

A claim is accepted only if:
  1. it cites at least one evidence ID,
  2. every cited ID exists in the evidence pack,
  3. every number in its text appears in the evidence it cites, and
  4. it contains no investment-advice language.

Rejected claims are kept (with the reason) and shown to the user separately,
so the filtering is transparent rather than silent.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, ConfigDict

from fsa.ai.evidence import Evidence, EvidencePack

Section = Literal["strengths", "concerns", "trends", "questions"]
SECTIONS: tuple[Section, ...] = ("strengths", "concerns", "trends", "questions")
MAX_CLAIMS_PER_SECTION = 5

# Digits with optional thousands separators and decimals: "416,161", "46.9", "2025".
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")

ADVICE_LANGUAGE = re.compile(
    r"\b(buy|sell|hold|investors?|invest in|investment (?:case|thesis)|recommend\w*|"
    r"undervalued|overvalued|price target|fair value|bullish|bearish|outperform\w*|"
    r"underperform\w*|good investment|bad investment)\b",
    re.IGNORECASE,
)


# --- What the model must return (also used to build the JSON schema) --------


class RawClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    statement: str
    evidence_ids: list[str]


class RawAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    strengths: list[RawClaim]
    concerns: list[RawClaim]
    trends: list[RawClaim]
    questions: list[RawClaim]


def _claims_schema(description: str) -> dict[str, object]:
    return {
        "type": "array",
        "description": description,
        "items": {
            "type": "object",
            "additionalProperties": False,
            "required": ["statement", "evidence_ids"],
            "properties": {
                "statement": {"type": "string"},
                "evidence_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "IDs from the evidence list that support this statement.",
                },
            },
        },
    }


OUTPUT_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": list(SECTIONS),
    "properties": {
        "strengths": _claims_schema("Financial strengths shown by the evidence."),
        "concerns": _claims_schema("Potential concerns shown by the evidence."),
        "trends": _claims_schema("Important multi-year trends."),
        "questions": _claims_schema("Questions an analyst should investigate, as questions."),
    },
}


# --- Validated result --------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Claim:
    statement: str
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True, slots=True)
class RejectedClaim:
    section: Section
    statement: str
    reason: str


@dataclass(frozen=True, slots=True)
class ValidatedClaims:
    sections: dict[Section, tuple[Claim, ...]]
    rejected: tuple[RejectedClaim, ...]


def numbers_in(text: str) -> set[Decimal]:
    """Every number in a piece of text, normalized: "$416,161M" → 416161, "46.90%" → 46.9."""
    found = set()
    for token in _NUMBER.findall(text):
        try:
            found.add(Decimal(token.replace(",", "")).normalize())
        except InvalidOperation:
            continue
    return found


def _evidence_text(e: Evidence) -> str:
    return " ".join(part for part in (e.label, e.period, e.value, e.note) if part)


def check_claim(claim: RawClaim, evidence: dict[str, Evidence]) -> str | None:
    """Why a claim must be rejected, or None if it passes every check."""
    ids = list(dict.fromkeys(claim.evidence_ids))  # dedupe, keep order
    if not claim.statement.strip():
        return "The statement is empty."
    if not ids:
        return "It cites no evidence."
    unknown = [i for i in ids if i not in evidence]
    if unknown:
        return f"It cites evidence that does not exist: {', '.join(unknown)}."
    allowed: set[Decimal] = set()
    for i in ids:
        allowed |= numbers_in(_evidence_text(evidence[i]))
    unsupported = sorted(numbers_in(claim.statement) - allowed)
    if unsupported:
        shown = ", ".join(format(n, "f") for n in unsupported)
        return f"It contains numbers not found in its cited evidence: {shown}."
    match = ADVICE_LANGUAGE.search(claim.statement)
    if match:
        return f'It uses investment-advice language ("{match.group(0)}").'
    return None


def validate_claims(raw: RawAnalysis, pack: EvidencePack) -> ValidatedClaims:
    evidence = pack.by_id()
    sections: dict[Section, tuple[Claim, ...]] = {}
    rejected: list[RejectedClaim] = []
    for section in SECTIONS:
        accepted: list[Claim] = []
        for claim in getattr(raw, section):
            reason = check_claim(claim, evidence)
            if reason is None and len(accepted) >= MAX_CLAIMS_PER_SECTION:
                reason = f"The section already has {MAX_CLAIMS_PER_SECTION} claims."
            if reason is not None:
                rejected.append(RejectedClaim(section, claim.statement, reason))
                continue
            ids = dict.fromkeys(claim.evidence_ids)
            accepted.append(Claim(claim.statement.strip(), tuple(evidence[i] for i in ids)))
        sections[section] = tuple(accepted)
    return ValidatedClaims(sections=sections, rejected=tuple(rejected))
