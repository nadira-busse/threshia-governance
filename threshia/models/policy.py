"""
Policy models.

Policy: a governance policy parsed from a markdown document.
PolicyMatch: a policy chunk retrieved by RAG as relevant to a tool call.
"""

from dataclasses import dataclass, field


@dataclass
class Policy:
    """A governance policy loaded from a markdown document.

    Each policy file has YAML frontmatter (id, category, risk_level, etc.)
    and a markdown body with the actual policy text. The loader parses both.

    Attributes:
        id: Unique identifier from frontmatter (e.g. "fin-001").
        category: Policy domain (e.g. "financial", "data", "access").
        risk_level: "low", "medium", or "high".
        applicable_tools: Which tools this policy governs.
        source: Where the policy comes from (e.g. "EU AI Act - Article 14").
        content: The full markdown body text.
        file_path: Path to the source file (for debugging/traceability).
        gated_tools: Subset of applicable_tools that require evidenced human
                     approval before ALLOW (e.g. controlled ERP actions).
                     Tools in applicable_tools but not here are allowed
                     unconditionally once matched. Defaults to empty list
                     for policies where nothing needs gating (e.g. the
                     ITSM read-only policy).
        never_permitted: Action names this policy blocks outright, regardless
                          of approval evidence. This is the deterministic,
                          machine-authoritative source for the rule engine's
                          hard-block check (threshia/rules/never_permitted.py) —
                          loaded and validated from the policy's YAML
                          frontmatter, not parsed from Markdown prose. The
                          Markdown body may still explain these restrictions
                          in words, but formatting changes there cannot affect
                          this field. Defaults to empty list for policy
                          fixtures/tests that don't need it; the loader
                          requires at least one entry for real policy
                          documents (see threshia/policies/loader.py).
    """

    id: str
    category: str
    risk_level: str
    applicable_tools: list[str]
    source: str
    content: str
    file_path: str
    gated_tools: list[str] = field(default_factory=list)
    never_permitted: list[str] = field(default_factory=list)


@dataclass
class PolicyMatch:
    """A policy chunk retrieved by ChromaDB as relevant to a tool call.

    When the governance engine queries ChromaDB, it returns the most
    relevant chunks. This model captures each match with its relevance
    score so the verdict can report which policies were considered.

    Attributes:
        policy_id: The id of the matched policy (e.g. "fin-001").
        category: The policy's category.
        relevance_score: ChromaDB distance score (lower = more relevant).
        matched_chunk: The specific text that matched the query.
    """

    policy_id: str
    category: str
    relevance_score: float
    matched_chunk: str
