"""
Tests for threshia.execution.guard.governed_execute.

Uses the real, loaded repository policy set (not fixtures), consistent
with tests/test_engine.py.
"""

from unittest.mock import patch

import pytest

from threshia.audit.logger import AuditConfig, read_audit_log
from threshia.engine.evaluator import SemanticConfig
from threshia.execution.guard import governed_execute
from threshia.execution.result import ExecutionResult
from threshia.models.policy import PolicyMatch
from threshia.models.tool_call import ToolCall
from threshia.policies.loader import load_all_policies


@pytest.fixture(scope="module")
def policies():
    return load_all_policies()


class _RecordingExecutor:
    """A minimal callable executor that records every invocation."""

    def __init__(self, return_value=None):
        self.return_value = return_value
        self.calls: list[ToolCall] = []

    def __call__(self, tool_call: ToolCall):
        self.calls.append(tool_call)
        return self.return_value


# --- ALLOW: executor invoked exactly once ---


def test_allow_direct_policy_match_executes_once_and_preserves_result(policies):
    call = ToolCall(tool_name="ERP.InvoiceLookup", parameters={})
    executor = _RecordingExecutor(return_value={"status": "ok"})

    outcome = governed_execute(call, policies, executor)

    assert outcome.status == "EXECUTED"
    assert outcome.executed is True
    assert outcome.result == {"status": "ok"}
    assert outcome.verdict.decision == "ALLOW"
    assert executor.calls == [call]


def test_allow_gated_action_with_literal_true_approval_executes_once(policies):
    call = ToolCall(
        tool_name="ERP.PaymentReviewTrigger",
        parameters={"human_approval_evidenced": True},
    )
    executor = _RecordingExecutor(return_value="done")

    outcome = governed_execute(call, policies, executor)

    assert outcome.status == "EXECUTED"
    assert outcome.executed is True
    assert outcome.result == "done"
    assert outcome.verdict.decision == "ALLOW"
    assert len(executor.calls) == 1
    assert executor.calls[0] is call


# --- BLOCK: never-permitted, executor never called ---


def test_block_never_permitted_action_never_executes(policies):
    call = ToolCall(tool_name="release_payment", parameters={})
    executor = _RecordingExecutor()

    outcome = governed_execute(call, policies, executor)

    assert outcome.status == "DENIED"
    assert outcome.executed is False
    assert outcome.result is None
    assert outcome.verdict.decision == "BLOCK"
    assert executor.calls == []


# --- FLAG: gating without approval evidence ---


def test_flag_gated_action_without_evidence_never_executes(policies):
    call = ToolCall(tool_name="ERP.PaymentReviewTrigger", parameters={})
    executor = _RecordingExecutor()

    outcome = governed_execute(call, policies, executor)

    assert outcome.status == "REVIEW_REQUIRED"
    assert outcome.executed is False
    assert outcome.result is None
    assert outcome.verdict.decision == "FLAG"
    assert executor.calls == []


# --- FLAG: uncovered semantic path ---


def test_flag_uncovered_tool_semantic_provider_allow_never_executes(policies):
    """
    The core enforcement safety regression: a provider suggesting ALLOW
    for an uncovered tool must never reach the executor, because the
    authoritative verdict stays FLAG (see threshia/models/verdict.py:
    only explicit deterministic policy coverage may produce ALLOW).
    """
    call = ToolCall(tool_name="Sales.CreateDiscountOffer", parameters={})
    executor = _RecordingExecutor()

    with (
        patch("threshia.providers.mistral_provider.MISTRAL_API_KEY", "test-key"),
        patch("threshia.policies.vector_store.build_index"),
        patch(
            "threshia.policies.vector_store.retrieve",
            return_value=[
                PolicyMatch(
                    policy_id="erp-controlled-actions-001",
                    category="financial",
                    relevance_score=0.5,
                    matched_chunk="current policy context",
                )
            ],
        ),
        patch(
            "threshia.providers.mistral_provider.call_mistral",
            return_value={"decision": "ALLOW", "reasoning": "Looks like a safe read."},
        ),
    ):
        outcome = governed_execute(call, policies, executor)

    assert outcome.status == "REVIEW_REQUIRED"
    assert outcome.verdict.decision == "FLAG"
    assert outcome.verdict.provider_suggested_decision == "ALLOW"
    assert executor.calls == []


