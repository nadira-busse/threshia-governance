"""
Mistral provider — LLM reasoning layer.

Called only for tool calls that no policy's applicable_tools list covers,
but that semantic retrieval (vector_store.py) found related policy
content for. Uses Mistral's cloud API directly via urllib (stdlib) rather
than an SDK, since this is one of two external calls this project makes
(see openai_provider.py for the other).

Requires MISTRAL_API_KEY to be set (see .env.example). Without it,
is_configured() returns False and the engine skips this provider entirely,
falling back to the existing rule-based FLAG default — see
threshia/engine/evaluator.py.

Implements the shared provider interface documented in
threshia/providers/base.py: is_configured() and call_mistral() (this
module's name for evaluate()).
"""

import json
import urllib.error
import urllib.request

from threshia.config import MISTRAL_API_KEY, MISTRAL_BASE_URL, MISTRAL_MODEL
from threshia.providers.base import ProviderError, build_prompt, validate_provider_response

# Re-exported so existing imports of `from threshia.providers.mistral_provider
# import ProviderError` keep working — the exception type itself lives in
# base.py so every provider raises (and evaluator.py catches) the same type.
__all__ = ["ProviderError", "is_configured", "call_mistral"]


def is_configured() -> bool:
    """True if MISTRAL_API_KEY is set."""
    return bool(MISTRAL_API_KEY)


def call_mistral(
    tool_name: str,
    parameters: dict,
    retrieved_policy_texts: list[str],
    timeout: int = 20,
) -> dict:
    """
    Calls the Mistral API and returns a dict like:
        {"decision": "FLAG", "reasoning": "..."}

    Raises ProviderError for any failure mode (missing key, network error,
    malformed response) — callers should catch this and fail safe to FLAG.
    """
    if not MISTRAL_API_KEY:
        raise ProviderError("MISTRAL_API_KEY is not set (see .env.example).")

    prompt = build_prompt(tool_name, parameters, retrieved_policy_texts)

    payload = json.dumps(
        {
            "model": MISTRAL_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        f"{MISTRAL_BASE_URL}/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {MISTRAL_API_KEY}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise ProviderError(f"Could not reach Mistral API: {e}")
    except json.JSONDecodeError as e:
        raise ProviderError(f"Mistral API returned non-JSON response: {e}")

    try:
        content = body["choices"][0]["message"]["content"]
        parsed = json.loads(content)
    except (KeyError, IndexError, TypeError) as e:
        raise ProviderError(f"Unexpected Mistral response structure: {e}")
    except json.JSONDecodeError as e:
        raise ProviderError(f"Mistral message content was not valid JSON: {e}")

    return validate_provider_response(parsed, "Mistral")
