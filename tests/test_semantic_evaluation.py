"""Regression tests for the evaluator's optional semantic boundary."""

from unittest.mock import patch

from threshia.engine.evaluator import evaluate
from threshia.models.policy import PolicyMatch
from threshia.models.tool_call import ToolCall
from threshia.policies.loader import load_all_policies
from threshia.providers.base import ProviderError


def _unknown_call() -> ToolCall:
    return ToolCall(tool_name="Sales.CreateDiscountOffer", parameters={})


def _retrieved_policy() -> list[PolicyMatch]:
    return [
        PolicyMatch(
            policy_id="erp-controlled-actions-001",
            category="financial",
            relevance_score=0.5,
            matched_chunk="current policy context",
        )
    ]


def test_index_build_exception_returns_fallback_flag():
    policies = load_all_policies()

    with (
        patch("threshia.providers.mistral_provider.MISTRAL_API_KEY", "test-key"),
        patch(
            "threshia.policies.vector_store.build_index",
            side_effect=RuntimeError("embedding initialization failed"),
        ),
        patch("threshia.policies.vector_store.retrieve") as mock_retrieve,
        patch("threshia.providers.mistral_provider.call_mistral") as mock_provider,
    ):
        verdict = evaluate(_unknown_call(), policies)

    assert verdict.decision == "FLAG"
    assert verdict.decision_source == "fallback"
    assert verdict.fallback_reason == "embedding initialization failed"
    assert "semantic index or retrieval failed" in verdict.reasoning.lower()
    mock_retrieve.assert_not_called()
    mock_provider.assert_not_called()


def test_retrieval_exception_returns_fallback_flag():
    policies = load_all_policies()

    with (
        patch("threshia.providers.mistral_provider.MISTRAL_API_KEY", "test-key"),
        patch("threshia.policies.vector_store.build_index"),
        patch(
            "threshia.policies.vector_store.retrieve",
            side_effect=RuntimeError("query failed"),
        ),
        patch("threshia.providers.mistral_provider.call_mistral") as mock_provider,
    ):
        verdict = evaluate(_unknown_call(), policies)

    assert verdict.decision == "FLAG"
    assert verdict.decision_source == "fallback"
    assert verdict.fallback_reason == "query failed"
    mock_provider.assert_not_called()


def test_provider_error_still_returns_fallback_flag():
    policies = load_all_policies()

    with (
        patch("threshia.providers.mistral_provider.MISTRAL_API_KEY", "test-key"),
        patch("threshia.policies.vector_store.build_index"),
        patch("threshia.policies.vector_store.retrieve", return_value=_retrieved_policy()),
        patch(
            "threshia.providers.mistral_provider.call_mistral",
            side_effect=ProviderError("provider unavailable"),
        ),
    ):
        verdict = evaluate(_unknown_call(), policies)

    assert verdict.decision == "FLAG"
    assert verdict.decision_source == "fallback"
    assert verdict.fallback_reason == "provider unavailable"
    assert verdict.policy_coverage == 1


def test_unconfigured_provider_skips_chroma_and_uses_rule_flag():
    policies = load_all_policies()

    with (
        patch("threshia.providers.mistral_provider.MISTRAL_API_KEY", ""),
        patch("threshia.policies.vector_store.build_index") as mock_build,
        patch("threshia.policies.vector_store.retrieve") as mock_retrieve,
    ):
        verdict = evaluate(_unknown_call(), policies)

    assert verdict.decision == "FLAG"
    assert verdict.decision_source == "rule"
    mock_build.assert_not_called()
    mock_retrieve.assert_not_called()


def test_direct_policy_path_never_touches_semantic_infrastructure():
    policies = load_all_policies()
    call = ToolCall(tool_name="ERP.InvoiceLookup", parameters={})

    with (
        patch("threshia.policies.vector_store.build_index") as mock_build,
        patch("threshia.policies.vector_store.retrieve") as mock_retrieve,
        patch("threshia.providers.mistral_provider.call_mistral") as mock_provider,
    ):
        verdict = evaluate(call, policies)

    assert verdict.decision == "ALLOW"
    assert verdict.decision_source == "rule"
    mock_build.assert_not_called()
    mock_retrieve.assert_not_called()
    mock_provider.assert_not_called()


