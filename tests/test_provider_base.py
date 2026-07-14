"""Tests for threshia.providers.base — the provider registry and shared helpers."""

import pytest

from threshia.providers.base import (
    ProviderError,
    build_prompt,
    get_provider,
    validate_provider_response,
)


def test_get_provider_mistral_returns_correct_pair():
    from threshia.providers import mistral_provider

    is_configured, call_evaluate = get_provider("mistral")
    assert is_configured is mistral_provider.is_configured
    assert call_evaluate is mistral_provider.call_mistral


def test_get_provider_openai_returns_correct_pair():
    from threshia.providers import openai_provider

    is_configured, call_evaluate = get_provider("openai")
    assert is_configured is openai_provider.is_configured
    assert call_evaluate is openai_provider.call_openai


def test_get_provider_unknown_name_raises():
    with pytest.raises(ProviderError, match="Unknown provider"):
        get_provider("does-not-exist")


def test_build_prompt_includes_tool_name_and_policy_context():
    prompt = build_prompt("Some.Tool", {"x": 1}, ["policy text here"])
    assert "Some.Tool" in prompt
    assert "policy text here" in prompt


def test_build_prompt_handles_no_retrieved_policies():
    prompt = build_prompt("Some.Tool", {}, [])
    assert "(no policy content retrieved)" in prompt


def test_validate_provider_response_accepts_valid():
    result = validate_provider_response(
        {"decision": "ALLOW", "reasoning": "ok"}, "TestProvider"
    )
    assert result["decision"] == "ALLOW"


def test_validate_provider_response_rejects_invalid_decision():
    with pytest.raises(ProviderError, match="TestProvider returned invalid decision"):
        validate_provider_response({"decision": "MAYBE", "reasoning": "ok"}, "TestProvider")


def test_validate_provider_response_rejects_missing_fields():
    with pytest.raises(ProviderError, match="TestProvider response missing required fields"):
        validate_provider_response({"decision": "ALLOW"}, "TestProvider")