def test_flag_uncovered_tool_no_provider_configured_never_executes(policies):
    """No API key configured (the conftest default) — semantic layer is
    skipped entirely and the tool falls back to the standard rule FLAG."""
    call = ToolCall(tool_name="Sales.CreateDiscountOffer", parameters={})
    executor = _RecordingExecutor()

    outcome = governed_execute(call, policies, executor)

    assert outcome.status == "REVIEW_REQUIRED"
    assert outcome.verdict.decision == "FLAG"
    assert outcome.verdict.decision_source == "rule"
    assert executor.calls == []


# --- Executor failure ---


def test_executor_failure_propagates_and_is_not_retried(policies):
    call = ToolCall(tool_name="ERP.InvoiceLookup", parameters={})
    calls: list[ToolCall] = []

    def failing_executor(tool_call: ToolCall):
        calls.append(tool_call)
        raise RuntimeError("downstream tool failed")

    with pytest.raises(RuntimeError, match="downstream tool failed"):
        governed_execute(call, policies, failing_executor)

    # Governance decision was ALLOW and the executor really was invoked —
    # the exception is a distinct execution failure, not a governance
    # denial, and it was not retried.
    assert len(calls) == 1


# --- No double execution ---


def test_executor_is_never_invoked_more_than_once_across_all_verdicts(policies):
    scenarios = [
        ToolCall(tool_name="ERP.InvoiceLookup", parameters={}),  # ALLOW
        ToolCall(tool_name="release_payment", parameters={}),  # BLOCK
        ToolCall(tool_name="ERP.PaymentReviewTrigger", parameters={}),  # FLAG
    ]

    for call in scenarios:
        executor = _RecordingExecutor()
        governed_execute(call, policies, executor)
        assert len(executor.calls) <= 1


# --- ExecutionResult invariants ---


def test_execution_result_rejects_inconsistent_status_and_decision(policies):
    call = ToolCall(tool_name="ERP.InvoiceLookup", parameters={})
    verdict = governed_execute(call, policies, _RecordingExecutor()).verdict

    with pytest.raises(ValueError):
        ExecutionResult(status="DENIED", verdict=verdict, executed=False)


def test_execution_result_rejects_executed_status_mismatch(policies):
    call = ToolCall(tool_name="ERP.InvoiceLookup", parameters={})
    verdict = governed_execute(call, policies, _RecordingExecutor()).verdict

    with pytest.raises(ValueError):
        ExecutionResult(status="EXECUTED", verdict=verdict, executed=False)


# --- Audit integration ---


def test_no_audit_entry_written_when_audit_config_not_requested(tmp_path, policies):
    log_path = tmp_path / "audit.jsonl"
    call = ToolCall(tool_name="ERP.InvoiceLookup", parameters={})

    governed_execute(call, policies, _RecordingExecutor(), audit_log_path=log_path)

    assert not log_path.exists()


def test_exactly_one_audit_entry_written_when_requested(tmp_path, policies):
    log_path = tmp_path / "audit.jsonl"
    call = ToolCall(tool_name="ERP.InvoiceLookup", parameters={})

    governed_execute(
        call,
        policies,
        _RecordingExecutor(),
        audit_config=AuditConfig(),
        audit_log_path=log_path,
    )

    entries = read_audit_log(log_path=log_path)
    assert len(entries) == 1
    assert entries[0]["decision"] == "ALLOW"


def test_audit_parameter_allowlist_is_honored_through_the_execution_boundary(
    tmp_path, policies
):
    log_path = tmp_path / "audit.jsonl"
    call = ToolCall(
        tool_name="ERP.InvoiceLookup",
        parameters={"invoice_id": "INV-1", "salary": "FAKE-SECRET-VALUE"},
    )

    governed_execute(
        call,
        policies,
        _RecordingExecutor(),
        audit_config=AuditConfig(parameter_allowlist=frozenset({"invoice_id"})),
        audit_log_path=log_path,
    )

    entry = read_audit_log(log_path=log_path)[0]
    assert entry["tool_call"]["parameters"] == {"invoice_id": "INV-1"}
    assert "FAKE-SECRET-VALUE" not in log_path.read_text(encoding="utf-8")


def test_block_and_flag_are_auditable_even_though_executor_never_ran(tmp_path, policies):
    log_path = tmp_path / "audit.jsonl"
    executor = _RecordingExecutor()

    governed_execute(
        ToolCall(tool_name="release_payment", parameters={}),
        policies,
        executor,
        audit_config=AuditConfig(),
        audit_log_path=log_path,
    )
    governed_execute(
        ToolCall(tool_name="ERP.PaymentReviewTrigger", parameters={}),
        policies,
        executor,
        audit_config=AuditConfig(),
        audit_log_path=log_path,
    )

    entries = read_audit_log(log_path=log_path)
    assert [e["decision"] for e in entries] == ["BLOCK", "FLAG"]
    assert executor.calls == []


