"""
Policy vector store — semantic retrieval layer.

Used only when a tool call isn't covered by any policy's applicable_tools
list (see threshia/engine/evaluator.py). Rather than defaulting straight to
FLAG for every unknown tool, this retrieves the most semantically similar
policy content so an LLM can reason about whether it likely applies.

Uses ChromaDB's default local embedding model — no external embedding API
or key required. The persisted index lives in .chroma/, which is excluded
from version control (see .gitignore).
"""

import hashlib
import json

import chromadb

from threshia.config import CHROMA_PERSIST_DIR
from threshia.models.policy import Policy, PolicyMatch

COLLECTION_NAME = "threshia_policies"
POLICY_FINGERPRINT_KEY = "policy_fingerprint"


def _client() -> chromadb.ClientAPI:
    return chromadb.PersistentClient(path=str(CHROMA_PERSIST_DIR))


def _policy_fingerprint(policies: list[Policy]) -> str:
    """Return a deterministic fingerprint for policy data that can affect the index."""
    canonical_policies = [
        {
            "id": policy.id,
            "category": policy.category,
            "risk_level": policy.risk_level,
            "applicable_tools": sorted(policy.applicable_tools),
            "gated_tools": sorted(policy.gated_tools),
            "never_permitted": sorted(policy.never_permitted),
            "source": policy.source,
            "content": policy.content,
        }
        for policy in policies
    ]
    canonical_policies.sort(
        key=lambda policy: json.dumps(
            policy, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
    )
    payload = json.dumps(
        canonical_policies,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _indexed_document(policy: Policy) -> str:
    """
    Build the text Chroma embeds and searches for this policy.

    `never_permitted` is included explicitly (like `applicable_tools`)
    rather than relied upon to appear in `policy.content`. The Markdown
    body's never-permitted section is human-readable explanation, not the
    machine list (see threshia/rules/never_permitted.py) — it may
    summarize rather than enumerate every blocked action name. Including
    the structured list here keeps the exact action-name strings
    available as semantic-retrieval context regardless of how the body
    prose is worded.
    """
    tools = ", ".join(sorted(policy.applicable_tools))
    never_permitted = ", ".join(sorted(policy.never_permitted))
    return (
        f"Category: {policy.category}. Applicable tools: {tools}. "
        f"Never-permitted actions: {never_permitted}. {policy.content}"
    )


def build_index(policies: list[Policy], force: bool = False) -> int:
    """Make the persisted collection represent the current loaded policies.

    Reuse requires both the current deterministic policy fingerprint and
    the expected document count. A mismatch rebuilds the collection, which
    covers policy changes, additions, removals, and incomplete prior builds.
    Pass force=True to rebuild unconditionally.
    """
    client = _client()
    collection = client.get_or_create_collection(COLLECTION_NAME)
    fingerprint = _policy_fingerprint(policies)
    current_count = collection.count()
    metadata = collection.metadata or {}

    if (
        not force
        and current_count == len(policies)
        and metadata.get(POLICY_FINGERPRINT_KEY) == fingerprint
    ):
        return current_count

    try:
        client.delete_collection(COLLECTION_NAME)
    except ValueError:
        pass  # collection didn't exist yet — fine

    collection = client.get_or_create_collection(
        COLLECTION_NAME,
        metadata={POLICY_FINGERPRINT_KEY: fingerprint},
    )
    ordered_policies = sorted(policies, key=lambda policy: policy.id)
    if ordered_policies:
        collection.add(
            ids=[policy.id for policy in ordered_policies],
            documents=[_indexed_document(policy) for policy in ordered_policies],
            metadatas=[
                {"category": policy.category, "risk_level": policy.risk_level}
                for policy in ordered_policies
            ],
        )
    return collection.count()


def retrieve(query_text: str, top_k: int = 3) -> list[PolicyMatch]:
    """
    Retrieve the top_k most semantically similar policies to query_text.

    Returns an empty list if the collection hasn't been seeded yet
    (call build_index first) rather than raising an error.
    """
    client = _client()
    collection = client.get_or_create_collection(COLLECTION_NAME)

    if collection.count() == 0:
        return []

    n_results = min(top_k, collection.count())
    results = collection.query(query_texts=[query_text], n_results=n_results)

    def first_or_empty(value: list | None) -> list:
        """
        ChromaDB's query() result fields are typed as optional (they can
        be None if that field wasn't requested). Indexing into a possibly-
        None value directly would be a real bug, not just a lint nag, so
        this guards it explicitly rather than assuming the field is
        always present.
        """
        return value[0] if value else []

    matches = []
    ids = first_or_empty(results.get("ids"))
    documents = first_or_empty(results.get("documents"))
    metadatas = first_or_empty(results.get("metadatas"))
    distances = first_or_empty(results.get("distances"))

    for policy_id, doc, meta, distance in zip(ids, documents, metadatas, distances):
        matches.append(
            PolicyMatch(
                policy_id=policy_id,
                category=meta.get("category", "unknown"),
                relevance_score=distance,
                matched_chunk=doc[:300],
            )
        )
    return matches
