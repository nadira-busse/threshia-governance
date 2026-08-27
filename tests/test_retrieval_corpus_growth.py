"""
Regression tests for retrieval behavior under a larger, more ambiguous
corpus than the three shipped policies.

tests/fixtures/policies/retrieval_corpus/ holds synthetic, test-only
policy documents (never loaded by the shipped runtime in
threshia/policies/documents/, never used to authorize anything real).
They load through the real loader and are indexed/retrieved through the
real threshia.policies.vector_store — these tests exercise that module
directly, not evaluate(), and never touch the real .chroma/ directory.

The corpus exists because the shipped 3-policy set is too small to
exercise TOP_K_POLICIES selectivity or semantic ambiguity between
similarly worded policies. These tests keep only the lasting, non-brittle
structural guarantees: corpus loads, index scales, top-k stays selective,
and the index lifecycle (reuse/rebuild on change/add/remove) holds at
this larger scale. Exact ranking numbers for individual diagnostic
queries are evidence, not codified here, since embedding output for a
specific query/corpus wording pair is not a stable contract to assert on
forever.
"""

import dataclasses
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from threshia.config import TOP_K_POLICIES
from threshia.models.policy import Policy
from threshia.policies import vector_store
from threshia.policies.loader import load_all_policies

CORPUS_DIR = Path(__file__).resolve().parent / "fixtures" / "policies" / "retrieval_corpus"
CORPUS_SIZE = 27


@pytest.fixture(autouse=True)
def isolate_chroma_dir(tmp_path, monkeypatch):
    """Point every test at a temporary ChromaDB directory, never the real one."""
    monkeypatch.setattr(vector_store, "CHROMA_PERSIST_DIR", tmp_path)


@pytest.fixture(scope="module")
def corpus() -> list[Policy]:
    return load_all_policies(CORPUS_DIR)


def _build_index_or_skip(policies: list[Policy], force: bool = False) -> int:
    """Same network-failure skip guard as tests/test_vector_store.py."""
    try:
        return vector_store.build_index(policies, force=force)
    except Exception as e:
        message = str(e).lower()
        network_signals = ("getaddrinfo", "connecterror", "connection", "dns", "timeout")
        if any(signal in message for signal in network_signals):
            pytest.skip(
                "Could not download ChromaDB's embedding model (network/DNS "
                f"issue reaching huggingface.co). Original error: {e}"
            )
        raise


def _extra_policy(policy_id: str) -> Policy:
    return Policy(
        id=policy_id,
        category="test-only",
        risk_level="low",
        applicable_tools=["Test.ExtraTool"],
        source="test fixture",
        content="An additional synthetic policy used only to test index lifecycle behavior.",
        file_path="<memory>",
        never_permitted=["test_only_never_permitted_action"],
    )


# --- Corpus validity ---


def test_synthetic_corpus_loads_through_the_real_loader(corpus):
    """The corpus must use the same structured contract as shipped policies —
    no weakened validation for test fixtures."""
    assert len(corpus) == CORPUS_SIZE
    ids = {p.id for p in corpus}
    assert len(ids) == CORPUS_SIZE  # no duplicate ids
    for policy in corpus:
        assert policy.applicable_tools
        assert policy.never_permitted  # loader requires at least one entry


def test_synthetic_corpus_is_not_the_shipped_runtime_corpus(corpus):
    """Guards against the synthetic fixtures ever being confused with, or
    accidentally merged into, the three shipped runtime policies."""
    shipped = load_all_policies()
    assert len(shipped) == 3
    assert {p.id for p in shipped}.isdisjoint({p.id for p in corpus})


# --- Index build at larger scale (real embeddings; skips on network issues) ---


def test_index_build_seeds_all_documents(corpus):
    count = _build_index_or_skip(corpus, force=True)
    assert count == CORPUS_SIZE


def test_topk_is_selective_under_a_larger_corpus(corpus):
    """
    With corpus_size (27) > TOP_K_POLICIES, retrieval must return only the
    configured top-k — not the entire corpus. This is the core selectivity
    claim from the investigation (section 6.A).
    """
    _build_index_or_skip(corpus, force=True)
    matches = vector_store.retrieve(
        "agent wants to look up an employee's account status", top_k=TOP_K_POLICIES
    )
    assert 0 < len(matches) <= TOP_K_POLICIES < CORPUS_SIZE


def test_build_index_is_idempotent_at_larger_scale(corpus):
    first = _build_index_or_skip(corpus, force=True)
    second = _build_index_or_skip(corpus, force=False)
    assert first == second == CORPUS_SIZE


