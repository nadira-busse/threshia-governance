"""
Tests for threshia.providers.openai_provider.

Mirrors tests/test_mistral_provider.py — mocks urllib.request.urlopen so
these tests never make a real network call or require a real
OPENAI_API_KEY.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from threshia.providers.openai_provider import ProviderError, call_openai


def _mock_response(content_dict: dict):
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(
        {"choices": [{"message": {"content": json.dumps(content_dict)}}]}
    ).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    return mock_resp


@patch("threshia.providers.openai_provider.OPENAI_API_KEY", "test-key-123")
@patch("threshia.providers.openai_provider.urllib.request.urlopen")
def test_call_openai_returns_parsed_decision(mock_urlopen):
    mock_urlopen.return_value = _mock_response(
        {"decision": "ALLOW", "reasoning": "Matches an allowed pattern."}
    )

    result = call_openai("Unknown.Tool", {}, ["some policy text"])

    assert result["decision"] == "ALLOW"
    assert result["reasoning"] == "Matches an allowed pattern."


@patch("threshia.providers.openai_provider.OPENAI_API_KEY", "")
def test_call_openai_raises_without_api_key():
    with pytest.raises(ProviderError, match="OPENAI_API_KEY"):
        call_openai("Unknown.Tool", {}, [])


@patch("threshia.providers.openai_provider.OPENAI_API_KEY", "test-key-123")
@patch("threshia.providers.openai_provider.urllib.request.urlopen")
def test_call_openai_raises_on_invalid_decision(mock_urlopen):
    mock_urlopen.return_value = _mock_response(
        {"decision": "MAYBE", "reasoning": "Not sure."}
    )
    with pytest.raises(ProviderError, match="invalid decision"):
        call_openai("Unknown.Tool", {}, [])


@patch("threshia.providers.openai_provider.OPENAI_API_KEY", "test-key-123")
@patch("threshia.providers.openai_provider.urllib.request.urlopen")
def test_call_openai_raises_on_missing_fields(mock_urlopen):
    mock_urlopen.return_value = _mock_response({"decision": "ALLOW"})  # no reasoning
    with pytest.raises(ProviderError, match="missing required fields"):
        call_openai("Unknown.Tool", {}, [])


@patch("threshia.providers.openai_provider.OPENAI_API_KEY", "test-key-123")
@patch("threshia.providers.openai_provider.urllib.request.urlopen")
def test_call_openai_raises_on_network_error(mock_urlopen):
    import urllib.error

    mock_urlopen.side_effect = urllib.error.URLError("connection refused")
    with pytest.raises(ProviderError, match="Could not reach OpenAI"):
        call_openai("Unknown.Tool", {}, [])
