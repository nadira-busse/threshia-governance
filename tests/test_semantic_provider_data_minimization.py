"""
Regression tests for what reaches an external LLM provider (Mistral/
OpenAI) on the semantic advisory path, and what of that can reach the
audit log via provider reasoning.

Two boundaries are covered here:

    Boundary 1 — outbound provider request: SemanticConfig
    (threshia/engine/evaluator.py) controls this. Deny-by-default: no
    parameter names or values leave the process unless explicitly
    allowlisted.

    Boundary 2 — inbound provider reasoning -> audit: Verdict.reasoning is
    always persisted verbatim by threshia/audit/logger.py (AuditConfig
    only filters tool_call.parameters, not reasoning). Since boundary 1
    means a real provider was never given an unsent value, it cannot echo
    that value back — this file proves the request-construction side of
    that chain directly, by asserting on what the (mocked) provider
    actually received.

No live provider calls are made anywhere in this file.
"""

from unittest.mock import patch

from threshia.audit.logger import read_audit_log
from threshia.engine.evaluator import SemanticConfig, evaluate, evaluate_and_log
from threshia.models.policy import PolicyMatch
from threshia.models.tool_call import ToolCall
from threshia.policies.loader import load_all_policies

SYNTHETIC_SENSITIVE_PARAMETERS = {
    "salary": 123456,
    "medical_note": "synthetic-medical-value",
    "email": "fake@example.invalid",
    "iban": "TEST-IBAN-000",
    "access_token": "dummy-token-value",
    "ticket_id": "TCK-123",
}


def _retrieved_policy():
    return [
        PolicyMatch(
            policy_id="erp-controlled-actions-001",
            category="financial",
            relevance_score=0.5,
            matched_chunk="current policy context",
        )
    ]


def _uncovered_call(parameters=None):
    return ToolCall(tool_name="Sales.CreateDiscountOffer", parameters=parameters or {})


# --- Default outbound behavior ---


def test_default_outbound_request_excludes_all_parameter_values_and_names():
    call = _uncovered_call(dict(SYNTHETIC_SENSITIVE_PARAMETERS))
    captured = {}

    def fake_call_mistral(tool_name, parameters, retrieved_policy_texts, timeout=20):
        captured["tool_name"] = tool_name
        captured["parameters"] = parameters
        return {"decision": "FLAG", "reasoning": "Advisory reasoning, no parameter echo."}

    with (
        patch("threshia.providers.mistral_provider.MISTRAL_API_KEY", "test-key"),
        patch("threshia.policies.vector_store.build_index"),
        patch("threshia.policies.vector_store.retrieve", return_value=_retrieved_policy()),
        patch("threshia.providers.mistral_provider.call_mistral", side_effect=fake_call_mistral),
    ):
        evaluate(call, load_all_policies())

    assert captured["parameters"] == {}
    # Not just values — the key *names* are excluded too by default.
    assert set(captured["parameters"].keys()).isdisjoint(SYNTHETIC_SENSITIVE_PARAMETERS.keys())


def test_default_outbound_prompt_text_contains_no_sensitive_value():
    """Inspects the actual built prompt text, not just the parameters dict
    passed in — proves nothing leaks via any other route through
    build_prompt()."""
    call = _uncovered_call(dict(SYNTHETIC_SENSITIVE_PARAMETERS))
    captured = {}

    def fake_call_mistral(tool_name, parameters, retrieved_policy_texts, timeout=20):
        from threshia.providers.base import build_prompt

        captured["prompt"] = build_prompt(tool_name, parameters, retrieved_policy_texts)
        return {"decision": "FLAG", "reasoning": "n/a"}

    with (
        patch("threshia.providers.mistral_provider.MISTRAL_API_KEY", "test-key"),
        patch("threshia.policies.vector_store.build_index"),
        patch("threshia.policies.vector_store.retrieve", return_value=_retrieved_policy()),
        patch("threshia.providers.mistral_provider.call_mistral", side_effect=fake_call_mistral),
    ):
        evaluate(call, load_all_policies())

    for value in SYNTHETIC_SENSITIVE_PARAMETERS.values():
        assert str(value) not in captured["prompt"]
    for key in SYNTHETIC_SENSITIVE_PARAMETERS:
        assert key not in captured["prompt"]