# --- Index lifecycle (mocked client — fast, deterministic, no embedding model) ---


def test_reuse_when_corpus_unchanged(monkeypatch, corpus):
    collection = MagicMock()
    collection.count.return_value = CORPUS_SIZE
    collection.metadata = {
        vector_store.POLICY_FINGERPRINT_KEY: vector_store._policy_fingerprint(corpus)
    }
    client = MagicMock()
    client.get_or_create_collection.return_value = collection
    monkeypatch.setattr(vector_store, "_client", lambda: client)

    count = vector_store.build_index(corpus)

    assert count == CORPUS_SIZE
    client.delete_collection.assert_not_called()
    collection.add.assert_not_called()


def test_rebuild_when_one_policy_content_changes(monkeypatch, corpus):
    changed = list(corpus)
    changed[0] = dataclasses.replace(changed[0], content=changed[0].content + " Updated wording.")

    existing = MagicMock()
    existing.count.return_value = CORPUS_SIZE
    existing.metadata = {
        vector_store.POLICY_FINGERPRINT_KEY: vector_store._policy_fingerprint(corpus)
    }
    rebuilt = MagicMock()
    rebuilt.count.return_value = CORPUS_SIZE
    client = MagicMock()
    client.get_or_create_collection.side_effect = [existing, rebuilt]
    monkeypatch.setattr(vector_store, "_client", lambda: client)

    assert vector_store._policy_fingerprint(corpus) != vector_store._policy_fingerprint(changed)

    count = vector_store.build_index(changed)

    assert count == CORPUS_SIZE
    client.delete_collection.assert_called_once_with(vector_store.COLLECTION_NAME)
    rebuilt.add.assert_called_once()
    assert len(rebuilt.add.call_args.kwargs["documents"]) == CORPUS_SIZE


def test_rebuild_when_a_policy_is_added(monkeypatch, corpus):
    grown = [*corpus, _extra_policy("eval-extra-added-001")]

    existing = MagicMock()
    existing.count.return_value = CORPUS_SIZE
    existing.metadata = {
        vector_store.POLICY_FINGERPRINT_KEY: vector_store._policy_fingerprint(corpus)
    }
    rebuilt = MagicMock()
    rebuilt.count.return_value = CORPUS_SIZE + 1
    client = MagicMock()
    client.get_or_create_collection.side_effect = [existing, rebuilt]
    monkeypatch.setattr(vector_store, "_client", lambda: client)

    count = vector_store.build_index(grown)

    assert count == CORPUS_SIZE + 1
    client.delete_collection.assert_called_once_with(vector_store.COLLECTION_NAME)
    rebuilt.add.assert_called_once()
    assert len(rebuilt.add.call_args.kwargs["ids"]) == CORPUS_SIZE + 1


def test_rebuild_when_a_policy_is_removed(monkeypatch, corpus):
    shrunk = corpus[1:]  # drop one policy

    existing = MagicMock()
    existing.count.return_value = CORPUS_SIZE
    existing.metadata = {
        vector_store.POLICY_FINGERPRINT_KEY: vector_store._policy_fingerprint(corpus)
    }
    rebuilt = MagicMock()
    rebuilt.count.return_value = CORPUS_SIZE - 1
    client = MagicMock()
    client.get_or_create_collection.side_effect = [existing, rebuilt]
    monkeypatch.setattr(vector_store, "_client", lambda: client)

    count = vector_store.build_index(shrunk)

    assert count == CORPUS_SIZE - 1
    client.delete_collection.assert_called_once_with(vector_store.COLLECTION_NAME)
    rebuilt.add.assert_called_once()
    assert len(rebuilt.add.call_args.kwargs["ids"]) == CORPUS_SIZE - 1


def test_document_count_matches_current_corpus_count_after_rebuild(monkeypatch, corpus):
    """Sanity check: the reported count always reflects the corpus just
    indexed, not a stale prior corpus size, across a rebuild."""
    old = corpus[:10]
    existing = MagicMock()
    existing.count.return_value = len(old)
    existing.metadata = {
        vector_store.POLICY_FINGERPRINT_KEY: vector_store._policy_fingerprint(old)
    }
    rebuilt = MagicMock()
    rebuilt.count.return_value = CORPUS_SIZE
    client = MagicMock()
    client.get_or_create_collection.side_effect = [existing, rebuilt]
    monkeypatch.setattr(vector_store, "_client", lambda: client)

    count = vector_store.build_index(corpus)

    assert count == CORPUS_SIZE
