"""
Integration test: confirm THRESHIA_PROVIDER actually switches which
provider the engine calls — not just labels the resulting Verdict.

Mocks vector_store and the provider's evaluate() so this test never
touches ChromaDB, the network, or a real API key.
"""

from unittest.mock import patch

from threshia.engine.evaluator import evaluate
from threshia.models.policy import PolicyMatch
from threshia.models.tool_call import ToolCall
from threshia.policies.loader import load_all_policies


@patch("threshia.providers.openai_provider.OPENAI_API_KEY", "test-key")
@patch("threshia.config.PROVIDER", "openai")
@patch("threshia.policies.vector_store.build_index")
@patch("threshia.policies.vector_store.retrieve")
@patch("threshia.providers.openai_provider.call_openai")
def test_engine_uses_openai_when_configured_as_provider(
    mock_call_openai, mock_retrieve, mock_build_index
):
    policies = load_all_policies()
    mock_retrieve.return_value = [
        PolicyMatch(
            policy_id="erp-controlled-actions-001",
            category="financial",
            relevance_score=0.5,
            matched_chunk="...",
        )
    ]
    mock_call_openai.return_value = {"decision": "FLAG", "reasoning": "Uncertain case."}

    call = ToolCall(tool_name="Sales.CreateDiscountOffer", parameters={})
    verdict = evaluate(call, policies)

    assert verdict.decision == "FLAG"
    assert verdict.decision_source == "llm"
    assert verdict.provider == "openai"
    mock_call_openai.assert_called_once()
    mock_build_index.assert_called_once()


@patch("threshia.config.PROVIDER", "unrecognized-provider-name")
def test_engine_falls_back_gracefully_on_unknown_provider_name():
    """
    A typo'd or unsupported THRESHIA_PROVIDER value shouldn't crash the
    engine — it should behave exactly like no provider being configured.
    """
    policies = load_all_policies()
    call = ToolCall(tool_name="Sales.CreateDiscountOffer", parameters={})

    verdict = evaluate(call, policies)

    assert verdict.decision == "FLAG"
    assert verdict.decision_source == "rule"
