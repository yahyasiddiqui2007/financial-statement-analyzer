"""AI financial analysis grounded in the app's own calculated metrics."""

from fsa.ai.analyst import (
    DISCLAIMER,
    MODEL,
    AIAnalysis,
    AIServiceError,
    AIUnavailableError,
    ClaudeCompleter,
    Completer,
    CompletionResult,
    generate_analysis,
)
from fsa.ai.evidence import Evidence, EvidencePack, build_evidence_pack
from fsa.ai.validation import SECTIONS, Claim, RejectedClaim

__all__ = [
    "DISCLAIMER",
    "MODEL",
    "SECTIONS",
    "AIAnalysis",
    "AIServiceError",
    "AIUnavailableError",
    "Claim",
    "ClaudeCompleter",
    "Completer",
    "CompletionResult",
    "Evidence",
    "EvidencePack",
    "RejectedClaim",
    "build_evidence_pack",
    "generate_analysis",
]
