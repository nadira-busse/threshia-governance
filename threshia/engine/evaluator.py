"""
Governance engine — rule-first evaluation.

Evaluation order:
    1. Never-permitted check — does the tool_name appear on any policy's
       never-permitted list? If so: BLOCK immediately, regardless of
       anything else in the tool call. This runs first and cannot be
       overridden by a later ALLOW.
    2. Policy match — does any policy's applicable_tools list this tool?
       If a policy covers it, proceed to gating (step 3).
       If no policy covers it, attempt semantic evaluation (step 2b)
       before falling back to FLAG.
    2b. Semantic evaluation — if ChromaDB is installed and the configured
        provider (THRESHIA_PROVIDER, default "mistral") has its API key set,
        retrieve the most relevant policy content and ask that provider to
        reason about the uncovered tool call. If ChromaDB isn't installed,
        the provider name isn't recognized, its key isn't set, or
        retrieval finds nothing, this step is skipped entirely and
        behavior is identical to not having this layer at all —
        decision_source="rule", FLAG, as before. If the LLM call itself
        fails after a semantic match was found, decision_source="fallback".
    3. Gating check — for each matching policy, is this tool in that
       policy's gated_tools? If so, it only gets ALLOW when the ToolCall's
       parameters carry evidence of human approval
       (parameters["human_approval_evidenced"] is True). Otherwise: FLAG.
    4. If every matching policy is satisfied: ALLOW.
"""

import time

from threshia.models.policy import Policy, PolicyMatch
from threshia.models.tool_call import ToolCall
from threshia.models.verdict import Verdict
from threshia.rules.never_permitted import extract_all_never_permitted_actions


def _try_semantic_evaluation(
    tool_call: ToolCall, policies: list[Policy], start: float
) -> Verdict | None:
    """
    Attempt retrieval + LLM evaluation for a tool call no policy covers.

    Returns None if the feature isn't available (chromadb not installed,
    no API key configured, or retrieval found nothing) — callers should
    treat None as "fall back to the standard rule-based FLAG", not as
    a failure.
    """
    try:
        from threshia.policies import vector_store
    except ImportError:
        return None  # chromadb not installed — feature not available yet

    from threshia.config import PROVIDER, TOP_K_POLICIES
    from threshia.providers.base import ProviderError, get_provider

    try:
        provider_is_configured, provider_evaluate = get_provider(PROVIDER)
    except ProviderError:
        return None  # THRESHIA_PROVIDER set to an unrecognized name

    if not provider_is_configured():
        return None  # this provider's API key isn't set — feature not available yet

    vector_store.build_index(policies)  # idempotent: only seeds if empty
    query_text = f"Tool call: {tool_call.tool_name}. Parameters: {tool_call.parameters}"
    retrieved = vector_store.retrieve(query_text, top_k=TOP_K_POLICIES)

    if not retrieved:
        return None  # empty index or no match — fall back to standard FLAG

    policies_by_id = {p.id: p for p in policies}
    retrieved_texts = [
        policies_by_id[m.policy_id].content
        for m in retrieved
        if m.policy_id in policies_by_id
    ]

    try:
        result = provider_evaluate(tool_call.tool_name, tool_call.parameters, retrieved_texts)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return Verdict(
            decision=result["decision"],
            tool_call=tool_call,
            matched_policies=retrieved,
            reasoning=result["reasoning"],
            decision_source="llm",
            retrieval_score=retrieved[0].relevance_score,
            policy_coverage=len(retrieved),
            provider=PROVIDER,
            evaluation_ms=elapsed_ms,
        )
    except ProviderError as e:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return Verdict(
            decision="FLAG",
            tool_call=tool_call,
            matched_policies=retrieved,
            reasoning=(
                f"Semantic match found but LLM evaluation failed, defaulting "
                f"to FLAG for safety. Error: {e}"
            ),
            decision_source="fallback",
            retrieval_score=retrieved[0].relevance_score,
            policy_coverage=len(retrieved),
            provider=PROVIDER,
            evaluation_ms=elapsed_ms,
            fallback_reason=str(e),
        )


