"""
Tests for threshia.policies.vector_store.

Note: the first run on a fresh machine downloads ChromaDB's default
embedding model (~90MB) from Hugging Face. That requires internet access
once; after that it's cached and runs fully offline.

If that download fails (no internet, DNS/firewall blocking huggingface.co),
these tests SKIP rather than FAIL — a missing one-time download is an
environment condition, not a defect in this code. Check your connection
if you want to retry the download.
"""

import pytest

from threshia.models.policy import Policy
from threshia.policies import vector_store


@pytest.fixture(autouse=True)
def isolate_chroma_dir(tmp_path, monkeypatch):
    """Point every test at a temporary ChromaDB directory, never the real one."""
    monkeypatch.setattr(vector_store, "CHROMA_PERSIST_DIR", tmp_path)
    yield


def make_policy(policy_id: str, category: str, content: str) -> Policy:
    return Policy(
        id=policy_id,
        category=category,
        risk_level="low",
        applicable_tools=[],
        source="test fixture",
        content=content,
        file_path="<memory>",
    )


def _build_index_or_skip(policies: list[Policy], force: bool = False) -> int:
    """
    Wrap build_index() so a first-run embedding-model download failure
    (no internet, DNS/firewall blocking huggingface.co) skips the test
    instead of failing it. A real bug in build_index() still fails
    normally, since we only catch network-shaped errors here.
    """
    try:
        return vector_store.build_index(policies, force=force)
    except Exception as e:
        message = str(e).lower()
        network_signals = ("getaddrinfo", "connecterror", "connection", "dns", "timeout")
        if any(signal in message for signal in network_signals):
            pytest.skip(
                "Could not download ChromaDB's embedding model (network/DNS "
                f"issue reaching huggingface.co). This is a one-time download "
                f"on first use, not a code defect. Original error: {e}"
            )
        raise  # a non-network error is a real failure — don't hide it


def test_build_index_seeds_collection():
    policies = [
        make_policy("p1", "financial", "Policy about payments and invoices."),
        make_policy("p2", "hr", "Policy about employee data access."),
    ]
    count = _build_index_or_skip(policies)
    assert count == 2


def test_build_index_is_idempotent_without_force():
    policies = [make_policy("p1", "financial", "Payment policy text.")]
    first = _build_index_or_skip(policies)
    second = _build_index_or_skip(policies)
    assert first == second == 1


def test_retrieve_before_seeding_returns_empty_list():
    assert vector_store.retrieve("some query") == []


def test_retrieve_returns_relevant_policy():
    policies = [
        make_policy(
            "erp-policy",
            "financial",
            "Rules about ERP payment approval and invoice processing.",
        ),
        make_policy(
            "hr-policy",
            "hr",
            "Rules about employee onboarding and restricted HR data access.",
        ),
    ]
    _build_index_or_skip(policies)

    matches = vector_store.retrieve("agent wants to process a vendor payment", top_k=1)

    assert len(matches) == 1
    assert matches[0].policy_id == "erp-policy"
    assert matches[0].category == "financial"
