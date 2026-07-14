"""
Audit logging.

Every governance decision should leave a trace. This module appends each
Verdict as one JSON line to audit.jsonl (JSON Lines format: one valid JSON
object per line, so the log can be appended to forever without ever
needing to parse or rewrite the whole file).

Logging is kept separate from evaluate() itself (see threshia/engine/
evaluator.py) — evaluate() stays a pure function with no side effects,
which makes it straightforward to unit test. Use evaluate_and_log() from
the engine module when you want both in one call.
"""

import dataclasses
import json
from pathlib import Path

from threshia.config import AUDIT_LOG_PATH
from threshia.models.verdict import Verdict


def log_verdict(verdict: Verdict, log_path: Path | None = None) -> None:
    """
    Append a single Verdict to the audit log as one JSON line.

    dataclasses.asdict() recursively converts the Verdict, its nested
    ToolCall, and its list of PolicyMatch objects into plain dicts.
    json.dumps(..., default=str) handles the datetime fields (timestamp
    on both Verdict and ToolCall), which aren't JSON-serializable by
    default — they're written out as ISO-format strings instead.
    """
    path = log_path if log_path is not None else AUDIT_LOG_PATH
    entry = dataclasses.asdict(verdict)

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
