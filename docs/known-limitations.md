# Known Limitations

This document describes the current boundaries of Threshia.

## Policy coverage

Three policy documents exist, covering three of Kelvior's five agents.
A tool call outside those three domains (ERP, HR, ITSM) is either handled
by the optional semantic layer, if configured, or defaults to `FLAG`. This
is a coverage gap, not an engine defect — the fail-safe default is working
as designed in that case.

## Never-permitted parsing depends on a Markdown convention

`rules/never_permitted.py` extracts blocked action names by looking for a
line containing restriction language ("never permitted," "not permitted,"
"must not be performed"), followed by a bullet list of backtick-quoted
names. `scripts/validate_policies.py` (also run in CI) checks every policy
document for restriction-sounding language that didn't produce any parsed
actions, and fails the check if it finds one — this catches the common
case of a policy author describing a restriction in a way the parser
doesn't recognize, though it can't catch every possible phrasing.
`tests/test_never_permitted.py` covers the current three policy documents,
several edge cases (a wrapped intro sentence, a second unrelated list
later in the same document), and the validation check itself.

## The automated tests for both LLM providers use mocked API responses

`tests/test_mistral_provider.py` and `tests/test_openai_provider.py` mock
the HTTP call to their respective APIs, so request/response handling,
JSON parsing, and error paths are covered by CI without requiring real API
keys or incurring API costs on every push. `scripts/verify_mistral_live.py`
and `scripts/verify_openai_live.py` each call their real API for a manual
integration check — deliberately kept outside the automated test suite so CI
stays free and offline-runnable.

Both provider paths have been manually verified against their real APIs
using an uncovered tool call (`Sales.CreateDiscountOffer`). In each check,
retrieval supplied policy context and the configured provider returned a
valid `BLOCK` verdict.

The exact reasoning differed between providers and between runs. That is
expected for probabilistic model output and is why these checks confirm
integration behavior, not deterministic verdict equivalence.

This confirms the retrieval-plus-LLM path works end to end for both
providers, but each is a manual check, not a repeated or automated one —
a different tool call or a future model update on either side could
produce a different verdict.

## ChromaDB's embedding model requires a one-time network download

The first call to `vector_store.build_index()` on a fresh machine
downloads ChromaDB's default embedding model (~90MB) from Hugging Face.
Without internet access at that moment, this call fails; the engine's
fallback behavior (skip the semantic layer, default to `FLAG`) only
applies to a missing API key or missing ChromaDB installation, not to a
failed download partway through setup. `tests/test_vector_store.py`
skips its tests (rather than failing them) when this download fails for a
network-related reason.

## No live agent integration

Every tool call evaluated in this repository, in tests and in the example
script, is a `ToolCall` object constructed directly in Python. Threshia has
not been connected to an actual running agent that generates tool-call
attempts on its own.

## Audit log has no rotation or size management

`audit.jsonl` grows without bound as `evaluate_and_log()` is called. There
is no log rotation, archiving, or size limit in this version.

## Packaging verification is manual, not automated in CI

A clean wheel install was manually verified by building the package with
`python -m build`, installing it in a separate virtual environment, and
importing it from outside the repository. `load_all_policies()` returned
all three packaged policy IDs, confirming that the policy documents ship
with the wheel and can be loaded without relying on the source tree.

This verification is not currently automated in CI, so a future change to
`pyproject.toml` or the policy directory structure could break packaging
without the CI pipeline detecting it.