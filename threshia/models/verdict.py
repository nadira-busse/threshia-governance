"""
Verdict model.

The output of the governance engine. Every tool call evaluation
produces exactly one Verdict, regardless of whether it was decided
by a deterministic rule, an LLM evaluation, or a fallback.

Design decision D1: three verdicts only (ALLOW / BLOCK / FLAG).
No CONDITIONAL — runtime governance is a gate, not an assessment.
See docs/architecture-overview.md section on verdict design for rationale.

Design decision D7: decision_source tracks HOW the verdict was reached.
"rule" = deterministic check (<1ms), "llm" = RAG + LLM (~300ms),
"fallback" = LLM failed, defaulting to FLAG for safety.
This replaced the original confidence field (LLM self-assessed
confidence is unreliable — retrieval_score and policy_coverage
are more meaningful signals).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Literal

from threshia.models.policy import PolicyMatch

if TYPE_CHECKING:
    # Import only for type checkers — avoids a circular import at runtime
    # (tool_call.py doesn't import verdict.py, so this is one-directional,
    # but keeping it under TYPE_CHECKING is the standard, lint-clean way
    # to write a forward reference).
    from threshia.models.tool_call import ToolCall


# Valid verdict decisions — used for validation
VALID_DECISIONS = {"ALLOW", "BLOCK", "FLAG"}

# Valid decision sources — used for validation
VALID_SOURCES = {"rule", "llm", "fallback"}


@dataclass
class Verdict:
    """The governance engine's decision on a tool call.

    Attributes:
        decision: ALLOW (compliant), BLOCK (violation), or FLAG (needs review).
        tool_call: The ToolCall that was evaluated.
        matched_policies: Policies that were relevant to the decision.
        reasoning: Human-readable explanation of why this decision was made.
        decision_source: How the decision was reached:
                         "rule" (deterministic), "llm" (RAG+LLM), "fallback" (error).
        retrieval_score: ChromaDB relevance score. None for rule-based decisions.
        policy_coverage: Number of applicable policies found.
        provider: Which LLM provider was used, or "none" for rule-based decisions.
        evaluation_ms: How long the evaluation took in milliseconds.
        timestamp: When the verdict was produced.
        fallback_reason: Only set when decision_source is "fallback".
    """

    decision: Literal["ALLOW", "BLOCK", "FLAG"]
    tool_call: "ToolCall"  # forward reference to avoid circular import
    matched_policies: list[PolicyMatch]
    reasoning: str
    decision_source: str
    retrieval_score: float | None
    policy_coverage: int
    provider: str
    evaluation_ms: int
    timestamp: datetime = field(default_factory=datetime.now)
    fallback_reason: str | None = None

    def __post_init__(self):
        """Validate decision and decision_source values."""
        if self.decision not in VALID_DECISIONS:
            raise ValueError(
                f"Invalid decision '{self.decision}'. "
                f"Must be one of: {VALID_DECISIONS}"
            )
        if self.decision_source not in VALID_SOURCES:
            raise ValueError(
                f"Invalid decision_source '{self.decision_source}'. "
                f"Must be one of: {VALID_SOURCES}"
            )