# Only explicit deterministic policy coverage may produce ALLOW. An
# uncovered tool's semantic-path verdict is always authoritative FLAG,
# regardless of what the provider suggested — this is enforced in
# threshia.engine.evaluator._authoritative_uncovered_verdict() after the
# (mocked, here) provider response is already parsed, so these tests
# would still pass even against a real, unpatched provider call that
# happened to return ALLOW. This closes a real failure mode: live
# verification against both Mistral and OpenAI once showed a
# semantically-irrelevant, uncovered tool call receiving ALLOW from both
# providers (see test_weather_get_forecast_style_regression_never_authorizes
# below, modeled directly on that finding).


def test_uncovered_tool_provider_allow_is_never_authoritative():
    """
    The core regression: a provider suggesting ALLOW for an uncovered
    tool must never become an authoritative ALLOW. This test
    would still pass even if the mocked provider truly returned ALLOW
    from a real API — the invariant is enforced after parsing, not by
    trusting the provider's word.
    """
    policies = load_all_policies()

    with (
        patch("threshia.providers.mistral_provider.MISTRAL_API_KEY", "test-key"),
        patch("threshia.policies.vector_store.build_index"),
        patch("threshia.policies.vector_store.retrieve", return_value=_retrieved_policy()),
        patch(
            "threshia.providers.mistral_provider.call_mistral",
            return_value={
                "decision": "ALLOW",
                "reasoning": "This resembles an allowed read-only pattern.",
            },
        ),
    ):
        verdict = evaluate(_unknown_call(), policies)

    assert verdict.decision == "FLAG"
    assert verdict.decision != "ALLOW"
    assert verdict.decision_source == "llm"
    assert verdict.provider_suggested_decision == "ALLOW"
    # The provider's suggestion must remain inspectable in the reasoning
    # text, not silently dropped — a reader must be able to see it
    # recommended ALLOW without mistaking that for authorization.
    assert "ALLOW" in verdict.reasoning
    assert "no policy explicitly covers" in verdict.reasoning.lower()
    assert "resembles an allowed read-only pattern" in verdict.reasoning


def test_weather_get_forecast_style_regression_never_authorizes():
    """
    Regression modeled directly on the observed live failure: an
    uncovered, semantically-irrelevant tool call
    (`Weather.GetForecast`) received ALLOW from both Mistral and OpenAI
    in live verification, by pattern-matching "read-only" against the
    ITSM read-only policy despite having no real relationship to any
    governed domain (see live-provider-results.md, finding 2). This
    encodes that failure class as a permanent, offline regression test —
    no live API call is made here.
    """
    policies = load_all_policies()
    call = ToolCall(tool_name="Weather.GetForecast", parameters={"location": "Berlin"})
    irrelevant_match = [
        PolicyMatch(
            policy_id="itsm-readonly-001",
            category="it_operations",
            relevance_score=1.94,
            matched_chunk="Read and recommendation tool calls are allowed without review.",
        )
    ]

    with (
        patch("threshia.providers.mistral_provider.MISTRAL_API_KEY", "test-key"),
        patch("threshia.policies.vector_store.build_index"),
        patch("threshia.policies.vector_store.retrieve", return_value=irrelevant_match),
        patch(
            "threshia.providers.mistral_provider.call_mistral",
            return_value={
                "decision": "ALLOW",
                "reasoning": (
                    "The tool call reads forecast data (read-only) and does "
                    "not match any write, modification, or high-risk "
                    "patterns described in the provided governance policies."
                ),
            },
        ),
    ):
        verdict = evaluate(call, policies)

    assert verdict.decision == "FLAG"
    assert verdict.provider_suggested_decision == "ALLOW"
    assert verdict.decision_source == "llm"


def test_uncovered_tool_provider_flag_is_coherent_review_required():
    policies = load_all_policies()

    with (
        patch("threshia.providers.mistral_provider.MISTRAL_API_KEY", "test-key"),
        patch("threshia.policies.vector_store.build_index"),
        patch("threshia.policies.vector_store.retrieve", return_value=_retrieved_policy()),
        patch(
            "threshia.providers.mistral_provider.call_mistral",
            return_value={"decision": "FLAG", "reasoning": "Uncertain, needs human review."},
        ),
    ):
        verdict = evaluate(_unknown_call(), policies)

    assert verdict.decision == "FLAG"
    assert verdict.decision_source == "llm"
    # Already FLAG at the source — nothing was overridden, so there's no
    # separate "suggested" value to preserve.
    assert verdict.provider_suggested_decision is None
    assert "Uncertain, needs human review." in verdict.reasoning


