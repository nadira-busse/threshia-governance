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

from unittest.mock import MagicMock

import pytest

from threshia.models.policy import Policy
from threshia.policies import vector_store
from threshia.policies.loader import load_all_policies


@pytest.fixture(autouse=True)
def isolate_chroma_dir(tmp_path, monkeypatch):
    """Point every test at a temporary ChromaDB directory, never the real one."""
    monkeypatch.setattr(vector_store, "CHROMA_PERSIST_DIR", tmp_path)
    yield


def make_policy(
    policy_id: str,
    category: str,
    content: str,
    applicable_tools: list[str] | None = None,
    never_permitted: list[str] | None = None,
) -> Policy:
    return Policy(
        id=policy_id,
        category=category,
        risk_level="low",
        applicable_tools=applicable_tools or [],
        source="test fixture",
        content=content,
        file_path="<memory>",
        never_permitted=never_permitted or [],
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


def test_unchanged_policy_fingerprint_reuses_existing_collection(monkeypatch):
    policies = [make_policy("p1", "financial", "Current payment policy.")]
    collection = MagicMock()
    collection.count.return_value = 1
    collection.metadata = {
        vector_store.POLICY_FINGERPRINT_KEY: vector_store._policy_fingerprint(policies)
    }
    client = MagicMock()
    client.get_or_create_collection.return_value = collection
    monkeypatch.setattr(vector_store, "_client", lambda: client)

    count = vector_store.build_index(policies)

    assert count == 1
    client.delete_collection.assert_not_called()
    collection.add.assert_not_called()


def test_changed_policy_content_rebuilds_collection(monkeypatch):
    old_policies = [make_policy("p1", "financial", "Old payment policy.")]
    current_policies = [make_policy("p1", "financial", "Updated payment policy.")]
    existing = MagicMock()
    existing.count.return_value = 1
    existing.metadata = {
        vector_store.POLICY_FINGERPRINT_KEY: vector_store._policy_fingerprint(old_policies)
    }
    rebuilt = MagicMock()
    rebuilt.count.return_value = 1
    client = MagicMock()
    client.get_or_create_collection.side_effect = [existing, rebuilt]
    monkeypatch.setattr(vector_store, "_client", lambda: client)

    assert vector_store._policy_fingerprint(old_policies) != (
        vector_store._policy_fingerprint(current_policies)
    )

    count = vector_store.build_index(current_policies)

    assert count == 1
    client.delete_collection.assert_called_once_with(vector_store.COLLECTION_NAME)
    rebuilt.add.assert_called_once()
    assert "Updated payment policy." in rebuilt.add.call_args.kwargs["documents"][0]


def test_changed_never_permitted_rebuilds_collection(monkeypatch):
    """
    never_permitted is machine-authoritative frontmatter, not necessarily
    reflected in policy.content — the fingerprint must include it
    explicitly so a restrictions-only change still triggers a rebuild.
    """
    old_policies = [make_policy("p1", "financial", "Payment policy.", never_permitted=["action_a"])]
    current_policies = [
        make_policy("p1", "financial", "Payment policy.", never_permitted=["action_a", "action_b"])
    ]
    existing = MagicMock()
    existing.count.return_value = 1
    existing.metadata = {
        vector_store.POLICY_FINGERPRINT_KEY: vector_store._policy_fingerprint(old_policies)
    }
    rebuilt = MagicMock()
    rebuilt.count.return_value = 1
    client = MagicMock()
    client.get_or_create_collection.side_effect = [existing, rebuilt]
    monkeypatch.setattr(vector_store, "_client", lambda: client)

    assert vector_store._policy_fingerprint(old_policies) != (
        vector_store._policy_fingerprint(current_policies)
    )

    count = vector_store.build_index(current_policies)

    assert count == 1
    client.delete_collection.assert_called_once_with(vector_store.COLLECTION_NAME)
    rebuilt.add.assert_called_once()


def test_indexed_document_includes_never_permitted_action_names():
    """
    The exact action-name strings must be present in the embedded document
    text even if the Markdown body prose only summarizes them in words —
    this is what keeps semantic retrieval able to match on the exact
    blocked-action vocabulary after the prose migration.
    """
    policy = make_policy(
        "p1",
        "financial",
        "This policy explains its restrictions in prose only, without listing them.",
        never_permitted=["release_payment", "modify_vendor_bank_details"],
    )
    document = vector_store._indexed_document(policy)
    assert "release_payment" in document
    assert "modify_vendor_bank_details" in document


@pytest.mark.parametrize(
    "current_policies",
    [
        [
            make_policy("p1", "financial", "Payment policy."),
            make_policy("p2", "hr", "HR policy."),
        ],
        [make_policy("p1", "financial", "Payment policy.")],
    ],
    ids=["added-policy", "removed-policy"],
)
def test_added_or_removed_policy_rebuilds_collection(monkeypatch, current_policies):
    old_policies = [
        make_policy("p1", "financial", "Payment policy."),
        make_policy("p3", "it", "IT policy."),
    ]
    existing = MagicMock()
    existing.count.return_value = len(old_policies)
    existing.metadata = {
        vector_store.POLICY_FINGERPRINT_KEY: vector_store._policy_fingerprint(old_policies)
    }
    rebuilt = MagicMock()
    rebuilt.count.return_value = len(current_policies)
    client = MagicMock()
    client.get_or_create_collection.side_effect = [existing, rebuilt]
    monkeypatch.setattr(vector_store, "_client", lambda: client)

    count = vector_store.build_index(current_policies)

    assert count == len(current_policies)
    client.delete_collection.assert_called_once_with(vector_store.COLLECTION_NAME)
    rebuilt.add.assert_called_once()


def test_policy_fingerprint_is_stable_across_input_ordering():
    policy_a = make_policy(
        "p1",
        "financial",
        "Payment policy.",
        applicable_tools=["ERP.ToolB", "ERP.ToolA"],
    )
    policy_b = make_policy("p2", "hr", "HR policy.")
    reordered_a = make_policy(
        "p1",
        "financial",
        "Payment policy.",
        applicable_tools=["ERP.ToolA", "ERP.ToolB"],
    )

    assert vector_store._policy_fingerprint([policy_a, policy_b]) == (
        vector_store._policy_fingerprint([policy_b, reordered_a])
    )


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


def test_retrieval_uses_current_content_after_automatic_rebuild():
    old_policies = [
        make_policy("p1", "financial", "Legacy policy about archived invoices.")
    ]
    current_policies = [
        make_policy("p1", "financial", "Current policy about payment authorization.")
    ]
    _build_index_or_skip(old_policies)

    _build_index_or_skip(current_policies)
    matches = vector_store.retrieve("payment authorization", top_k=1)

    assert len(matches) == 1
    assert "Current policy about payment authorization." in matches[0].matched_chunk
    assert "Legacy policy" not in matches[0].matched_chunk


def test_repository_policy_index_contains_current_standalone_text():
    policies = load_all_policies()
    _build_index_or_skip(policies)

    collection = vector_store._client().get_collection(vector_store.COLLECTION_NAME)
    result = collection.get()
    documents = result["documents"]

    assert documents is not None
    assert len(documents) == 3
    joined_documents = "\n".join(documents)
    normalized_documents = " ".join(joined_documents.split())
    assert "ERP connector" in normalized_documents
    assert "approval procedure" in normalized_documents
    assert "segregation-of-duties principle" in normalized_documents
    assert "HRMS connector" in normalized_documents
    assert "ITSM connector" in normalized_documents
    assert "this policy set" in normalized_documents