def evaluate(tool_call: ToolCall, policies: list[Policy]) -> Verdict:
    """Evaluate a single tool call against the loaded policy set."""
    start = time.perf_counter()

    # Step 1: never-permitted check, across all policies at once.
    never_permitted_lookup = extract_all_never_permitted_actions(policies)
    if tool_call.tool_name in never_permitted_lookup:
        blocking_policy_id = never_permitted_lookup[tool_call.tool_name]
        blocking_policy = next(p for p in policies if p.id == blocking_policy_id)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return Verdict(
            decision="BLOCK",
            tool_call=tool_call,
            matched_policies=[
                PolicyMatch(
                    policy_id=blocking_policy.id,
                    category=blocking_policy.category,
                    relevance_score=1.0,
                    matched_chunk=f"never-permitted action: {tool_call.tool_name}",
                )
            ],
            reasoning=(
                f"'{tool_call.tool_name}' appears on the never-permitted list "
                f"in policy '{blocking_policy.id}'. This action is blocked "
                f"regardless of approval evidence or other context."
            ),
            decision_source="rule",
            retrieval_score=None,
            policy_coverage=1,
            provider="none",
            evaluation_ms=elapsed_ms,
        )

    # Step 2: find policies whose applicable_tools cover this tool.
    matches = [p for p in policies if tool_call.tool_name in p.applicable_tools]

    if not matches:
        # Step 2b: try semantic retrieval + LLM before defaulting to FLAG.
        semantic_verdict = _try_semantic_evaluation(tool_call, policies, start)
        if semantic_verdict is not None:
            return semantic_verdict

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return Verdict(
            decision="FLAG",
            tool_call=tool_call,
            matched_policies=[],
            reasoning=(
                f"No loaded policy covers tool '{tool_call.tool_name}'. "
                f"Defaulting to FLAG for human review rather than allowing "
                f"an ungoverned action to proceed."
            ),
            decision_source="rule",
            retrieval_score=None,
            policy_coverage=0,
            provider="none",
            evaluation_ms=elapsed_ms,
        )

    # Step 3: check gating on each matching policy.
    policy_matches = [
        PolicyMatch(
            policy_id=p.id,
            category=p.category,
            relevance_score=1.0,
            matched_chunk=f"applicable_tools match: {tool_call.tool_name}",
        )
        for p in matches
    ]

    for policy in matches:
        if tool_call.tool_name in policy.gated_tools:
            evidenced = bool(tool_call.parameters.get("human_approval_evidenced", False))
            if not evidenced:
                elapsed_ms = int((time.perf_counter() - start) * 1000)
                return Verdict(
                    decision="FLAG",
                    tool_call=tool_call,
                    matched_policies=policy_matches,
                    reasoning=(
                        f"'{tool_call.tool_name}' is a gated tool under policy "
                        f"'{policy.id}' and requires evidenced human approval "
                        f"before it may proceed. No approval evidence was "
                        f"found in this tool call's parameters."
                    ),
                    decision_source="rule",
                    retrieval_score=None,
                    policy_coverage=len(matches),
                    provider="none",
                    evaluation_ms=elapsed_ms,
                )

    # Step 4: every matching policy is satisfied.
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    return Verdict(
        decision="ALLOW",
        tool_call=tool_call,
        matched_policies=policy_matches,
        reasoning=(
            f"'{tool_call.tool_name}' is covered by {len(matches)} polic"
            f"{'y' if len(matches) == 1 else 'ies'} and is not gated, or its "
            f"approval evidence requirement is satisfied."
        ),
        decision_source="rule",
        retrieval_score=None,
        policy_coverage=len(matches),
        provider="none",
        evaluation_ms=elapsed_ms,
    )


def evaluate_and_log(tool_call: ToolCall, policies: list[Policy]) -> Verdict:
    """
    Convenience wrapper: evaluate a tool call and append the resulting
    Verdict to the audit log in one call. Use this in real usage; use
    evaluate() directly in tests, where you don't want every test run
    writing to audit.jsonl.
    """
    from threshia.audit.logger import log_verdict

    verdict = evaluate(tool_call, policies)
    log_verdict(verdict)
    return verdict
