# Current Scope

This document defines what Threshia currently owns and what remains outside the system.

## In scope

Threshia currently provides:

- validated policy documents with structured YAML rules and explanatory Markdown;
- deterministic checks for blocked actions, explicit policy coverage, and approval requirements;
- `ALLOW`, `BLOCK`, and `FLAG` governance decisions;
- semantic retrieval and LLM analysis for uncovered tools, without sending tool parameters to the provider by default;
- interchangeable Mistral and OpenAI integrations behind one provider interface;
- a local ChromaDB index that is rebuilt when the loaded policies change;
- optional JSONL audit logging that excludes tool parameter values by default;
- separate configuration for what may be sent to an external provider and what may be stored in the audit log;
- `governed_execute()`, which only invokes the supplied executor when the decision is `ALLOW`;
- synthetic example policies for finance, HR, and IT service management (ITSM).

Only explicitly covered policy rules can produce `ALLOW`. An uncovered tool remains `FLAG` even when an LLM provider suggests otherwise.

## Outside the current boundary

- **External tool implementation** — Threshia does not register tools, own their credentials, create downstream API clients, or decide how an external operation is implemented. The integrating system supplies the executor.

- **Human-review workflow** — `FLAG` maps to `REVIEW_REQUIRED` when using `governed_execute()`, but Threshia does not provide a review queue, UI, notification flow, or approval service.

- **Independent approval provenance** — Threshia checks whether `human_approval_evidenced` is the literal boolean `True`. It does not independently verify who approved the action or authenticate where that evidence came from.

- **Live agent runtime integration** — The tests and example create `ToolCall` objects directly in Python. Threshia is not currently connected to an agent framework that automatically sends proposed tool calls through the engine.

- **Execution orchestration** — `governed_execute()` invokes the supplied synchronous executor once for `ALLOW` and not at all for `BLOCK` or `FLAG`. It does not provide retries, timeouts, queues, job persistence, compensation, or asynchronous orchestration.

- **Automatic policy reload** — Policies are loaded by the calling process. Changes to policy files are not automatically applied to `Policy` objects that are already in memory. When policies are loaded again, the semantic index is rebuilt if it no longer matches the current policy set.

- **Automated live-provider verification** — CI tests provider behavior with mocked API responses. Live Mistral and OpenAI checks are manual and require local credentials.

- **General-purpose CLI or service API** — The repository provides Python APIs and an example script, but no general command-line interface or hosted service endpoint.
