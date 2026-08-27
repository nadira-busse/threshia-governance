"""
Execution result model.

ExecutionResult answers a different question than Verdict:

    Verdict           -> what is the governance decision?
    ExecutionResult    -> what happened at the enforcement boundary?

They are kept as separate types rather than merged: a Verdict is the
governance decision produced by evaluate(), independent of whether the
governed external tool was ever executed. An ExecutionResult only exists on
the enforcement path (threshia/execution/guard.py) and always carries the
Verdict it was derived from, so the governance decision remains
inspectable either way.
"""

from dataclasses import dataclass
from typing import Any, Literal

from threshia.models.verdict import Verdict

# Valid execution statuses — used for validation.
VALID_EXECUTION_STATUSES = {"EXECUTED", "DENIED", "REVIEW_REQUIRED"}

# Each status corresponds to exactly one Verdict.decision. This mapping is
# enforced in ExecutionResult.__post_init__ so the two can never disagree.
_STATUS_FOR_DECISION = {
    "ALLOW": "EXECUTED",
    "BLOCK": "DENIED",
    "FLAG": "REVIEW_REQUIRED",
}


@dataclass(frozen=True)
class ExecutionResult:
    """The outcome of one governed_execute() call.

    Attributes:
        status: "EXECUTED" (verdict was ALLOW), "DENIED" (verdict was
                BLOCK), or "REVIEW_REQUIRED" (verdict was FLAG — a human
                or external review process must decide what happens
                next; Threshia does not own that process).
        verdict: The authoritative Verdict this result was derived from.
                 Always present, regardless of status.
        executed: True exactly when status == "EXECUTED". Duplicated
                  alongside `status` so a caller can branch on a plain
                  boolean without matching status strings.
        result: The executor's return value. Only ever set when
                executed is True; None for DENIED and REVIEW_REQUIRED,
                and also None if the executor legitimately returned
                None itself.
    """

    status: Literal["EXECUTED", "DENIED", "REVIEW_REQUIRED"]
    verdict: Verdict
    executed: bool
    result: Any = None

    def __post_init__(self) -> None:
        if self.status not in VALID_EXECUTION_STATUSES:
            raise ValueError(
                f"Invalid status '{self.status}'. "
                f"Must be one of: {VALID_EXECUTION_STATUSES}"
            )
        expected_status = _STATUS_FOR_DECISION[self.verdict.decision]
        if self.status != expected_status:
            raise ValueError(
                f"status '{self.status}' is inconsistent with verdict.decision "
                f"'{self.verdict.decision}' (expected '{expected_status}')."
            )
        if self.executed != (self.status == "EXECUTED"):
            raise ValueError("executed must be True exactly when status is 'EXECUTED'.")
        if not self.executed and self.result is not None:
            raise ValueError("result must be None when executed is False.")
