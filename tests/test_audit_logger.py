"""Tests for threshia.audit.logger."""

import json
from unittest.mock import patch

from threshia.audit.logger import AuditConfig, log_verdict, read_audit_log
from threshia.engine.evaluator import evaluate, evaluate_and_log
from threshia.models.policy import PolicyMatch
from threshia.models.tool_call import ToolCall
from threshia.policies.loader import load_all_policies


def test_log_verdict_writes_one_json_line(tmp_path):
    log_path = tmp_path / "audit.jsonl"
    policies = load_all_policies()
    call = ToolCall(tool_name="ERP.InvoiceLookup", parameters={})
    verdict = evaluate(call, policies)

    log_verdict(verdict, log_path=log_path)

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["decision"] == "ALLOW"
    assert entry["tool_call"]["tool_name"] == "ERP.InvoiceLookup"


def test_log_verdict_appends_across_multiple_calls(tmp_path):
    log_path = tmp_path / "audit.jsonl"
    policies = load_all_policies()

    call_a = ToolCall(tool_name="ERP.InvoiceLookup", parameters={})
    call_b = ToolCall(tool_name="release_payment", parameters={})

    log_verdict(evaluate(call_a, policies), log_path=log_path)
    log_verdict(evaluate(call_b, policies), log_path=log_path)

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    decisions = [json.loads(line)["decision"] for line in lines]
    assert decisions == ["ALLOW", "BLOCK"]


def test_log_verdict_creates_parent_directory(tmp_path):
    log_path = tmp_path / "nested" / "dir" / "audit.jsonl"
    policies = load_all_policies()
    call = ToolCall(tool_name="ITSM.IncidentLookup", parameters={})

    log_verdict(evaluate(call, policies), log_path=log_path)

    assert log_path.exists()


def test_read_audit_log_returns_empty_list_when_missing(tmp_path):
    missing_path = tmp_path / "does_not_exist.jsonl"
    assert read_audit_log(log_path=missing_path) == []


def test_read_audit_log_round_trips_entries(tmp_path):
    log_path = tmp_path / "audit.jsonl"
    policies = load_all_policies()
    call = ToolCall(
        tool_name="ERP.PaymentReviewTrigger",
        parameters={"human_approval_evidenced": True},
    )
    log_verdict(evaluate(call, policies), log_path=log_path)

    entries = read_audit_log(log_path=log_path)

    assert len(entries) == 1
    assert entries[0]["decision"] == "ALLOW"
    assert entries[0]["decision_source"] == "rule"


def test_evaluate_and_log_writes_to_configured_audit_path(tmp_path, monkeypatch):
    """
    evaluate_and_log() should use the real AUDIT_LOG_PATH from config by
    default. We redirect that config value to a temp path so this test
    never touches the project's actual audit.jsonl.
    """
    import threshia.audit.logger as logger_module

    temp_log = tmp_path / "audit.jsonl"
    monkeypatch.setattr(logger_module, "AUDIT_LOG_PATH", temp_log)

    policies = load_all_policies()
    call = ToolCall(tool_name="ERP.InvoiceLookup", parameters={})

    verdict = evaluate_and_log(call, policies)

    assert verdict.decision == "ALLOW"
    assert temp_log.exists()
    assert len(read_audit_log(log_path=temp_log)) == 1


def test_semantic_infrastructure_fallback_serializes_to_audit_log(tmp_path):
    log_path = tmp_path / "audit.jsonl"
    policies = load_all_policies()
    call = ToolCall(tool_name="Sales.CreateDiscountOffer", parameters={})

    with (
        patch("threshia.providers.mistral_provider.MISTRAL_API_KEY", "test-key"),
        patch(
            "threshia.policies.vector_store.build_index",
            side_effect=RuntimeError("index unavailable"),
        ),
    ):
        verdict = evaluate(call, policies)

    log_verdict(verdict, log_path=log_path)
    entry = read_audit_log(log_path=log_path)[0]

    assert entry["decision"] == "FLAG"
    assert entry["decision_source"] == "fallback"
    assert entry["fallback_reason"] == "index unavailable"


def test_uncovered_tool_provider_allow_logs_as_flag_not_allow(tmp_path):
    """
    Audit-consistency check: when a provider suggests ALLOW for an
    uncovered tool, the persisted log entry's authoritative `decision`
    field must read FLAG, never ALLOW — and the provider's actual
    suggestion must still be readable in the same entry, distinctly, via
    `provider_suggested_decision`. A reviewer scanning audit.jsonl for
    ALLOW entries must never encounter this case under "decision": "ALLOW".
    """
    log_path = tmp_path / "audit.jsonl"
    policies = load_all_policies()
    call = ToolCall(tool_name="Sales.CreateDiscountOffer", parameters={})

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
        verdict = evaluate(call, policies)

    assert verdict.decision == "FLAG"  # sanity check on the object before serializing

    log_verdict(verdict, log_path=log_path)
    entry = read_audit_log(log_path=log_path)[0]

    assert entry["decision"] == "FLAG"
    assert entry["decision"] != "ALLOW"
    assert entry["decision_source"] == "llm"
    assert entry["provider_suggested_decision"] == "ALLOW"
    assert "Looks like a safe read." in entry["reasoning"]


