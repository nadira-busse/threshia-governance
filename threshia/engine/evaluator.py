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
    2b. Semantic evaluation — if the configured provider
        (THRESHIA_PROVIDER, default "mistral") is available and has its API
        key set, retrieve the most relevant policy context and ask that
        provider to reason about the uncovered tool call. If semantic
        retrieval is unavailable in the current environment, the provider
        is not configured, or retrieval finds nothing, this step is skipped
        and the call falls back to the standard rule-based FLAG path. If index construction,
        retrieval, or the LLM call fails after the semantic path starts,
        the engine returns FLAG with decision_source="fallback".

        Only explicit deterministic policy coverage may produce ALLOW
        (see threshia/models/verdict.py). A tool call that reaches this
        step has no policy in its applicable_tools, which means no
        policy explicitly prohibits it either, so the provider's
        suggestion (ALLOW, BLOCK, or FLAG) is never authoritative here:
        this step always returns FLAG when a provider response is
        successfully obtained, with the provider's actual suggestion
        preserved in Verdict.provider_suggested_decision and folded into
        `reasoning`. Semantic retrieval and LLM reasoning inform human
        review; they do not authorize or prohibit an ungoverned action.
        This is enforced in code below, after the provider response is
        parsed and validated — never by relying on prompt wording alone.

        Data minimization on this path: ToolCall.parameters is arbitrary
        caller-supplied data Threshia doesn't own the schema of. Local
        retrieval (ChromaDB, via vector_store.py) runs entirely in-process
        against a local embedding model, so the full ToolCall is fine to
        use there. The external provider request is a different boundary
        — see SemanticConfig below and _try_semantic_evaluation's
        docstring: parameter values are excluded from that request by
        default, and only keys named in SemanticConfig.parameter_allowlist
        are ever included.
    3. Gating check — for each matching policy, is this tool in that
       policy's gated_tools? If so, it only gets ALLOW when the ToolCall's
       parameters carry evidence of human approval
       (parameters["human_approval_evidenced"] is True). Otherwise: FLAG.
    4. If every matching policy is satisfied: ALLOW.
