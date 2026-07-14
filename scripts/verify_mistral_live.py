"""
Live Mistral verification — calls the REAL Mistral API, not a mock.

This is deliberately NOT part of the automated test suite or CI: it costs
a real API call and depends on network access and a real MISTRAL_API_KEY,
neither of which belong in a suite that should run offline and for free
on every push. Run this manually whenever you want to confirm the LLM
layer still works end to end against the actual API — e.g. after a
Mistral API change, or before mentioning this layer in an interview.

Setup:
    1. Get a Mistral API key: https://console.mistral.ai/
    2. Add it to your local .env file:
           MISTRAL_API_KEY=your-key-here
    3. Run:
           python scripts/verify_mistral_live.py

This evaluates one tool call that no policy explicitly covers
(Sales.CreateDiscountOffer — Kelvior's Sales Proposal Agent isn't one of
the three agents Threshia has a policy for), so the engine has to fall
through to semantic retrieval + a real Mistral call to produce a verdict.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from threshia.config import MISTRAL_API_KEY
from threshia.engine.evaluator import evaluate
from threshia.models.tool_call import ToolCall
from threshia.policies.loader import load_all_policies


def main() -> int:
    if not MISTRAL_API_KEY:
        print(
            "MISTRAL_API_KEY is not set. Add it to your .env file first "
            "(see the docstring at the top of this script)."
        )
        return 1

    policies = load_all_policies()
    tool_call = ToolCall(
        tool_name="Sales.CreateDiscountOffer",
        parameters={"discount_percent": 15, "customer_tier": "standard"},
    )

    print(f"Evaluating: {tool_call.tool_name}({tool_call.parameters})")
    print("No policy covers this tool directly — this will exercise "
          "ChromaDB retrieval + a real Mistral API call.\n")

    verdict = evaluate(tool_call, policies)

    print(f"Verdict          : {verdict.decision}")
    print(f"Decision source  : {verdict.decision_source}")
    print(f"Reasoning        : {verdict.reasoning}")
    print(f"Policy coverage  : {verdict.policy_coverage}")
    print(f"Retrieval score  : {verdict.retrieval_score}")
    print(f"Provider         : {verdict.provider}")
    print(f"Evaluation time  : {verdict.evaluation_ms}ms")

    if verdict.decision_source == "llm":
        print("\nConfirmed: the real Mistral API was called and returned a "
              "usable verdict.")
        return 0
    elif verdict.decision_source == "fallback":
        print("\nRetrieval found a semantic match, but the Mistral call "
              "itself failed. See the reasoning above for the error.")
        return 1
    else:
        print("\nUnexpected: this evaluated via the rule path, not the LLM "
              "path. Check that no policy accidentally covers this tool name.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
