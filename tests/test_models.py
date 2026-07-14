"""
Tests for Threshia data models and configuration.

Tests verify:
- Model creation with required and default fields
- Verdict validation (invalid decision/source raises ValueError)
- Config defaults load correctly
"""

from datetime import datetime

import pytest

from threshia.config import POLICIES_DIR, TOP_K_POLICIES
from threshia.models import Policy, PolicyMatch, ToolCall, Verdict

# --- ToolCall tests ---


def test_tool_call_creation():
    """ToolCall can be created with required fields only."""
    tc = ToolCall(tool_name="transfer_funds", parameters={"amount": 100})

    assert tc.tool_name == "transfer_funds"
    assert tc.parameters == {"amount": 100}
    assert tc.agent_id == "demo-agent"  # default
    assert isinstance(tc.timestamp, datetime)  # auto-generated


def test_tool_call_custom_agent_id():
    """ToolCall accepts a custom agent_id."""
    tc = ToolCall(
        tool_name="query_database",
        parameters={"table": "users"},
        agent_id="finance-agent",
    )

    assert tc.agent_id == "finance-agent"


def test_tool_call_empty_parameters():
    """ToolCall works with empty parameters dict."""
    tc = ToolCall(tool_name="list_files", parameters={})

    assert tc.parameters == {}


# --- Policy tests ---


def test_policy_creation():
    """Policy can be created with all required fields."""
    policy = Policy(
        id="fin-001",
        category="financial",
        risk_level="high",
        applicable_tools=["transfer_funds", "approve_payment"],
        source="EU AI Act - High-Risk Systems",
        content="Agents must not execute transactions exceeding €500.",
        file_path="policies/documents/fin-001-transaction-limits.md",
    )

    assert policy.id == "fin-001"
    assert policy.category == "financial"
    assert policy.risk_level == "high"
    assert len(policy.applicable_tools) == 2
    assert "transfer_funds" in policy.applicable_tools


def test_policy_match_creation():
    """PolicyMatch captures a RAG retrieval result."""
    match = PolicyMatch(
        policy_id="fin-001",
        category="financial",
        relevance_score=0.85,
        matched_chunk="Agents must not execute transactions exceeding €500.",
    )

    assert match.policy_id == "fin-001"
    assert match.relevance_score == 0.85


# --- Verdict tests ---


def _make_verdict(**overrides):
    """Helper to create a Verdict with sensible defaults.

    This avoids repeating all required fields in every test.
    Override any field by passing it as a keyword argument.
    """
    defaults = {
        "decision": "ALLOW",
        "tool_call": ToolCall(
            tool_name="transfer_funds", parameters={"amount": 50}
        ),
        "matched_policies": [],
        "reasoning": "Amount within limits.",
        "decision_source": "rule",
        "retrieval_score": None,
        "policy_coverage": 0,
        "provider": "none",
        "evaluation_ms": 0,
    }
    defaults.update(overrides)
    return Verdict(**defaults)


def test_verdict_allow():
    """ALLOW verdict from a rule-based decision."""
    v = _make_verdict()

    assert v.decision == "ALLOW"
    assert v.decision_source == "rule"
    assert v.fallback_reason is None


def test_verdict_block_with_policies():
    """BLOCK verdict with matched policies from LLM evaluation."""
    match = PolicyMatch(
        policy_id="fin-001",
        category="financial",
        relevance_score=0.92,
        matched_chunk="Exceeding €500 requires human approval.",
    )
    v = _make_verdict(
        decision="BLOCK",
        matched_policies=[match],
        reasoning="Amount exceeds limit.",
        decision_source="llm",
        retrieval_score=0.92,
        policy_coverage=1,
        provider="mistral",
        evaluation_ms=234,
    )

    assert v.decision == "BLOCK"
    assert v.decision_source == "llm"
    assert len(v.matched_policies) == 1
    assert v.matched_policies[0].policy_id == "fin-001"
    assert v.provider == "mistral"


def test_verdict_flag_fallback():
    """FLAG verdict from fallback when LLM fails."""
    v = _make_verdict(
        decision="FLAG",
        decision_source="fallback",
        fallback_reason="LLM returned unparseable output.",
        provider="mistral",
        evaluation_ms=512,
    )

    assert v.decision == "FLAG"
    assert v.decision_source == "fallback"
    assert v.fallback_reason == "LLM returned unparseable output."


def test_verdict_invalid_decision():
    """Invalid decision value raises ValueError."""
    with pytest.raises(ValueError, match="Invalid decision"):
        _make_verdict(decision="MAYBE")


def test_verdict_invalid_source():
    """Invalid decision_source value raises ValueError."""
    with pytest.raises(ValueError, match="Invalid decision_source"):
        _make_verdict(decision_source="magic")


def test_verdict_timestamp_auto_generated():
    """Verdict timestamp is auto-generated if not provided."""
    v = _make_verdict()

    assert isinstance(v.timestamp, datetime)


# --- Config tests ---


def test_config_default_provider_falls_back_to_mistral(monkeypatch):
    """
    get_provider_name() falls back to 'mistral' when THRESHIA_PROVIDER isn't
    set, regardless of what the developer's local .env contains.

    Calls get_provider_name() directly rather than reloading threshia.config
    — reloading would re-run load_dotenv(), which silently re-populates
    THRESHIA_PROVIDER from .env even after monkeypatch.delenv() clears it,
    making a reload-based version of this test unreliable.
    """
    from threshia.config import get_provider_name

    monkeypatch.delenv("THRESHIA_PROVIDER", raising=False)
    assert get_provider_name() == "mistral"


def test_config_policies_dir_exists():
    """Policies directory path is correctly constructed."""
    assert "policies" in str(POLICIES_DIR)
    assert "documents" in str(POLICIES_DIR)


def test_config_top_k():
    """TOP_K_POLICIES has a sensible default."""
    assert TOP_K_POLICIES == 5
    assert isinstance(TOP_K_POLICIES, int)