def test_audit_entry_for_allow_is_written_even_if_executor_later_fails(tmp_path, policies):
    """
    An ALLOW audit entry records authorization, not execution success.

    The audit entry must still exist if the executor subsequently raises.
    """
    log_path = tmp_path / "audit.jsonl"
    call = ToolCall(tool_name="ERP.InvoiceLookup", parameters={})

    def failing_executor(tool_call: ToolCall):
        raise RuntimeError("downstream tool failed")

    with pytest.raises(RuntimeError):
        governed_execute(
            call,
            policies,
            failing_executor,
            audit_config=AuditConfig(),
            audit_log_path=log_path,
        )

    entries = read_audit_log(log_path=log_path)
    assert len(entries) == 1
    assert entries[0]["decision"] == "ALLOW"


# --- SemanticConfig pass-through ---

_SEMANTIC_SENSITIVE_PARAMETERS = {
    "salary": 123456,
    "medical_note": "synthetic-medical-value",
    "ticket_id": "TCK-777",
}


def _uncovered_semantic_call(parameters):
    return ToolCall(tool_name="Sales.CreateDiscountOffer", parameters=parameters)


def test_default_semantic_path_sends_no_parameters_through_governed_execute(policies):
    """
    No semantic_config: governed_execute() must exhibit exactly the same
    deny-by-default outbound behavior as evaluate() does directly — no
    arbitrary parameter names or values reach the provider, the
    authoritative verdict stays FLAG, and the executor is never called.
    """
    call = _uncovered_semantic_call(dict(_SEMANTIC_SENSITIVE_PARAMETERS))
    executor = _RecordingExecutor()
    captured = {}

    def fake_call_mistral(tool_name, parameters, retrieved_policy_texts, timeout=20):
        captured["parameters"] = parameters
        return {"decision": "FLAG", "reasoning": "n/a"}

    with (
        patch("threshia.providers.mistral_provider.MISTRAL_API_KEY", "test-key"),
        patch("threshia.policies.vector_store.build_index"),
        patch(
            "threshia.policies.vector_store.retrieve",
            return_value=[
                PolicyMatch(
                    policy_id="erp-controlled-actions-001",
                    category="financial",
                    relevance_score=0.5,
                    matched_chunk="current policy context",
                )
            ],
        ),
        patch("threshia.providers.mistral_provider.call_mistral", side_effect=fake_call_mistral),
    ):
        outcome = governed_execute(call, policies, executor)

    assert captured["parameters"] == {}
    assert set(captured["parameters"]).isdisjoint(_SEMANTIC_SENSITIVE_PARAMETERS)
    assert outcome.status == "REVIEW_REQUIRED"
    assert outcome.verdict.decision == "FLAG"
    assert executor.calls == []


def test_explicit_allowlist_through_governed_execute(policies):
    """
    An allowlisted key reaches the provider through governed_execute();
    non-allowlisted synthetic sensitive fields do not, and the original
    ToolCall.parameters is left unmodified.
    """
    call = _uncovered_semantic_call(dict(_SEMANTIC_SENSITIVE_PARAMETERS))
    original_parameters = dict(call.parameters)
    executor = _RecordingExecutor()
    captured = {}

    def fake_call_mistral(tool_name, parameters, retrieved_policy_texts, timeout=20):
        captured["parameters"] = parameters
        return {"decision": "FLAG", "reasoning": "n/a"}

    with (
        patch("threshia.providers.mistral_provider.MISTRAL_API_KEY", "test-key"),
        patch("threshia.policies.vector_store.build_index"),
        patch(
            "threshia.policies.vector_store.retrieve",
            return_value=[
                PolicyMatch(
                    policy_id="erp-controlled-actions-001",
                    category="financial",
                    relevance_score=0.5,
                    matched_chunk="current policy context",
                )
            ],
        ),
        patch("threshia.providers.mistral_provider.call_mistral", side_effect=fake_call_mistral),
    ):
        outcome = governed_execute(
            call,
            policies,
            executor,
            semantic_config=SemanticConfig(parameter_allowlist=frozenset({"ticket_id"})),
        )

    assert captured["parameters"] == {"ticket_id": "TCK-777"}
    assert "salary" not in captured["parameters"]
    assert "medical_note" not in captured["parameters"]
    assert call.parameters == original_parameters
    assert outcome.status == "REVIEW_REQUIRED"
    assert executor.calls == []


