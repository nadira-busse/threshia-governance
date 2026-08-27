"""
Verdict model.

A Verdict is the authoritative governance decision for one ToolCall,
produced by evaluate() (threshia/engine/evaluator.py) regardless of
whether the decision came from a deterministic rule, semantic provider
analysis, or a safe fallback.

Only three decisions exist: ALLOW, BLOCK, FLAG. There is no CONDITIONAL
— a runtime gate has to tell the caller whether to proceed, stop, or send
the call for review, not produce an assessment for later judgment. See
docs/architecture-overview.md for the fuller rationale.

decision_source records the evaluation path: "rule" for deterministic
evaluation, "llm" when semantic provider analysis contributed advisory
context, "fallback" when the semantic path failed safely.
decision_source replaces a plain LLM self-reported confidence score,
which isn't a reliable signal on its own — retrieval_score and
policy_coverage are more meaningful for understanding an "llm" verdict.

Only explicit deterministic policy coverage may produce ALLOW. A tool
call with no policy in its applicable_tools has, by definition, no policy
that explicitly prohibits it either, so an uncovered tool call's
semantic-path verdict is always authoritative FLAG, regardless of what
the configured provider suggested (ALLOW, BLOCK, or FLAG). This is
enforced in threshia/engine/evaluator.py after the provider response is
parsed and validated, not by prompt wording. The provider's actual
suggestion is preserved separately in provider_suggested_decision and
folded into `reasoning` — never silently dropped, never treated as
authorization. See tests/test_semantic_evaluation.py for the regression
coverage, including a case modeled on a provider recommending ALLOW for
a semantically unrelated, uncovered tool call.
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
        provider_suggested_decision: The raw decision an LLM provider
                                      returned for an uncovered tool call,
                                      when decision_source is "llm" and
                                      that suggestion differs from the
                                      authoritative `decision` (see the
                                      module docstring above). None
                                      whenever no provider suggestion
                                      exists or it already matches
                                      `decision` — this field exists
                                      specifically to make an overridden
                                      suggestion inspectable, not to
                                      duplicate agreement.
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
    provider_suggested_decision: str | None = None

    def __post_init__(self):
        """Validate decision, decision_source, and provider_suggested_decision."""
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
        if (
            self.provider_suggested_decision is not None
            and self.provider_suggested_decision not in VALID_DECISIONS
        ):
            raise ValueError(
                f"Invalid provider_suggested_decision "
                f"'{self.provider_suggested_decision}'. "
                f"Must be one of: {VALID_DECISIONS} or None."
            )
