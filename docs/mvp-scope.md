# MVP Scope

## What this version supports

- Loading policy documents (Markdown + YAML frontmatter) from
  `threshia/policies/documents/`, with validation of required fields and
  clear errors for malformed files.
- Evaluating a single `ToolCall` against the loaded policy set through a
  fixed rule order: never-permitted check, policy match, approval gating.
- Distinguishing three verdict sources (`rule`, `llm`, `fallback`) so a
  reviewer of the audit log can tell how each decision was reached.
- An optional semantic layer (ChromaDB retrieval + an LLM provider) for
  tool calls no policy explicitly covers, which is skipped entirely — not
  attempted and not required — when ChromaDB isn't installed or no
  provider is configured.
- Two interchangeable LLM providers (Mistral, OpenAI) behind one shared
  interface (`threshia/providers/base.py`). Switching is a config change
  (`THRESHIA_PROVIDER`), not a code change.
- Optional append-only audit logging through `evaluate_and_log()`, which
  writes each returned verdict to `audit.jsonl`. The lower-level
  `evaluate()` function remains side-effect free.
- Three policy documents, each derived from a real Kelvior agent
  definition (Finance Invoice Assistant, HR Onboarding Helper, IT Ticket
  Triage).

## What is not in this version

- **Only three of Kelvior's five agents have a corresponding policy.**
  The Sales Proposal Agent and Learning Policy Coach aren't covered. A tool
  call from either would currently fall to the fail-safe FLAG default (or
  the optional semantic layer, if configured), not a dedicated policy.
- **No integration with a live, running agent.** Every `ToolCall` in the
  test suite and the example script is constructed directly in Python.
  Threshia has not been wired into an actual agent runtime that calls
  `evaluate()` on its own tool-call attempts.
- **The Mistral and OpenAI providers are tested with mocked API responses**
  (`tests/test_mistral_provider.py`, `tests/test_openai_provider.py`), not
  against the real APIs in automated CI. Both paths have been manually
  verified against their real APIs (see `docs/known-limitations.md`),
  but neither is checked this way repeatedly or automatically.
- **No CLI beyond the single example script.** There's no argument-parsing
  entry point for evaluating an arbitrary tool call from the command line.
- **No mechanism to reload or hot-swap policies at runtime.** Policies are
  loaded once per process; changing a policy document requires restarting
  whatever process called `load_all_policies()`.

## Possible future directions

These are directions that would make sense given the current architecture,
not commitments:

- Policies for the two remaining Kelvior agents, extending the same
  Markdown-plus-frontmatter format.
- A small CLI (`threshia evaluate --tool ... --params ...`) as a more direct
  entry point than editing the example script.
- Wiring `evaluate_and_log()` into an actual agent framework's tool-call
  hook, to validate the design against a real runtime rather than
  hand-constructed `ToolCall` objects.