def test_semantic_allow_suggestion_still_cannot_execute_through_governed_execute(policies):
    """Authorization safety, exercised through the enforcement boundary:
    a provider ALLOW suggestion for an uncovered tool must never reach
    the executor, even with an allowlisted parameter in play."""
    call = _uncovered_semantic_call({"ticket_id": "TCK-1"})
    executor = _RecordingExecutor()

    with (
        patch("threshia.providers.mistral_provider.MISTRAL_API_KEY", "test-key"),
        patch("threshia.policies.vector_store.build_index"),
        patch(
            "threshia.policies.vector_store.retrieve",
            return_value=[
                PolicyMatch(
                    policy_id="erp-controlled-actions-001",
                    category="financial",
                    relevance_score=0.5,
                    matched_chunk="current policy context",
                )
            ],
        ),
        patch(
            "threshia.providers.mistral_provider.call_mistral",
            return_value={"decision": "ALLOW", "reasoning": "Looks like a safe read."},
        ),
    ):
        outcome = governed_execute(
            call,
            policies,
            executor,
            semantic_config=SemanticConfig(parameter_allowlist=frozenset({"ticket_id"})),
        )

    assert outcome.status == "REVIEW_REQUIRED"
    assert outcome.verdict.decision == "FLAG"
    assert outcome.verdict.provider_suggested_decision == "ALLOW"
    assert executor.calls == []


def test_semantic_config_does_not_interfere_with_covered_deterministic_execution(policies):
    """A directly covered tool's deterministic ALLOW/executor behavior
    must be unaffected by any semantic_config, and the semantic provider
    must not be consulted at all for a covered tool."""
    call = ToolCall(tool_name="ERP.InvoiceLookup", parameters={})
    executor = _RecordingExecutor(return_value="done")

    with (
        patch("threshia.policies.vector_store.build_index") as mock_build,
        patch("threshia.policies.vector_store.retrieve") as mock_retrieve,
        patch("threshia.providers.mistral_provider.call_mistral") as mock_provider,
    ):
        outcome = governed_execute(
            call,
            policies,
            executor,
            semantic_config=SemanticConfig(parameter_allowlist=frozenset({"ticket_id"})),
        )

    assert outcome.status == "EXECUTED"
    assert outcome.executed is True
    assert outcome.result == "done"
    assert outcome.verdict.decision == "ALLOW"
    assert executor.calls == [call]
    mock_build.assert_not_called()
    mock_retrieve.assert_not_called()
    mock_provider.assert_not_called()


def test_semantic_and_audit_allowlists_are_independent_through_governed_execute(tmp_path, policies):
    """
    SemanticConfig and AuditConfig are separate trust boundaries: a key
    allowlisted for the provider is not implicitly allowlisted for audit
    persistence. ticket_id crosses the provider boundary here but must
    still be absent from the persisted audit record under a default
    (empty) AuditConfig.
    """
    log_path = tmp_path / "audit.jsonl"
    call = _uncovered_semantic_call({"ticket_id": "TCK-777"})
    executor = _RecordingExecutor()
    captured = {}

    def fake_call_mistral(tool_name, parameters, retrieved_policy_texts, timeout=20):
        captured["parameters"] = parameters
        return {"decision": "FLAG", "reasoning": "Needs human review."}

    with (
        patch("threshia.providers.mistral_provider.MISTRAL_API_KEY", "test-key"),
        patch("threshia.policies.vector_store.build_index"),
        patch(
            "threshia.policies.vector_store.retrieve",
            return_value=[
                PolicyMatch(
                    policy_id="erp-controlled-actions-001",
                    category="financial",
                    relevance_score=0.5,
                    matched_chunk="current policy context",
                )
            ],
        ),
        patch("threshia.providers.mistral_provider.call_mistral", side_effect=fake_call_mistral),
    ):
        governed_execute(
            call,
            policies,
            executor,
            semantic_config=SemanticConfig(parameter_allowlist=frozenset({"ticket_id"})),
            audit_config=AuditConfig(),  # default: empty parameter_allowlist
            audit_log_path=log_path,
        )

    # Crossed the provider boundary (explicitly allowlisted there).
    assert captured["parameters"] == {"ticket_id": "TCK-777"}

    # Did NOT cross the separate audit boundary (not allowlisted there).
    entry = read_audit_log(log_path=log_path)[0]
    assert entry["tool_call"]["parameters"] == {}
    assert "TCK-777" not in log_path.read_text(encoding="utf-8")
