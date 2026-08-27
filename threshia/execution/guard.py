"""
Execution/enforcement boundary.

threshia/engine/evaluator.py is a policy decision point: evaluate() answers
"what is the governance decision?" and returns a Verdict. It does not execute
the governed external tool or write the audit log. Returning a Verdict alone
does not enforce anything — a caller can receive BLOCK or FLAG and invoke the real tool
anyway, since nothing stops it. governed_execute() closes that gap for
callers who want it: it evaluates, then enforces the resulting verdict by
calling the supplied executor only for ALLOW, exactly once, and never for
BLOCK or FLAG.

Threshia stays tool-agnostic here: `executor` is any callable the
integrating caller already owns (an MCP client call, an internal function,
whatever actually runs the tool). Threshia does not register tools, hold
credentials, retry, queue, or know anything about the executor's
implementation — see threshia/execution/result.py for what it does track.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from threshia.audit.logger import AuditConfig, log_verdict
from threshia.engine.evaluator import SemanticConfig, evaluate
from threshia.execution.result import ExecutionResult
from threshia.models.policy import Policy
from threshia.models.tool_call import ToolCall


def governed_execute(
    tool_call: ToolCall,
    policies: list[Policy],
    executor: Callable[[ToolCall], Any],
    *,
    audit_config: AuditConfig | None = None,
    audit_log_path: Path | None = None,
    semantic_config: SemanticConfig | None = None,
) -> ExecutionResult:
    """
    Evaluate tool_call, then enforce the resulting verdict.

    - ALLOW: executor(tool_call) is called exactly once; its return value
      is preserved in the returned ExecutionResult.result.
    - BLOCK: executor is never called; result reports "DENIED".
    - FLAG: executor is never called; result reports "REVIEW_REQUIRED".
      Threshia does not create or own any review workflow — routing a
      REVIEW_REQUIRED result to one is entirely the caller's concern.

    Governance evaluation always happens before any execution attempt,
    and only explicit deterministic policy coverage can produce ALLOW
    (see threshia/models/verdict.py) — a provider suggestion for an
    uncovered tool can never reach the executor through this boundary.

    semantic_config is forwarded unchanged to evaluate() — it controls
    what tool-call parameter values (if any) are disclosed to an external
    LLM provider on the semantic advisory path (see SemanticConfig,
    threshia/engine/evaluator.py). governed_execute() does no filtering
    of its own; the evaluator remains the single owner of that
    minimization boundary. Leave it as None (the default) for the same
    deny-by-default behavior evaluate() already has: no parameter names
    or values leave the process toward a provider.

    audit_config is a separate, independent trust boundary: it controls
    what tool-call parameter values (if any) are persisted to the audit
    log, not what is disclosed to a provider. A key allowlisted for one
    is not implicitly allowlisted for the other — the caller sets each
    independently. Audit logging is opt-in and explicit, and reuses the
    same threshia.audit.logger.log_verdict()/AuditConfig path as
    evaluate_and_log() — there is no second audit serialization path and
    no change to its data-minimization behavior (see
    threshia/audit/logger.py). Pass audit_config to have the verdict
    logged; leave it as None (the default) for no audit side effects at
    all. When requested, exactly one audit entry is written — for ALLOW,
    BLOCK, and FLAG alike — before the executor is invoked. An ALLOW audit
    entry records the governance authorization before execution. It does
    not prove that the executor was invoked or that execution succeeded.
    If executor raises, that exception propagates directly out of
    governed_execute() — after the audit entry (if requested) has already
    been written — and is never converted into a governance decision,
    retried, or logged as a second entry.
    """
    verdict = evaluate(tool_call, policies, semantic_config=semantic_config)

    if audit_config is not None:
        log_verdict(verdict, log_path=audit_log_path, config=audit_config)

    if verdict.decision == "ALLOW":
        result = executor(tool_call)
        return ExecutionResult(status="EXECUTED", verdict=verdict, executed=True, result=result)

    if verdict.decision == "BLOCK":
        return ExecutionResult(status="DENIED", verdict=verdict, executed=False)

    return ExecutionResult(status="REVIEW_REQUIRED", verdict=verdict, executed=False)