# --- Parameter data minimization ---

SYNTHETIC_SENSITIVE_PARAMETERS = {
    "salary": 123456,
    "medical_note": "synthetic-medical-value",
    "email": "fake@example.invalid",
    "iban": "TEST-IBAN-000",
    "access_token": "dummy-token-value",
    "invoice_id": "INV-123",
}


def test_log_verdict_excludes_parameters_by_default(tmp_path):
    """
    No parameter value survives into persisted JSONL by default — the
    default AuditConfig has an empty allowlist.
    """
    log_path = tmp_path / "audit.jsonl"
    policies = load_all_policies()
    call = ToolCall(
        tool_name="HR.EmployeeProfileLookup",
        parameters={**SYNTHETIC_SENSITIVE_PARAMETERS, "human_approval_evidenced": True},
    )

    log_verdict(evaluate(call, policies), log_path=log_path)

    raw_text = log_path.read_text(encoding="utf-8")
    for value in [
        123456,
        "synthetic-medical-value",
        "fake@example.invalid",
        "TEST-IBAN-000",
        "dummy-token-value",
        "INV-123",
    ]:
        assert str(value) not in raw_text

    entry = json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])
    assert entry["tool_call"]["parameters"] == {}


def test_log_verdict_default_still_preserves_governance_metadata(tmp_path):
    """Excluding parameters must not remove decision-relevant metadata."""
    log_path = tmp_path / "audit.jsonl"
    policies = load_all_policies()
    call = ToolCall(
        tool_name="ERP.PaymentReviewTrigger",
        parameters={"human_approval_evidenced": True},
        agent_id="finance-invoice-agent",
    )

    log_verdict(evaluate(call, policies), log_path=log_path)
    entry = read_audit_log(log_path=log_path)[0]

    assert entry["decision"] == "ALLOW"
    assert entry["decision_source"] == "rule"
    assert entry["provider"] == "none"
    assert entry["policy_coverage"] == 1
    assert isinstance(entry["evaluation_ms"], int)
    assert entry["tool_call"]["tool_name"] == "ERP.PaymentReviewTrigger"
    assert entry["tool_call"]["agent_id"] == "finance-invoice-agent"
    assert entry["matched_policies"][0]["policy_id"] == "erp-controlled-actions-001"
    assert entry["human_approval_evidenced"] is True


def test_log_verdict_allowlist_persists_only_named_keys(tmp_path):
    log_path = tmp_path / "audit.jsonl"
    policies = load_all_policies()
    call = ToolCall(
        tool_name="HR.EmployeeProfileLookup",
        parameters={**SYNTHETIC_SENSITIVE_PARAMETERS, "ticket_id": "TCK-9"},
    )
    config = AuditConfig(parameter_allowlist=frozenset({"invoice_id", "ticket_id"}))

    log_verdict(evaluate(call, policies), log_path=log_path, config=config)
    entry = read_audit_log(log_path=log_path)[0]

    assert entry["tool_call"]["parameters"] == {"invoice_id": "INV-123", "ticket_id": "TCK-9"}
    for key in SYNTHETIC_SENSITIVE_PARAMETERS:
        if key not in ("invoice_id",):
            assert key not in entry["tool_call"]["parameters"]


def test_log_verdict_allowlist_ignores_missing_keys(tmp_path):
    """An allowlisted key absent from this call's parameters is not an error."""
    log_path = tmp_path / "audit.jsonl"
    policies = load_all_policies()
    call = ToolCall(tool_name="ERP.InvoiceLookup", parameters={"invoice_id": "INV-1"})
    config = AuditConfig(parameter_allowlist=frozenset({"invoice_id", "ticket_id"}))

    log_verdict(evaluate(call, policies), log_path=log_path, config=config)
    entry = read_audit_log(log_path=log_path)[0]

    assert entry["tool_call"]["parameters"] == {"invoice_id": "INV-1"}


def test_log_verdict_empty_allowlist_behaves_like_default(tmp_path):
    log_path = tmp_path / "audit.jsonl"
    policies = load_all_policies()
    call = ToolCall(tool_name="ERP.InvoiceLookup", parameters={"invoice_id": "INV-1"})

    log_verdict(
        evaluate(call, policies),
        log_path=log_path,
        config=AuditConfig(parameter_allowlist=frozenset()),
    )
    entry = read_audit_log(log_path=log_path)[0]

    assert entry["tool_call"]["parameters"] == {}


