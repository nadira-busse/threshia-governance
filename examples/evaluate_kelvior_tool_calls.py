"""
Demo: evaluate a handful of Kelvior-style tool calls through Threshia.

Run with:
    python examples/evaluate_kelvior_tool_calls.py

This loads the real policy documents from threshia/policies/documents/,
evaluates five tool calls that span every verdict path the engine
supports, and prints each Verdict. No API key or ChromaDB setup is
required — these examples are all resolved by the rule layer alone.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from threshia.engine.evaluator import evaluate
from threshia.models.tool_call import ToolCall
from threshia.policies.loader import load_all_policies

EXAMPLES = [
    (
        "Read-only ERP lookup — no gating, no risk",
        ToolCall(tool_name="ERP.InvoiceLookup", parameters={}),
    ),
    (
        "Controlled ERP action, no approval evidence yet",
        ToolCall(tool_name="ERP.PaymentReviewTrigger", parameters={}),
    ),
    (
        "Same controlled action, now with evidenced human approval",
        ToolCall(
            tool_name="ERP.PaymentReviewTrigger",
            parameters={"human_approval_evidenced": True},
        ),
    ),
    (
        "Never-permitted action — blocked regardless of context",
        ToolCall(
            tool_name="release_payment",
            parameters={"human_approval_evidenced": True},
        ),
    ),
    (
        "Tool no loaded policy covers — fail-safe default, or semantic "
        "layer if a provider is configured in .env",
        ToolCall(tool_name="CRM.DeleteAllCustomers", parameters={}),
    ),
]


def main() -> None:
    policies = load_all_policies()
    print(f"Loaded {len(policies)} policy documents.\n")

    for description, tool_call in EXAMPLES:
        verdict = evaluate(tool_call, policies)
        print(f"— {description}")
        print(f"  Tool call : {tool_call.tool_name}({tool_call.parameters})")
        print(f"  Verdict   : {verdict.decision} (source: {verdict.decision_source})")
        print(f"  Reasoning : {verdict.reasoning}")
        print()


if __name__ == "__main__":
    main()
