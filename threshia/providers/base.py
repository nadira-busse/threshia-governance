"""
Provider abstraction.

Threshia's optional LLM layer can use more than one backend. Every provider
module exposes the same two functions:

    is_configured() -> bool
        True if this provider has what it needs (an API key) to run.

    evaluate(tool_name, parameters, retrieved_policy_texts, timeout=20) -> dict
        Returns {"decision": "ALLOW"|"BLOCK"|"FLAG", "reasoning": str}.
        Raises ProviderError on any failure.

threshia/engine/evaluator.py only ever calls get_provider(name) — it never
imports a specific provider module. Adding a third provider means writing
one new module with these two functions and registering it in _PROVIDERS
below; the engine doesn't change.

build_prompt() and validate_provider_response() are shared here because
the prompt and the response contract don't depend on which model answers
it — only each provider's specific request/response shape differs. Both
Mistral and OpenAI happen to use an OpenAI-compatible chat-completions
format in this codebase, but that's a detail of those two providers, not
a guarantee this abstraction depends on.
"""

import json
from collections.abc import Callable

VALID_DECISIONS = {"ALLOW", "BLOCK", "FLAG"}

PROMPT_TEMPLATE = """You are a runtime governance evaluator for AI agent tool calls.
You will be given a proposed tool call and the text of the most relevant
governance policies found for it. No policy explicitly lists this exact
tool, so you must reason from the policy content whether the tool call
fits a pattern the policies already describe.

Respond with ONLY a JSON object in this exact format, nothing else:
{{"decision": "ALLOW|BLOCK|FLAG", "reasoning": "one or two sentence explanation"}}

Proposed tool call:
Tool name: {tool_name}
Parameters: {parameters}

Most relevant policy content found:
{policy_context}

If the tool call resembles a never-permitted or high-risk pattern in the
policy content, choose BLOCK. If it resembles an allowed pattern with no
gating condition, choose ALLOW. If you are not confident, choose FLAG —
defaulting to human review is always safer than a wrong ALLOW.

Respond with only the JSON object.
"""


class ProviderError(Exception):
    """Raised when a provider is unreachable or returns unusable output."""


def build_policy_context(retrieved_policy_texts: list[str]) -> str:
    if not retrieved_policy_texts:
        return "(no policy content retrieved)"
    return "\n\n---\n\n".join(retrieved_policy_texts)


def build_prompt(tool_name: str, parameters: dict, retrieved_policy_texts: list[str]) -> str:
    """Shared prompt every provider sends — see module docstring for why."""
    return PROMPT_TEMPLATE.format(
        tool_name=tool_name,
        parameters=json.dumps(parameters),
        policy_context=build_policy_context(retrieved_policy_texts),
    )


def validate_provider_response(parsed: dict, provider_name: str) -> dict:
    """
    Shared contract check so every provider is held to the same rules,
    regardless of which model or API answered.
    """
    if "decision" not in parsed or "reasoning" not in parsed:
        raise ProviderError(f"{provider_name} response missing required fields: {parsed!r}")
    if parsed["decision"] not in VALID_DECISIONS:
        raise ProviderError(f"{provider_name} returned invalid decision: {parsed['decision']!r}")
    return parsed


def _load_mistral() -> tuple[Callable[[], bool], Callable]:
    from threshia.providers import mistral_provider

    return mistral_provider.is_configured, mistral_provider.call_mistral


def _load_openai() -> tuple[Callable[[], bool], Callable]:
    from threshia.providers import openai_provider

    return openai_provider.is_configured, openai_provider.call_openai


# Registry: provider name (from THRESHIA_PROVIDER) -> loader function.
# Loaders import lazily so choosing "mistral" never has to import the
# openai_provider module (and vice versa).
_PROVIDERS: dict[str, Callable[[], tuple]] = {
    "mistral": _load_mistral,
    "openai": _load_openai,
}


def get_provider(name: str) -> tuple[Callable[[], bool], Callable]:
    """
    Look up a provider by name (the THRESHIA_PROVIDER config value).

    Returns (is_configured, evaluate) for that provider.
    Raises ProviderError if the name isn't registered.
    """
    loader = _PROVIDERS.get(name)
    if loader is None:
        raise ProviderError(
            f"Unknown provider '{name}'. Supported providers: {sorted(_PROVIDERS)}."
        )
    return loader()
