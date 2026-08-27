"""
Audit logging.

When audit logging is enabled, this module persists a Verdict as one JSON
line in audit.jsonl. JSON Lines keeps each record independently readable
and allows new records to be appended without rewriting the existing log.

Logging is kept separate from evaluate() itself (see threshia/engine/
evaluator.py) — evaluate() does not write the audit log, which makes it
straightforward to unit test without touching disk. (evaluate() can still
have effects of its own on the optional semantic path — building/updating
the persisted Chroma index, calling an external LLM provider — it just
never writes audit.jsonl.) Use evaluate_and_log() from the engine module,
or threshia/execution/guard.py's governed_execute() for a boundary that
also enforces the verdict, when you want evaluation and logging together.

Data minimization: tool_call.parameters is an unconstrained dict[str, Any]
that the *caller* populates with whatever a tool actually needs — Threshia
has no way to know in advance whether any given key holds routine data or
something like a salary, a medical note, or a token. build_audit_record()
therefore never persists parameter values by default; only keys explicitly
named in AuditConfig.parameter_allowlist are copied into the persisted
record. This is deny-by-default persistence, not sensitive-data detection —
Threshia does not attempt to guess which field names are sensitive, and
naming a key in the allowlist is the integrating caller's decision, not a
claim by Threshia that the value is safe.
"""

import dataclasses
import json
from dataclasses import dataclass, field
from pathlib import Path

from threshia.config import AUDIT_LOG_PATH
from threshia.models.verdict import Verdict


@dataclass(frozen=True)
class AuditConfig:
    """
    Controls what beyond governance decision metadata is persisted to the
    audit log.

    Attributes:
        parameter_allowlist: tool-call parameter keys to persist verbatim,
            when present on the call being logged. Empty by default, which
            means no parameter values are persisted — see the module
            docstring for why this is deny-by-default rather than a
            redaction list. No wildcard or pattern matching is supported:
            each key must be named explicitly.
    """

    parameter_allowlist: frozenset[str] = field(default_factory=frozenset)


def build_audit_record(verdict: Verdict, config: AuditConfig | None = None) -> dict:
    """
    Build the plain-dict record persisted for one Verdict.

    Governance decision metadata (decision, matched policies, provider,
    timing, reasoning, etc.) is always included — that's the audit log's
    reason to exist. tool_call.parameters is excluded by default; only
    keys named in config.parameter_allowlist are copied over, and only
    when present on this particular call (a missing allowlisted key is
    not an error). human_approval_evidenced is recorded as an explicit
    boolean control state separately from `parameters`, since it's a
    fixed key Threshia's own gating logic already reads (see
    threshia/engine/evaluator.py) — not an arbitrary caller field.
    """
    cfg = config if config is not None else AuditConfig()
    tool_call = verdict.tool_call

    persisted_parameters = {
        key: tool_call.parameters[key]
        for key in cfg.parameter_allowlist
        if key in tool_call.parameters
    }

    return {
        "decision": verdict.decision,
        "decision_source": verdict.decision_source,
        "reasoning": verdict.reasoning,
        "provider": verdict.provider,
        "provider_suggested_decision": verdict.provider_suggested_decision,
        "matched_policies": [dataclasses.asdict(m) for m in verdict.matched_policies],
        "retrieval_score": verdict.retrieval_score,
        "policy_coverage": verdict.policy_coverage,
        "evaluation_ms": verdict.evaluation_ms,
        "fallback_reason": verdict.fallback_reason,
        "timestamp": verdict.timestamp,
        "human_approval_evidenced": tool_call.parameters.get("human_approval_evidenced")
        is True,
        "tool_call": {
            "tool_name": tool_call.tool_name,
            "agent_id": tool_call.agent_id,
            "timestamp": tool_call.timestamp,
            "parameters": persisted_parameters,
        },
    }


def log_verdict(
    verdict: Verdict,
    log_path: Path | None = None,
    config: AuditConfig | None = None,
) -> None:
    """
    Append a single Verdict to the audit log as one JSON line.

    build_audit_record() decides what's in the persisted record — see its
    docstring and the module docstring for the parameter data-minimization
    boundary. json.dumps(..., default=str) handles the datetime fields
    (timestamp on both Verdict and ToolCall), which aren't JSON-serializable
    by default — they're written out as ISO-format strings instead.
    """
    path = log_path if log_path is not None else AUDIT_LOG_PATH
    entry = build_audit_record(verdict, config)

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, default=str) + "\n")


def read_audit_log(log_path: Path | None = None) -> list[dict]:
    """
    Read every logged verdict back as a list of plain dicts, in the order
    they were written. Returns an empty list if the log doesn't exist yet
    — a fresh project with no evaluations run is not an error.
    """
    path = log_path if log_path is not None else AUDIT_LOG_PATH
    if not path.exists():
        return []

    entries = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped:
                entries.append(json.loads(stripped))
    return entries
