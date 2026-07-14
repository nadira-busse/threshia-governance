"""
Shared test fixtures.

Ensures the test suite never depends on — or accidentally triggers — a
real LLM provider call because of API keys present in a developer's local
.env file. Without this, a test run on a machine with real keys configured
(e.g. after manually running scripts/verify_mistral_live.py) could
silently make a real, paid API call during what should be an offline,
free unit test suite.

Tests that specifically need a provider to look "configured" (e.g.
tests/test_provider_switching.py) patch the relevant key back on
explicitly within that test — those explicit patches apply during the
test body and take precedence over this fixture's default.
"""

import pytest


@pytest.fixture(autouse=True)
def no_live_provider_keys(monkeypatch):
    """Force both provider API keys empty by default for every test."""
    monkeypatch.setattr("threshia.providers.mistral_provider.MISTRAL_API_KEY", "")
    monkeypatch.setattr("threshia.providers.openai_provider.OPENAI_API_KEY", "")