"""

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from threshia.models.policy import Policy, PolicyMatch
from threshia.models.tool_call import ToolCall
from threshia.models.verdict import Verdict
from threshia.rules.never_permitted import build_never_permitted_lookup

if TYPE_CHECKING:
    from threshia.audit.logger import AuditConfig


@dataclass(frozen=True)
class SemanticConfig:
    """
    Controls what ToolCall.parameters is disclosed to an external LLM
    provider (Mistral/OpenAI) on the semantic advisory path — see
    _try_semantic_evaluation() below.

    Attributes:
        parameter_allowlist: parameter keys — both the key name and its
            value — to include in the outbound provider request, when
            present on the call being evaluated. Empty by default: no
            parameter values, and no parameter names, leave the process
            toward the provider. Parameter *names* (e.g. "medical_note",
            "salary") can reveal domain context on their own, so the
            default excludes names too, not just values. No wildcard or
            pattern matching is supported: each key must be named
            explicitly. This is deny-by-default disclosure, not
            sensitive-field detection — Threshia does not attempt to
            guess which caller-defined parameter names or values are
            safe to send externally; naming a key here is the
            integrating caller's decision.

    Only the outbound provider request is affected. Local deterministic
    evaluation and local semantic retrieval (ChromaDB) always see the
    full, real ToolCall.parameters — this config narrows what leaves the
    process, not what Threshia evaluates locally.
    """

    parameter_allowlist: frozenset[str] = field(default_factory=frozenset)


def _authoritative_uncovered_verdict(
    *,
    tool_call: ToolCall,
    matched_policies: list[PolicyMatch],
    provider_decision: str,
    provider_reasoning: str,
    provider_name: str,
    retrieval_score: float,
    policy_coverage: int,
    evaluation_ms: int,
) -> Verdict:
    """
    Build the Verdict for a successful provider response to an uncovered
    tool call, enforcing: only explicit deterministic policy coverage may
    produce ALLOW (see threshia/models/verdict.py).

    A tool call reaches this function only because no policy's
    applicable_tools covers it — by the same logic, no policy explicitly
    prohibits it either, so the provider's suggestion is never
    authoritative here, whether it was ALLOW, BLOCK, or FLAG. This always
    returns decision="FLAG". The provider's actual suggestion is never
    dropped: it's preserved in provider_suggested_decision (when it
    differs from FLAG) and always folded into `reasoning`, so a reader of
    the Verdict or the audit log can see what the provider recommended
    without mistaking it for what Threshia authorized.

    This is a deliberate code-level enforcement point, independent of
    prompt wording — see tests/test_semantic_evaluation.py's
    test_uncovered_tool_provider_allow_is_never_authoritative and the
    Weather.GetForecast-modeled regression for the failure this closes.
    """
    if provider_decision == "FLAG":
        reasoning = (
            f"No policy explicitly covers '{tool_call.tool_name}'. Semantic "
            f"review found related policy context but did not reach a "
            f"confident recommendation either: {provider_reasoning}"
        )
        provider_suggested_decision = None
    else:
        reasoning = (
            f"No policy explicitly covers '{tool_call.tool_name}', so this "
            f"tool call has no deterministic policy basis for ALLOW or "
            f"BLOCK. Semantic review suggested {provider_decision} "
            f"({provider_reasoning}), but only explicit deterministic "
            f"policy coverage may authorize or prohibit a tool call "
            f"outright — semantic analysis is advisory review context, not "
            f"authorization. Returning FLAG for human review."
        )
        provider_suggested_decision = provider_decision

    return Verdict(
        decision="FLAG",
        tool_call=tool_call,
        matched_policies=matched_policies,
        reasoning=reasoning,
        decision_source="llm",
        retrieval_score=retrieval_score,
        policy_coverage=policy_coverage,
        provider=provider_name,
        evaluation_ms=evaluation_ms,
        provider_suggested_decision=provider_suggested_decision,
    )


def _semantic_provider_parameters(
    parameters: dict, semantic_config: SemanticConfig
) -> dict:
    """
    Build the parameter dict included in the outbound provider request.

    Deny-by-default: only keys named in
    semantic_config.parameter_allowlist are copied over, and only when
    present on this particular call — a missing allowlisted key is not an
    error. See SemanticConfig's docstring for why this excludes parameter
    names, not just values, by default.
    """
    return {
        key: parameters[key]
        for key in semantic_config.parameter_allowlist
        if key in parameters
    }


def _try_semantic_evaluation(
    tool_call: ToolCall,
    policies: list[Policy],
    start: float,
    semantic_config: SemanticConfig,
) -> Verdict | None:
    """
    Attempt retrieval + LLM evaluation for a tool call no policy covers.

    Returns None if semantic evaluation cannot proceed (for example, the
    semantic retrieval integration is unavailable, no API key is configured,
    or retrieval finds no matching context). Callers should treat None as
    "fall back to the standard rule-based FLAG", not as a failure.
    """
    try:
        from threshia.policies import vector_store
    except ImportError:
        return None  # semantic retrieval unavailable in the current environment

    from threshia.config import PROVIDER, TOP_K_POLICIES
    from threshia.providers.base import ProviderError, get_provider

    try:
        provider_is_configured, provider_evaluate = get_provider(PROVIDER)
    except ProviderError:
        return None  # THRESHIA_PROVIDER set to an unrecognized name

    if not provider_is_configured():
        return None  # this provider's API key isn't set — feature not available yet

    try:
        vector_store.build_index(policies)
        # Local retrieval only — runs in-process against ChromaDB's local
        # embedding model, never transmitted anywhere. The full ToolCall
        # is fine to use here; the external-provider boundary is below.
        query_text = f"Tool call: {tool_call.tool_name}. Parameters: {tool_call.parameters}"
        retrieved = vector_store.retrieve(query_text, top_k=TOP_K_POLICIES)
    except Exception as e:
        # Chroma and its embedding stack expose several exception types.
        # Catch them only at this optional integration boundary so direct,
        # deterministic policy errors are never hidden.
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return Verdict(
            decision="FLAG",
            tool_call=tool_call,
            matched_policies=[],
            reasoning=(
                "Semantic index or retrieval failed, defaulting to FLAG "
                f"for safety. Error: {e}"
            ),
            decision_source="fallback",
            retrieval_score=None,
            policy_coverage=0,
            provider=PROVIDER,
            evaluation_ms=elapsed_ms,
            fallback_reason=str(e),
        )

    if not retrieved:
        return None  # empty index or no match — fall back to standard FLAG

    policies_by_id = {p.id: p for p in policies}
    retrieved_texts = [
        policies_by_id[m.policy_id].content
        for m in retrieved
        if m.policy_id in policies_by_id
    ]

    try:
        # External-provider boundary: only tool_name, retrieved policy
        # text, and explicitly allowlisted parameters (default: none) are
        # sent — never the full ToolCall.parameters. See SemanticConfig.
        outbound_parameters = _semantic_provider_parameters(
            tool_call.parameters, semantic_config
        )
        result = provider_evaluate(tool_call.tool_name, outbound_parameters, retrieved_texts)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return _authoritative_uncovered_verdict(
            tool_call=tool_call,
            matched_policies=retrieved,
            provider_decision=result["decision"],
            provider_reasoning=result["reasoning"],
            provider_name=PROVIDER,
            retrieval_score=retrieved[0].relevance_score,
            policy_coverage=len(retrieved),
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


def evaluate(
    tool_call: ToolCall,
    policies: list[Policy],
    semantic_config: SemanticConfig | None = None,
) -> Verdict:
    """
    Evaluate a single tool call against the loaded policy set.

    semantic_config controls what ToolCall.parameters (if anything) is
    disclosed to an external LLM provider on the semantic advisory path
    (see SemanticConfig above) — it has no effect on the deterministic
    rule/gating steps below, which always see the full, real
    tool_call.parameters. Defaults to SemanticConfig() (empty allowlist):
    no parameter values or names leave the process.
    """
    resolved_semantic_config = (
        semantic_config if semantic_config is not None else SemanticConfig()
    )
    start = time.perf_counter()

    # Step 1: never-permitted check, across all policies at once.
    never_permitted_lookup = build_never_permitted_lookup(policies)
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
        semantic_verdict = _try_semantic_evaluation(
            tool_call, policies, start, resolved_semantic_config
        )
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
            evidenced = tool_call.parameters.get("human_approval_evidenced") is True
            if not evidenced:
                elapsed_ms = int((time.perf_counter() - start) * 1000)
                return Verdict(
                    decision="FLAG",
                    tool_call=tool_call,
                    matched_policies=policy_matches,
                    reasoning=(
                        f"'{tool_call.tool_name}' is a gated tool under policy "
                        f"'{policy.id}' and requires evidenced human approval "
                        f"before it may proceed. The literal boolean True was "
                        f"not found in this tool call's approval field."
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


def evaluate_and_log(
    tool_call: ToolCall,
    policies: list[Policy],
    audit_config: "AuditConfig | None" = None,
    semantic_config: SemanticConfig | None = None,
) -> Verdict:
    """
    Convenience wrapper: evaluate a tool call and append the resulting
    Verdict to the audit log in one call.

    Use this when a caller needs a governance decision plus audit persistence
    without execution enforcement. Use governed_execute() when Threshia should
    also enforce whether the supplied executor may run.

    audit_config controls what tool-call parameter values (if any) are
    persisted — see threshia/audit/logger.py. semantic_config controls
    what tool-call parameter values (if any) are sent to an external LLM
    provider on the semantic advisory path — see SemanticConfig above.
    Neither has any effect on the verdict itself: evaluation always sees
    the full, real ToolCall.parameters; these configs only narrow what
    leaves the process (to the provider) or reaches disk (via the audit
    log) afterward. The caller of evaluate_and_log() is the one
    integrating a specific tool schema, so it's the caller — not
    Threshia — who decides whether any parameter key is safe to disclose
    externally or persist.
    """
    from threshia.audit.logger import log_verdict

    verdict = evaluate(tool_call, policies, semantic_config=semantic_config)
    log_verdict(verdict, config=audit_config)
    return verdict