def test_audit_config_does_not_change_the_verdict(tmp_path, monkeypatch):
    """AuditConfig controls persistence only — never the evaluated decision."""
    import threshia.audit.logger as logger_module

    temp_log = tmp_path / "audit.jsonl"
    monkeypatch.setattr(logger_module, "AUDIT_LOG_PATH", temp_log)

    policies = load_all_policies()
    call = ToolCall(
        tool_name="ERP.PaymentReviewTrigger",
        parameters={"human_approval_evidenced": True},
    )

    plain_verdict = evaluate(call, policies)
    logged_verdict = evaluate_and_log(
        call, policies, audit_config=AuditConfig(parameter_allowlist=frozenset({"nope"}))
    )

    assert logged_verdict.decision == plain_verdict.decision
    assert logged_verdict.decision_source == plain_verdict.decision_source
    assert logged_verdict.tool_call.parameters == call.parameters


def test_semantic_advisory_audit_excludes_parameters(tmp_path):
    """
    An uncovered semantic call must log the authoritative FLAG, the
    provider's suggestion, and no unapproved arbitrary parameters.
    """
    log_path = tmp_path / "audit.jsonl"
    policies = load_all_policies()
    call = ToolCall(
        tool_name="Sales.CreateDiscountOffer",
        parameters={"customer_email": "fake.customer@example.invalid"},
    )

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
        verdict = evaluate(call, policies)

    log_verdict(verdict, log_path=log_path)
    entry = read_audit_log(log_path=log_path)[0]

    assert entry["decision"] == "FLAG"
    assert entry["provider_suggested_decision"] == "ALLOW"
    assert entry["tool_call"]["parameters"] == {}
    assert "fake.customer@example.invalid" not in json.dumps(entry)


def test_fallback_diagnostics_remain_auditable_without_parameters(tmp_path):
    log_path = tmp_path / "audit.jsonl"
    policies = load_all_policies()
    call = ToolCall(
        tool_name="Sales.CreateDiscountOffer",
        parameters={"internal_note": "synthetic-note-value"},
    )

    with (
        patch("threshia.providers.mistral_provider.MISTRAL_API_KEY", "test-key"),
        patch(
            "threshia.policies.vector_store.build_index",
            side_effect=RuntimeError("index unavailable"),
        ),
    ):
        verdict = evaluate(call, policies)

    log_verdict(verdict, log_path=log_path)
    entry = read_audit_log(log_path=log_path)[0]

    assert entry["decision"] == "FLAG"
    assert entry["decision_source"] == "fallback"
    assert entry["fallback_reason"] == "index unavailable"
    assert entry["tool_call"]["parameters"] == {}


def test_synthetic_sensitive_exposure_regression(tmp_path):
    """
    Before AuditConfig existed, log_verdict() persisted the full
    ToolCall.parameters dict verbatim, so any synthetic sensitive-looking
    value below would have reached audit.jsonl unredacted. This regression
    proves the opposite: none of those values, including invoice_id,
    appear by default. With an allowlist of {"invoice_id"}, only that
    value may appear. All values here are fake/synthetic.
    """
    log_path = tmp_path / "audit.jsonl"
    policies = load_all_policies()
    call = ToolCall(
        tool_name="HR.EmployeeProfileLookup",
        parameters=dict(SYNTHETIC_SENSITIVE_PARAMETERS),
    )
    verdict = evaluate(call, policies)

    # Default: nothing persisted.
    log_verdict(verdict, log_path=log_path)
    default_raw = log_path.read_text(encoding="utf-8")
    for value in SYNTHETIC_SENSITIVE_PARAMETERS.values():
        assert str(value) not in default_raw
    default_entry = json.loads(default_raw.splitlines()[0])
    assert default_entry["tool_call"]["parameters"] == {}

    # With an explicit allowlist: only invoice_id survives.
    allowlisted_log_path = tmp_path / "audit_allowlisted.jsonl"
    log_verdict(
        verdict,
        log_path=allowlisted_log_path,
        config=AuditConfig(parameter_allowlist=frozenset({"invoice_id"})),
    )
    allowlisted_raw = allowlisted_log_path.read_text(encoding="utf-8")
    allowlisted_entry = json.loads(allowlisted_raw.splitlines()[0])

    assert allowlisted_entry["tool_call"]["parameters"] == {"invoice_id": "INV-123"}
    for key, value in SYNTHETIC_SENSITIVE_PARAMETERS.items():
        if key != "invoice_id":
            assert str(value) not in allowlisted_raw
