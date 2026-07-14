"""
Policy vector store — semantic retrieval layer.

Used only when a tool call isn't covered by any policy's applicable_tools
list (see threshia/engine/evaluator.py). Rather than defaulting straight to
FLAG for every unknown tool, this retrieves the most semantically similar
policy content so an LLM can reason about whether it likely applies.

Uses ChromaDB's default local embedding model — no external embedding API
or key required. The persisted index lives in .chroma/ (already excluded
in .gitignore from Sprint 1).
"""

import chromadb

from threshia.config import CHROMA_PERSIST_DIR
from threshia.models.policy import Policy, PolicyMatch

COLLECTION_NAME = "threshia_policies"


def _client() -> chromadb.ClientAPI:
    return chromadb.PersistentClient(path=str(CHROMA_PERSIST_DIR))


def build_index(policies: list[Policy], force: bool = False) -> int:
    """
    Seed the ChromaDB collection from the loaded policies. Idempotent by
    default — only seeds if the collection is empty. Pass force=True to
    wipe and rebuild (e.g. after editing a policy document).

    Returns the number of documents in the collection after seeding.
    """
    client = _client()

    if force:
        try:
            client.delete_collection(COLLECTION_NAME)
        except ValueError:
            pass  # collection didn't exist yet — fine

    collection = client.get_or_create_collection(COLLECTION_NAME)

    if collection.count() > 0 and not force:
        return collection.count()

    collection.add(
        ids=[p.id for p in policies],
        documents=[
            f"Category: {p.category}. Applicable tools: "
            f"{', '.join(p.applicable_tools)}. {p.content}"
            for p in policies
        ],
        metadatas=[{"category": p.category, "risk_level": p.risk_level} for p in policies],
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