def test_uncovered_tool_provider_block_is_advisory_not_authoritative():
    """
    BLOCK means an applicable policy explicitly prohibits the action
    (see the never-permitted rule path). An uncovered tool has no policy
    that explicitly covers it, so it has no basis for an authoritative
    BLOCK either — a provider's BLOCK suggestion here is inference by
    resemblance, not an applicable prohibition, and is treated the same
    as an ALLOW suggestion: advisory only, final result stays FLAG.
    """
    policies = load_all_policies()

    with (
        patch("threshia.providers.mistral_provider.MISTRAL_API_KEY", "test-key"),
        patch("threshia.policies.vector_store.build_index"),
        patch("threshia.policies.vector_store.retrieve", return_value=_retrieved_policy()),
        patch(
            "threshia.providers.mistral_provider.call_mistral",
            return_value={
                "decision": "BLOCK",
                "reasoning": "This resembles a never-permitted financial action.",
            },
        ),
    ):
        verdict = evaluate(_unknown_call(), policies)

    assert verdict.decision == "FLAG"
    assert verdict.decision != "BLOCK"
    assert verdict.decision_source == "llm"
    assert verdict.provider_suggested_decision == "BLOCK"
    assert "BLOCK" in verdict.reasoning
    assert "resembles a never-permitted financial action" in verdict.reasoning


def test_covered_tool_still_reaches_authoritative_allow():
    """
    Direct-path preservation: a tool with explicit policy coverage still
    gets a real, authoritative ALLOW — the deterministic-coverage-only
    rule only restricts the uncovered path. Semantic infrastructure is
    mocked to return ALLOW here too, to
    prove the covered path doesn't even consult it (see also
    test_direct_policy_path_never_touches_semantic_infrastructure).
    """
    policies = load_all_policies()
    call = ToolCall(tool_name="ERP.InvoiceLookup", parameters={})

    with (
        patch("threshia.providers.mistral_provider.MISTRAL_API_KEY", "test-key"),
        patch("threshia.policies.vector_store.build_index") as mock_build,
        patch("threshia.policies.vector_store.retrieve") as mock_retrieve,
        patch(
            "threshia.providers.mistral_provider.call_mistral",
            return_value={"decision": "ALLOW", "reasoning": "n/a"},
        ) as mock_provider,
    ):
        verdict = evaluate(call, policies)

    assert verdict.decision == "ALLOW"
    assert verdict.decision_source == "rule"
    assert verdict.provider_suggested_decision is None
    mock_build.assert_not_called()
    mock_retrieve.assert_not_called()
    mock_provider.assert_not_called()


# --- Retrieval safety regression under a deliberately misleading match ---


def test_highly_misleading_retrieval_still_cannot_produce_authoritative_allow():
    """
    Retrieval quality and authorization safety are separate concerns.
    This adversarially fakes a *convincing* but substantively wrong
    retrieval match — a read-only/advisory-sounding policy chunk, at a
    strong (low-distance) relevance score — for a tool call that has
    nothing to do with that policy, with the provider then suggesting
    ALLOW on the strength of that misleading context. Even in this worst
    case, the deterministic-coverage-only-ALLOW rule (see
    threshia/models/verdict.py) must hold: only explicit deterministic
    policy coverage may authorize, so an uncovered tool call's result
    must still be FLAG, never ALLOW.
    """
    policies = load_all_policies()
    call = ToolCall(
        tool_name="Vendor.BankDetailUpdateExecute",
        parameters={"vendor_id": "V-1", "new_iban": "synthetic-iban-value"},
    )
    misleadingly_strong_match = [
        PolicyMatch(
            policy_id="itsm-readonly-001",
            category="it_operations",
            relevance_score=0.05,  # deliberately strong/convincing distance
            matched_chunk=(
                "Read and recommendation tool calls are allowed without "
                "review. Update and lookup operations that do not modify "
                "financial records may proceed without a human approval "
                "gate."
            ),
        )
    ]

    with (
        patch("threshia.providers.mistral_provider.MISTRAL_API_KEY", "test-key"),
        patch("threshia.policies.vector_store.build_index"),
        patch(
            "threshia.policies.vector_store.retrieve",
            return_value=misleadingly_strong_match,
        ),
        patch(
            "threshia.providers.mistral_provider.call_mistral",
            return_value={
                "decision": "ALLOW",
                "reasoning": "Retrieved context describes this as a low-risk update operation.",
            },
        ),
    ):
        verdict = evaluate(call, policies)

    assert verdict.decision == "FLAG"
    assert verdict.decision != "ALLOW"
    assert verdict.decision_source == "llm"
    assert verdict.provider_suggested_decision == "ALLOW"
    assert verdict.retrieval_score == 0.05
