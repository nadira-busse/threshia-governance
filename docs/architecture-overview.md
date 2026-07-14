# Architecture Overview

## Components

```
threshia/
├── models/       ToolCall, Policy, PolicyMatch, Verdict — plain dataclasses
├── policies/      loader.py, vector_store.py, and documents/ (the 3 policy .md files)
├── rules/         never_permitted.py — parses block lists out of policy content
├── engine/        evaluator.py — the evaluate() decision function
├── providers/     base.py (shared interface + registry), mistral_provider.py, openai_provider.py
├── audit/         logger.py — JSONL audit trail
└── config.py      env loading, path resolution
```

Each package has one responsibility. `models` defines the data shapes.
`policies` loads and (optionally) indexes policy content. `rules` extracts
structured rules from that content. `engine` is the only place that combines
them into a decision. `providers` is the only place that talks to an
external API. `audit` is the only place that writes to disk for logging
purposes.

## Request flow

```
ToolCall
   │
   ▼
never-permitted check (rules/never_permitted.py)
   │  match → BLOCK, decision_source="rule"
   ▼  no match
policy match (does any Policy.applicable_tools contain this tool?)
   │
   ├─ no match ──► optional semantic evaluation (policies/vector_store.py +
   │               providers/mistral_provider.py) ──► LLM verdict, or FLAG
   │               if the LLM layer isn't configured or fails
   │
   └─ match(es) ──► gating check (is this tool in any matched Policy's
                     gated_tools, and if so, is human_approval_evidenced
                     present in ToolCall.parameters?)
                        │  not evidenced → FLAG
                        ▼  evidenced or not gated
                     ALLOW
   │
   ▼
Verdict (returned from evaluate(); audit/logger.py appends it to
audit.jsonl when evaluate_and_log() is used instead of evaluate())
```

## Design decisions

### Three verdicts, not four

Kelvior Agent Decision Gate — the companion project this repository was
built alongside — produces four verdicts (`GO`, `CONDITIONAL GO`,
`REMEDIATE`, `BLOCK`) because it answers a one-time readiness question with
room for "acceptable with conditions." Threshia answers a different kind of
question, repeatedly, for every tool call an agent makes at runtime. A
runtime gate that returns "conditionally allowed" doesn't resolve anything —
the agent still has to either proceed or not. Threshia uses `ALLOW`, `BLOCK`,
`FLAG` (a case a human should look at) instead.

### Policy content is the single source of truth for what's blocked

Each policy document lists actions that are never permitted, as a plain
Markdown bullet list under a heading containing "never permitted." Rather
than keeping a separate Python list of the same action names,
`rules/never_permitted.py` parses that list directly out of the policy's
`content` field. Updating a policy document is the only step needed to
change what the rule engine blocks — there's no second place to remember to
update, and no way for the documentation and the enforced behavior to
silently drift apart.

The trade-off is that this parsing depends on a consistent Markdown
convention (a heading containing "never permitted," followed by a bullet
list of backtick-quoted action names). `tests/test_never_permitted.py`
covers this against both synthetic fixtures and the real policy documents,
including a case where the intro sentence wraps onto a second line before
the bullet list starts.

### Approval gating lives in the policy, not the tool call

`Policy.gated_tools` marks which of a policy's `applicable_tools` require
evidenced human approval before `ALLOW`. A `ToolCall` carries that evidence
as `parameters["human_approval_evidenced"]`. This keeps the *rule* (which
tools are gated) attached to the policy document where a reviewer would
look for it, and keeps the *evidence* (was this specific call actually
approved) attached to the specific call being evaluated. A never-permitted
match is checked first and overrides gating entirely — approval evidence
cannot authorize an action that's blocked outright
(`tests/test_engine.py::test_block_overrides_even_with_approval_evidence`).

### The optional LLM layer degrades instead of failing

A tool call that no policy's `applicable_tools` covers doesn't automatically
get an LLM's opinion. `engine/evaluator.py` first checks whether ChromaDB is
installed and whether the configured provider (`THRESHIA_PROVIDER`) has its
API key set. If any of those isn't true, or if retrieval finds nothing
relevant, the engine falls back to the same `FLAG` default it would use
without this layer at all — the behavior is identical to not having this
layer at all. Only when a semantic match *is* found but the provider call
itself fails does the engine report `decision_source="fallback"`, a
distinct category from `"rule"` and `"llm"` so an audit log can tell "never
attempted" apart from "attempted and failed" after the fact.

### Providers are swapped through one abstraction, not through the engine

`threshia/providers/base.py` defines the interface every provider
implements — `is_configured()` and an `evaluate(tool_name, parameters,
retrieved_policy_texts)` function returning `{"decision": ..., "reasoning":
...}` — and a small registry (`get_provider(name)`) that looks one up by
the `THRESHIA_PROVIDER` config value. `engine/evaluator.py` only ever calls
`get_provider()`; it never imports `mistral_provider` or `openai_provider`
directly. Both providers share the same prompt-building and
response-validation logic in `base.py`, so adding a third provider means
writing one new module with those two functions and registering it — the
engine, the prompt, and the response contract don't change.

This mirrors the model-agnostic design used elsewhere in this candidate's
portfolio (Weft is built the same way, so no single AI vendor is a hard
dependency): Mistral is the default for EU-sovereignty reasons, but
switching to OpenAI is a config change (`THRESHIA_PROVIDER=openai` plus
`OPENAI_API_KEY`), not a code change.
`tests/test_provider_switching.py::test_engine_uses_openai_when_configured_as_provider`
proves this by mocking OpenAI's `call_openai()` and confirming the engine
actually calls it — not just that it labels the verdict "openai."

### `evaluate()` stays pure; logging is a separate wrapper

`evaluate()` takes a `ToolCall` and a list of `Policy` objects and returns a
`Verdict`, with no side effects. `evaluate_and_log()` calls `evaluate()` and
then appends the result to `audit.jsonl`. Tests call `evaluate()` directly,
so running the test suite never writes to the real audit log.

## Where Kelvior's evidence became Threshia's policies

Kelvior's agent definitions (YAML files, not part of this repository)
specify `mcp_tools`, `allowed_actions`, and `restricted_actions` per agent.
The three policy documents in `threshia/policies/documents/` translate that
evidence into the shape Threshia's engine needs:

| Policy | Source agent | What it governs |
|---|---|---|
| `erp-controlled-actions-001.md` | Finance Invoice Assistant | Read-only ERP lookups (unconditional ALLOW) vs. controlled actions like payment-review triggers (gated) vs. actions like `release_payment` (never permitted) |
| `hr-restricted-data-001.md` | HR Onboarding Helper | Restricted employee data lookups (gated on approval evidence) vs. actions like `access_medical_or_absence_records` (never permitted) |
| `itsm-readonly-001.md` | IT Ticket Triage | Read/recommendation-only ITSM tools (unconditional ALLOW), with no gating at all — the cleanest ALLOW case in the set |
