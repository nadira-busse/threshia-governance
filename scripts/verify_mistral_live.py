"""
Live Mistral verification — calls the REAL Mistral API, not a mock.

Manually verifies that the current provider integration can complete the
live semantic-provider path: retrieval, the real API call, response
parsing, and Threshia's authoritative FLAG result for an uncovered tool.
This is deliberately NOT part of the automated test suite or CI: it costs
a real API call and depends on network access and a real MISTRAL_API_KEY,
neither of which belong in a suite that should run offline and for free
on every push. Run this manually after a Mistral API change or a change
to the prompt/provider adapter, to confirm the integration still works
end to end against the real API rather than a mock.

Setup:
    1. Get a Mistral API key: https://console.mistral.ai/
    2. Add it to your local .env file:
           MISTRAL_API_KEY=your-key-here
    3. Run:
           python scripts/verify_mistral_live.py

`Sales.CreateDiscountOffer` is deliberately not listed by any current policy,
so the engine has to fall through to semantic retrieval + a real Mistral call
to produce a verdict.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from threshia.config import MISTRAL_API_KEY, PROVIDER
from threshia.engine.evaluator import evaluate
from threshia.models.tool_call import ToolCall
from threshia.policies.loader import load_all_policies


def main() -> int:
    if PROVIDER != "mistral":
        print(
            f"THRESHIA_PROVIDER is currently '{PROVIDER}', not 'mistral'. "
            "Set THRESHIA_PROVIDER=mistral in .env (or remove the line, "
            "since mistral is the default) before running this script — "
            "otherwise evaluate() will call whichever provider is "
            "currently configured instead of Mistral."
        )
        return 1

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

    print(f"Authoritative decision : {verdict.decision}")
    print(f"Decision source        : {verdict.decision_source}")
    print(f"Provider suggestion    : {verdict.provider_suggested_decision}")
    print(f"Reasoning              : {verdict.reasoning}")
    print(f"Policy coverage        : {verdict.policy_coverage}")
    print(f"Retrieval score        : {verdict.retrieval_score}")
    print(f"Provider               : {verdict.provider}")
    print(f"Evaluation time        : {verdict.evaluation_ms}ms")

    if verdict.decision_source == "llm":
        print(
            "\nConfirmed: the real Mistral API was called and returned a "
            "usable advisory response. The authoritative decision is "
            f"Threshia's own ({verdict.decision}), not the provider's "
            "suggestion — an uncovered tool can never receive an "
            "authoritative ALLOW from provider output alone."
        )
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
