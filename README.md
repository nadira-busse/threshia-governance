# Threshia — Runtime Governance Engine

![Tests](https://github.com/nadira-busse/threshia-governance/actions/workflows/tests.yml/badge.svg)

Threshia evaluates individual AI-agent tool calls while an agent is running,
and returns one of three verdicts: `ALLOW`, `BLOCK`, or `FLAG`.

I built Threshia after working on Kelvior Agent Decision Gate, a reasoning
agent that decides whether an AI agent is ready to be deployed at all. That
project answers one question well — *should this agent go live?* — but it
doesn't answer a different one: once an agent is live, is every action it
takes actually allowed? Those are two separate gates. Kelvior checks
readiness before deployment. Threshia checks individual actions during
execution. This repository is the second gate.

## What it does

Threshia takes a proposed tool call — a tool name and its parameters — and
checks it against a set of governance policies. The evaluation runs in a
fixed order:

1. **Never-permitted check.** Some actions are blocked outright, regardless
   of context (releasing a payment, modifying an employee record). This
   check runs first and cannot be overridden by anything downstream.
2. **Policy match.** Does any loaded policy govern this tool?
3. **Approval gating.** If the matching policy requires evidenced human
   approval for this specific tool, the call is only allowed once that
   evidence is present.
4. **Optional semantic fallback.** If no policy explicitly covers the tool,
   Threshia can retrieve the most related policy text (ChromaDB) and ask a
   configured LLM provider to reason about it, instead of defaulting
   straight to `FLAG`. Mistral and OpenAI are both supported behind one
   provider interface — switching is a config change (`THRESHIA_PROVIDER`),
   not a code change. This step is optional — see below.

`evaluate_and_log()` appends each result to the JSONL audit log.
`evaluate()` returns the same verdict without writing to disk, which keeps
tests and standalone evaluation side-effect free.

## Why the policies are Kelvior policies

The three policy documents in this repository aren't generic examples. They
are written directly from three of Kelvior's real agent definitions — the
Finance Invoice Assistant, the HR Onboarding Helper, and IT Ticket Triage —
using their actual MCP tool names, allowed actions, and restricted actions.
Kelvior's agent definitions already describe what each agent is and isn't
permitted to do; Threshia's policies formalize that into something a rule
engine can check per tool call, tool by tool.

Kelvior Systems is a fictional enterprise simulation environment. All
business data, employees, systems, and processes referenced in the policy
documents are synthetic.

## Try it

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

pip install -e ".[dev]"
python -m pytest tests/ -v
python examples/evaluate_kelvior_tool_calls.py
```

The example script evaluates five tool calls that each take a different
path through the engine — a plain read, a gated action with and without
approval evidence, a never-permitted action, and a tool no policy covers —
and prints the resulting verdict and reasoning for each.

No API key or account is required for any of this. The optional LLM layer
(see below) needs a Mistral or OpenAI API key only if you want to
exercise it.

## Architecture and design decisions

Component responsibilities, the evaluation order, and the reasoning behind
specific choices (why three verdicts and not four, why policies are parsed
from Markdown instead of duplicated in Python, why the LLM layer degrades
instead of failing) are in
[docs/architecture-overview.md](docs/architecture-overview.md).

## Current scope

What this version supports, and what it deliberately doesn't yet, is in
[docs/mvp-scope.md](docs/mvp-scope.md) and
[docs/known-limitations.md](docs/known-limitations.md).

## Tests

77 tests across policy loading, rule evaluation, never-permitted-action
parsing, both LLM providers, the provider registry, provider switching,
ChromaDB retrieval, and audit logging. Run them with
`python -m pytest tests/ -v`. CI runs the same suite on every push, plus
`ruff`, `mypy`, and a policy-document validation script
(`.github/workflows/tests.yml`).

## Verifying the live LLM layer

The automated tests mock both providers' API calls, so CI stays free and
offline-runnable. To confirm a real integration works end to end, add
the relevant API key to a local `.env` file and run:

```bash
python scripts/verify_mistral_live.py
python scripts/verify_openai_live.py   # set THRESHIA_PROVIDER=openai first
```

Each evaluates a tool call none of the three policies cover, so it
exercises ChromaDB retrieval plus a real API call. Both provider paths
have been manually verified against their real APIs — see
`docs/known-limitations.md` for details.

## Author

**Nadira Büsse**

[LinkedIn](https://www.linkedin.com/in/nadirabusse)

## License

[MIT](LICENSE).
