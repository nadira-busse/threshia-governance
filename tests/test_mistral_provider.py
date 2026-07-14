"""
Tests for threshia.providers.mistral_provider.

Mocks urllib.request.urlopen so these tests never make a real network
call or require a real MISTRAL_API_KEY — important for CI and for not
burning API credits every time the test suite runs.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from threshia.providers.mistral_provider import ProviderError, call_mistral


def _mock_response(content_dict: dict):
    """Build a mock matching urlopen's context-manager + .read() interface."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(
        {"choices": [{"message": {"content": json.dumps(content_dict)}}]}
    ).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    return mock_resp


@patch("threshia.providers.mistral_provider.MISTRAL_API_KEY", "test-key-123")
@patch("threshia.providers.mistral_provider.urllib.request.urlopen")
def test_call_mistral_returns_parsed_decision(mock_urlopen):
    mock_urlopen.return_value = _mock_response(
        {"decision": "FLAG", "reasoning": "Resembles a gated pattern."}
    )

    result = call_mistral("Unknown.Tool", {}, ["some policy text"])

    assert result["decision"] == "FLAG"
    assert result["reasoning"] == "Resembles a gated pattern."


@patch("threshia.providers.mistral_provider.MISTRAL_API_KEY", "")
def test_call_mistral_raises_without_api_key():
    with pytest.raises(ProviderError, match="MISTRAL_API_KEY"):
        call_mistral("Unknown.Tool", {}, [])


@patch("threshia.providers.mistral_provider.MISTRAL_API_KEY", "test-key-123")
@patch("threshia.providers.mistral_provider.urllib.request.urlopen")
def test_call_mistral_raises_on_invalid_decision(mock_urlopen):
    mock_urlopen.return_value = _mock_response(
        {"decision": "MAYBE", "reasoning": "Not sure."}
    )
    with pytest.raises(ProviderError, match="invalid decision"):
        call_mistral("Unknown.Tool", {}, [])


@patch("threshia.providers.mistral_provider.MISTRAL_API_KEY", "test-key-123")
@patch("threshia.providers.mistral_provider.urllib.request.urlopen")
def test_call_mistral_raises_on_missing_fields(mock_urlopen):
    mock_urlopen.return_value = _mock_response({"decision": "ALLOW"})  # no reasoning
    with pytest.raises(ProviderError, match="missing required fields"):
        call_mistral("Unknown.Tool", {}, [])


@patch("threshia.providers.mistral_provider.MISTRAL_API_KEY", "test-key-123")
@patch("threshia.providers.mistral_provider.urllib.request.urlopen")
def test_call_mistral_raises_on_network_error(mock_urlopen):
    import urllib.error

    mock_urlopen.side_effect = urllib.error.URLError("connection refused")
    with pytest.raises(ProviderError, match="Could not reach Mistral"):
        call_mistral("Unknown.Tool", {}, [])
