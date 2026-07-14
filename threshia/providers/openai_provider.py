"""
OpenAI provider — alternative LLM reasoning layer, alongside Mistral.

Same role as mistral_provider.py (see that module's docstring for the
shared context), using OpenAI's API instead. Switching between them is a
config change: set THRESHIA_PROVIDER=openai and OPENAI_API_KEY in .env — no
code change needed, since threshia/engine/evaluator.py only ever calls
threshia.providers.base.get_provider(), never this module directly.

Requires OPENAI_API_KEY to be set (see .env.example). Without it,
is_configured() returns False and the engine falls back to the rule-based
FLAG default, same as with any unconfigured provider.
"""

import json
import urllib.error
import urllib.request

from threshia.config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL
from threshia.providers.base import ProviderError, build_prompt, validate_provider_response

__all__ = ["ProviderError", "is_configured", "call_openai"]


def is_configured() -> bool:
    """True if OPENAI_API_KEY is set."""
    return bool(OPENAI_API_KEY)


def call_openai(
    tool_name: str,
    parameters: dict,
    retrieved_policy_texts: list[str],
    timeout: int = 20,
) -> dict:
    """
    Calls the OpenAI API and returns a dict like:
        {"decision": "FLAG", "reasoning": "..."}

    Raises ProviderError for any failure mode (missing key, network error,
    malformed response) — callers should catch this and fail safe to FLAG.
    """
    if not OPENAI_API_KEY:
        raise ProviderError("OPENAI_API_KEY is not set (see .env.example).")

    prompt = build_prompt(tool_name, parameters, retrieved_policy_texts)

    payload = json.dumps(
        {
            "model": OPENAI_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        f"{OPENAI_BASE_URL}/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_API_KEY}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise ProviderError(f"Could not reach OpenAI API: {e}")
    except json.JSONDecodeError as e:
        raise ProviderError(f"OpenAI API returned non-JSON response: {e}")

    try:
        content = body["choices"][0]["message"]["content"]
        parsed = json.loads(content)
    except (KeyError, IndexError, TypeError) as e:
        raise ProviderError(f"Unexpected OpenAI response structure: {e}")
    except json.JSONDecodeError as e:
        raise ProviderError(f"OpenAI message content was not valid JSON: {e}")

    return validate_provider_response(parsed, "OpenAI")
