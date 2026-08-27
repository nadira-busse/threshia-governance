"""Threshia policy-enforcement execution boundary."""

from threshia.execution.guard import governed_execute
from threshia.execution.result import ExecutionResult

__all__ = ["ExecutionResult", "governed_execute"]
