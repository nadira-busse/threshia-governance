"""
Tests for threshia.engine.evaluator.

Uses the real, loaded Kelvior policy set (not fixtures) so these tests
double as an integration check: if a policy document's wording changes
in a way that breaks parsing or matching, these tests catch it.
"""

from unittest.mock import patch

import pytest

from threshia.engine.evaluator import evaluate
from threshia.models.tool_call import ToolCall
from threshia.policies.loader import load_all_policies


@pytest.fixture(scope="module")
def policies():
    return load_all_policies()


# --- Never-permitted actions: BLOCK regardless of context ---

def test_blocks_never_permitted_erp_action(policies):
    call = ToolCall(tool_name="release_payment", parameters={})
    verdict = evaluate(call, policies)

    assert verdict.decision == "BLOCK"
    assert verdict.decision_source == "rule"
    assert verdict.matched_policies[0].policy_id == "erp-controlled-actions-001"


def test_blocks_never_permitted_hr_action(policies):
    call = ToolCall(tool_name="access_medical_or_absence_records", parameters={})
    verdict = evaluate(call, policies)

    assert verdict.decision == "BLOCK"
    assert verdict.matched_policies[0].policy_id == "hr-restricted-data-001"


def test_blocks_never_permitted_itsm_action(policies):
    call = ToolCall(tool_name="modify_production_system", parameters={})
    verdict = evaluate(call, policies)

    assert verdict.decision == "BLOCK"
    assert verdict.matched_policies[0].policy_id == "itsm-readonly-001"


def test_block_overrides_even_with_approval_evidence(policies):
    """A never-permitted action stays blocked even if the caller claims
    human approval — approval cannot authorize a permanently blocked action."""
    call = ToolCall(
        tool_name="approve_payment",
        parameters={"human_approval_evidenced": True},
    )
    verdict = evaluate(call, policies)
    assert verdict.decision == "BLOCK"


# --- Read-only / unconditionally allowed tools ---

def test_allows_erp_readonly_lookup(policies):
    call = ToolCall(tool_name="ERP.InvoiceLookup", parameters={})
    verdict = evaluate(call, policies)

    assert verdict.decision == "ALLOW"
    assert verdict.policy_coverage == 1


def test_allows_itsm_classification_without_approval_evidence(policies):
    """ITSM tools are never gated — no approval field needed at all."""
    call = ToolCall(tool_name="ITSM.ClassificationSuggest", parameters={})
    verdict = evaluate(call, policies)
    assert verdict.decision == "ALLOW"


# --- Gated tools: FLAG without evidence, ALLOW with evidence ---

def test_flags_gated_erp_action_without_evidence(policies):
    call = ToolCall(tool_name="ERP.PaymentReviewTrigger", parameters={})
    verdict = evaluate(call, policies)

    assert verdict.decision == "FLAG"
    assert "approval" in verdict.reasoning.lower()


def test_allows_gated_erp_action_with_evidence(policies):
    call = ToolCall(
        tool_name="ERP.PaymentReviewTrigger",
        parameters={"human_approval_evidenced": True},
    )
    verdict = evaluate(call, policies)
    assert verdict.decision == "ALLOW"


def test_flags_gated_hr_lookup_without_evidence(policies):
    call = ToolCall(tool_name="HR.EmployeeProfileLookup", parameters={})
    verdict = evaluate(call, policies)
    assert verdict.decision == "FLAG"


def test_allows_gated_hr_lookup_with_evidence(policies):
    call = ToolCall(
        tool_name="HR.TrainingStatusLookup",
        parameters={"human_approval_evidenced": True},
    )
    verdict = evaluate(call, policies)
    assert verdict.decision == "ALLOW"


# --- Unknown tools: fail-safe FLAG ---

def test_flags_unknown_tool_not_covered_by_any_policy(policies):
    """
    An unknown tool with the semantic layer unavailable defaults to FLAG.

    Mocks _try_semantic_evaluation directly (returning None, meaning "not
    attempted") rather than relying only on conftest.py's global API-key
    patching. This test's guarantee — no direct policy coverage AND no
    semantic verdict leads to a rule-based FLAG — should hold regardless
    of how the semantic layer happens to be unavailable.
    """
    with patch(
        "threshia.engine.evaluator._try_semantic_evaluation", return_value=None
    ) as mock_semantic:
        call = ToolCall(tool_name="CRM.DeleteAllCustomers", parameters={})
        verdict = evaluate(call, policies)

    assert verdict.decision == "FLAG"
    assert verdict.decision_source == "rule"
    assert verdict.policy_coverage == 0
    assert "no loaded policy covers" in verdict.reasoning.lower()
    mock_semantic.assert_called_once()


# --- Verdict metadata sanity checks ---

def test_verdict_records_evaluation_time(policies):
    call = ToolCall(tool_name="ERP.InvoiceLookup", parameters={})
    verdict = evaluate(call, policies)
    assert verdict.evaluation_ms >= 0
    assert verdict.provider == "none"
    assert verdict.decision_source == "rule"
