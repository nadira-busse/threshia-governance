# Threshia — Runtime Governance Engine

![Tests](https://github.com/nadira-busse/threshia-governance/actions/workflows/tests.yml/badge.svg)

Threshia checks proposed AI-agent tool calls against explicit policies before an external tool is allowed to run.

I built it around a simple problem: an agent may be allowed to operate, but that does not mean every action it proposes should be treated the same way. Some actions can proceed, some need approval, some must be blocked, and unfamiliar actions should be reviewed instead of guessed into permission.

Threshia returns one of three decisions:

- `ALLOW` — a policy explicitly allows the call;
- `BLOCK` — a policy explicitly prohibits the action;
- `FLAG` — the call needs review or cannot be authorized from the current policies.

## How it works

For each `ToolCall`, Threshia follows a fixed order:

1. **Blocked actions** — rules marked as `never_permitted` are checked first. A match always returns `BLOCK`.
2. **Known tools** — if a policy explicitly covers the tool, Threshia evaluates it using deterministic rules.
3. **Approval checks** — gated tools require `human_approval_evidenced=True`.
4. **Unknown tools** — if no policy covers the tool, Threshia can retrieve related policy context and use Mistral or OpenAI to help explain what may be relevant.

The semantic path is only used for review context. It cannot authorize an unknown tool. An uncovered tool always returns `FLAG`.

Known tools do not need ChromaDB, an LLM provider, or network access.

## Using Threshia

Threshia provides three main entry points:

- `evaluate()` returns a governance decision.
- `evaluate_and_log()` also writes that decision to the local audit log.
- `governed_execute()` enforces the decision before calling the supplied executor.

Execution follows a simple rule:

| Decision | Result |
|---|---|
| `ALLOW` | the executor may run |
| `BLOCK` | execution is denied |
| `FLAG` | execution stops and review is required |

Threshia does not own the external tools, their credentials, or the human-review workflow.

## Policies

The repository includes example policies for:

- finance invoice operations;
- HR restricted-data lookups;
- IT ticket triage.

The rules Threshia enforces are stored in validated YAML frontmatter. The Markdown below them explains the policy and can also provide context during semantic review.

## Run locally

Create and activate a virtual environment:

    python -m venv venv

Windows (PowerShell):

    venv\Scripts\activate

If PowerShell refuses with "running scripts is disabled on this system", that's the default execution policy blocking the activation script, not a Threshia or Python problem. Allow it for the current session and try again:

    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

macOS/Linux:

    source venv/bin/activate

Install the project:

    pip install -e ".[dev]"

Run the tests:

    python -m pytest tests/ -v

Run the example:

    python examples/evaluate_tool_calls.py

No API key is required for the deterministic path or the automated tests. Without a configured semantic provider, uncovered tools are flagged for review.

## Semantic review

For uncovered tools, Threshia can use a local ChromaDB index to find related policy context and send that context to either Mistral or OpenAI.

By default, tool parameter names and values are not sent to the provider. Selected values can be explicitly allowed when an integration needs them.

The provider's response is advisory. It cannot turn an uncovered tool into `ALLOW`.

Semantic retrieval is also tested against a larger synthetic policy corpus so that retrieval is exercised beyond the small set of shipped example policies. See [Known Limitations](docs/known-limitations.md) for the current retrieval boundaries.

## Architecture and scope

- [Architecture overview](docs/architecture-overview.md) — request flow, responsibilities, state, and trust boundaries.
- [Current scope](docs/mvp-scope.md) — what Threshia owns and what remains outside the system.
- [Known limitations](docs/known-limitations.md) — current technical and verification limitations.
- [Security](SECURITY.md) — security assumptions and vulnerability reporting.

## Verification

The test suite covers the main decision paths, policy validation, semantic review behavior, retrieval, audit handling, and governed execution.

GitHub Actions runs the test suite and static checks on supported Python versions. External provider calls are mocked in CI.

Manual scripts are available for live provider checks:

    python scripts/verify_mistral_live.py

For OpenAI, first set the provider in your `.env` file:

    THRESHIA_PROVIDER=openai

Then run:

    python scripts/verify_openai_live.py

To switch back, set `THRESHIA_PROVIDER=mistral` (or remove the line — `mistral` is the default). Each live-check script also checks that `THRESHIA_PROVIDER` actually matches the provider it's testing, so a leftover setting from a previous check is reported rather than silently used.

Live checks require the relevant API credentials and are separate from automated test evidence.

## Author

**Nadira Büsse**

## License

[MIT](LICENSE)