def test_tool_identity_still_reaches_the_provider():
    call = _uncovered_call({"salary": 999})
    captured = {}

    def fake_call_mistral(tool_name, parameters, retrieved_policy_texts, timeout=20):
        captured["tool_name"] = tool_name
        return {"decision": "FLAG", "reasoning": "n/a"}

    with (
        patch("threshia.providers.mistral_provider.MISTRAL_API_KEY", "test-key"),
        patch("threshia.policies.vector_store.build_index"),
        patch("threshia.policies.vector_store.retrieve", return_value=_retrieved_policy()),
        patch("threshia.providers.mistral_provider.call_mistral", side_effect=fake_call_mistral),
    ):
        evaluate(call, load_all_policies())

    assert captured["tool_name"] == "Sales.CreateDiscountOffer"


# --- Explicit allowlist ---


def test_allowlisted_parameter_is_sent_others_are_not():
    call = _uncovered_call(dict(SYNTHETIC_SENSITIVE_PARAMETERS))
    captured = {}

    def fake_call_mistral(tool_name, parameters, retrieved_policy_texts, timeout=20):
        captured["parameters"] = parameters
        return {"decision": "FLAG", "reasoning": "n/a"}

    with (
        patch("threshia.providers.mistral_provider.MISTRAL_API_KEY", "test-key"),
        patch("threshia.policies.vector_store.build_index"),
        patch("threshia.policies.vector_store.retrieve", return_value=_retrieved_policy()),
        patch("threshia.providers.mistral_provider.call_mistral", side_effect=fake_call_mistral),
    ):
        evaluate(
            call,
            load_all_policies(),
            semantic_config=SemanticConfig(parameter_allowlist=frozenset({"ticket_id"})),
        )

    assert captured["parameters"] == {"ticket_id": "TCK-123"}


def test_allowlisted_missing_key_causes_no_failure():
    call = _uncovered_call({"ticket_id": "TCK-1"})
    captured = {}

    def fake_call_mistral(tool_name, parameters, retrieved_policy_texts, timeout=20):
        captured["parameters"] = parameters
        return {"decision": "FLAG", "reasoning": "n/a"}

    with (
        patch("threshia.providers.mistral_provider.MISTRAL_API_KEY", "test-key"),
        patch("threshia.policies.vector_store.build_index"),
        patch("threshia.policies.vector_store.retrieve", return_value=_retrieved_policy()),
        patch("threshia.providers.mistral_provider.call_mistral", side_effect=fake_call_mistral),
    ):
        verdict = evaluate(
            call,
            load_all_policies(),
            semantic_config=SemanticConfig(
                parameter_allowlist=frozenset({"ticket_id", "operation_type"})
            ),
        )

    assert captured["parameters"] == {"ticket_id": "TCK-1"}
    assert verdict.decision == "FLAG"


def test_empty_allowlist_behaves_like_default():
    call = _uncovered_call({"ticket_id": "TCK-1"})
    captured = {}

    def fake_call_mistral(tool_name, parameters, retrieved_policy_texts, timeout=20):
        captured["parameters"] = parameters
        return {"decision": "FLAG", "reasoning": "n/a"}

    with (
        patch("threshia.providers.mistral_provider.MISTRAL_API_KEY", "test-key"),
        patch("threshia.policies.vector_store.build_index"),
        patch("threshia.policies.vector_store.retrieve", return_value=_retrieved_policy()),
        patch("threshia.providers.mistral_provider.call_mistral", side_effect=fake_call_mistral),
    ):
        evaluate(call, load_all_policies(), semantic_config=SemanticConfig())

    assert captured["parameters"] == {}


# --- Deterministic path unaffected ---


def test_deterministic_gating_still_uses_full_local_parameters():
    """semantic_config must never affect the deterministic gating check —
    it only narrows what leaves the process on the semantic path."""
    call = ToolCall(
        tool_name="ERP.PaymentReviewTrigger",
        parameters={"human_approval_evidenced": True},
    )
    verdict = evaluate(
        call,
        load_all_policies(),
        semantic_config=SemanticConfig(parameter_allowlist=frozenset()),
    )
    assert verdict.decision == "ALLOW"
    # The in-memory ToolCall itself is untouched.
    assert call.parameters == {"human_approval_evidenced": True}


def test_semantic_config_does_not_change_the_verdict():
    call = _uncovered_call({"salary": 1})

    def fake_call_mistral(tool_name, parameters, retrieved_policy_texts, timeout=20):
        return {"decision": "ALLOW", "reasoning": "n/a"}

    with (
        patch("threshia.providers.mistral_provider.MISTRAL_API_KEY", "test-key"),
        patch("threshia.policies.vector_store.build_index"),
        patch("threshia.policies.vector_store.retrieve", return_value=_retrieved_policy()),
        patch("threshia.providers.mistral_provider.call_mistral", side_effect=fake_call_mistral),
    ):
        default_verdict = evaluate(call, load_all_policies())
        allowlisted_verdict = evaluate(
            call,
            load_all_policies(),
            semantic_config=SemanticConfig(parameter_allowlist=frozenset({"salary"})),
        )

    assert default_verdict.decision == allowlisted_verdict.decision == "FLAG"


# --- Semantic authorization invariant preserved under minimization ---


def test_provider_allow_for_uncovered_tool_still_yields_authoritative_flag():
    call = _uncovered_call(dict(SYNTHETIC_SENSITIVE_PARAMETERS))

    def fake_call_mistral(tool_name, parameters, retrieved_policy_texts, timeout=20):
        # Provider genuinely cannot see the sensitive values — confirmed
        # structurally, not just asserted here.
        assert parameters == {}
        return {"decision": "ALLOW", "reasoning": "Looks like a safe read."}

    with (
        patch("threshia.providers.mistral_provider.MISTRAL_API_KEY", "test-key"),
        patch("threshia.policies.vector_store.build_index"),
        patch("threshia.policies.vector_store.retrieve", return_value=_retrieved_policy()),
        patch("threshia.providers.mistral_provider.call_mistral", side_effect=fake_call_mistral),
    ):
        verdict = evaluate(call, load_all_policies())

    assert verdict.decision == "FLAG"
    assert verdict.provider_suggested_decision == "ALLOW"


# --- Audit echo regression (Boundary 2) ---


def test_unsent_sensitive_value_cannot_reach_audit_reasoning_by_default(tmp_path):
    """
    End-to-end: the provider mock itself asserts it never received the
    sensitive values (so a real provider structurally cannot echo them),
    returns ordinary reasoning, and the persisted audit record is then
    checked to confirm no synthetic sensitive value appears anywhere in
    it — including inside `reasoning`, which AuditConfig does not filter.
    """
    log_path = tmp_path / "audit.jsonl"
    call = _uncovered_call(dict(SYNTHETIC_SENSITIVE_PARAMETERS))

    def fake_call_mistral(tool_name, parameters, retrieved_policy_texts, timeout=20):
        assert parameters == {}, "provider must not receive parameter values by default"
        return {"decision": "FLAG", "reasoning": "Uncertain, recommend human review."}

    with (
        patch("threshia.providers.mistral_provider.MISTRAL_API_KEY", "test-key"),
        patch("threshia.policies.vector_store.build_index"),
        patch("threshia.policies.vector_store.retrieve", return_value=_retrieved_policy()),
        patch("threshia.providers.mistral_provider.call_mistral", side_effect=fake_call_mistral),
        patch("threshia.audit.logger.AUDIT_LOG_PATH", log_path),
    ):
        evaluate_and_log(call, load_all_policies())

    entries = read_audit_log(log_path=log_path)
    raw_text = log_path.read_text(encoding="utf-8")
    assert len(entries) == 1
    for value in SYNTHETIC_SENSITIVE_PARAMETERS.values():
        assert str(value) not in raw_text
    assert entries[0]["tool_call"]["parameters"] == {}


def test_allowlisted_value_may_reach_provider_reasoning_and_audit(tmp_path):
    """
    Documents the honest counterpart to the test above: once a caller
    explicitly allowlists a key for the semantic request, that value may
    be reflected in provider reasoning, and reasoning is always persisted
    — this is expected, not a bug, once the caller has opted in.
    """
    log_path = tmp_path / "audit.jsonl"
    call = _uncovered_call({"ticket_id": "TCK-999"})

    def fake_call_mistral(tool_name, parameters, retrieved_policy_texts, timeout=20):
        assert parameters == {"ticket_id": "TCK-999"}
        return {
            "decision": "FLAG",
            "reasoning": f"Ticket {parameters['ticket_id']} needs human review.",
        }

    with (
        patch("threshia.providers.mistral_provider.MISTRAL_API_KEY", "test-key"),
        patch("threshia.policies.vector_store.build_index"),
        patch("threshia.policies.vector_store.retrieve", return_value=_retrieved_policy()),
        patch("threshia.providers.mistral_provider.call_mistral", side_effect=fake_call_mistral),
        patch("threshia.audit.logger.AUDIT_LOG_PATH", log_path),
    ):
        from threshia.audit.logger import AuditConfig

        evaluate_and_log(
            call,
            load_all_policies(),
            audit_config=AuditConfig(),
            semantic_config=SemanticConfig(parameter_allowlist=frozenset({"ticket_id"})),
        )

    entries = read_audit_log(log_path=log_path)
    assert "TCK-999" in entries[0]["reasoning"]
