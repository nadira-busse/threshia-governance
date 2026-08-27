# Architecture Overview

Threshia separates governance decisions from external tool execution. The evaluator decides whether a proposed tool call is allowed, blocked, or requires review. `governed_execute()` can then enforce that decision before a caller-supplied executor is invoked.

## Components

```text
threshia/
├── models/       ToolCall, Policy, PolicyMatch, Verdict
├── policies/     policy loading, validation, semantic index, policy documents
├── rules/        structured never-permitted lookup
├── engine/       policy evaluation and verdict creation
├── providers/    shared LLM-provider interface, Mistral and OpenAI adapters
├── audit/        explicit JSONL audit serialization and persistence
├── execution/    governed execution boundary and ExecutionResult
└── config.py     environment and runtime-path configuration
```

The main responsibilities are deliberately separate:

- **policies** owns validated policy data and derived retrieval state;
- **rules** builds deterministic lookups from structured policy fields;
- **engine** owns governance decisions;
- **providers** owns external LLM integration;
- **audit** owns persisted decision records;
- **execution** enforces whether the supplied executor may run, but does not own the external tool itself.

## Request flow

```text
ToolCall
   ↓
never_permitted lookup
   │
   ├─ match ───────────────────────→ BLOCK
   │
   ↓
tool explicitly covered by a policy?
(applicable_tools)
   │
   ├─ yes → approval required?
   │          │
   │          ├─ no ───────────────→ ALLOW
   │          │
   │          ├─ yes + literal True → ALLOW
   │          │
   │          └─ otherwise ─────────→ FLAG
   │
   └─ no → semantic review path
              │
              ├─ provider + retrieval succeed
              │      ↓
              │   advisory analysis
              │      ↓
              │     FLAG
              │
              ├─ semantic path unavailable
              │      ↓
              │   rule-based FLAG
              │
              └─ retrieval/provider failure
                     ↓
                 fallback FLAG
```

Only explicit deterministic policy coverage may produce `ALLOW`.

A `Verdict` may then be used in one of two ways:

```text
evaluate() / evaluate_and_log()
    └─ returns decision; caller still owns enforcement

governed_execute()
    ├─ ALLOW -> supplied executor exactly once -> EXECUTED
    ├─ BLOCK -> no execution -> DENIED
    └─ FLAG  -> no execution -> REVIEW_REQUIRED
```

## Policy representation

Each policy is a Markdown document with validated YAML frontmatter.

Threshia uses these structured policy fields for deterministic evaluation:

- `applicable_tools` — tools directly governed by the policy;
- `gated_tools` — governed tools that require approval evidence;
- `never_permitted` — action names that must return `BLOCK`.

`never_permitted` is loaded into the typed `Policy` model and combined into the deterministic hard-block lookup. The loader rejects malformed structured values before evaluation can run.

The Markdown body has a different responsibility: human-readable explanation and semantic retrieval context. Heading spelling, bullet formatting, backticks, prose order, and other presentation changes cannot alter the deterministic hard-block set.

## Decision precedence

Evaluation is ordered intentionally:

1. `never_permitted` hard block;
2. exact policy coverage;
3. approval gating;
4. deterministic `ALLOW` for covered, permitted calls;
5. advisory semantic handling for uncovered calls.

The first rule is strongest. Approval evidence cannot override a never-permitted action.

## Approval trust boundary

For gated tools, Threshia accepts approval evidence only when `ToolCall.parameters["human_approval_evidenced"]` is the literal boolean `True`.

That check validates the control value, not its provenance. Threshia does not independently establish who approved the action, when approval occurred, whether evidence was replayed, or whether it is cryptographically bound to the specific call. The integrating system owns that trust boundary.

Stronger provenance is deliberately not implemented while no independent approval authority exists. Signing an approval claim inside the same trust boundary that created it would not establish independent authenticity.

## Semantic advisory boundary

Semantic evaluation exists only for tools that no policy explicitly covers.

The path can:

- retrieve related policy context from ChromaDB;
- pass minimized context to the configured provider;
- retain provider reasoning and the provider's suggested decision for review.

The semantic path cannot authorize or block an uncovered tool. Provider `ALLOW`, `BLOCK`, and `FLAG` suggestions all produce authoritative Threshia `FLAG` for an uncovered tool. The provider suggestion is stored separately as advisory metadata.

This invariant is enforced in code after provider output is parsed, so it does not depend on prompt wording or model behavior.

External-provider disclosure is separately constrained. By default, semantic provider requests contain the tool name and retrieved policy context but no `ToolCall.parameters` key names or values. `SemanticConfig.parameter_allowlist` can explicitly permit selected parameter values to cross that network boundary. The integrating caller owns that choice.

`SemanticConfig` is independent from `AuditConfig`: one controls network disclosure to an external provider, while the other controls local persistence. A value may be permitted at one boundary and denied at the other.

If index construction, embedding initialization, retrieval, or provider evaluation fails, the engine also returns `FLAG`, with fallback metadata describing the failure.

## Provider abstraction

`threshia/providers/base.py` defines the shared provider contract and provider registry. The evaluator selects a provider through that abstraction rather than importing Mistral or OpenAI directly.

Both provider adapters share the same prompt-building and response-validation path. Switching providers is configuration, not evaluator logic.

## Derived semantic state

The Chroma collection is derived from the current policies.

Its metadata stores a deterministic fingerprint over policy identity, structured rule fields, and policy content. The collection is reused only when both the fingerprint and document count match the currently loaded policy set; otherwise it is rebuilt.

The index is not a source of policy rules. It can be rebuilt from the current policies and is used only for semantic retrieval.

The shipped runtime corpus is intentionally small, so retrieval selectivity is also exercised with a larger synthetic test corpus. In those tests, the expected policy remained within the retrieved top-k for the related and deliberately confusable cases. Irrelevant queries still returned plausible nearest neighbors and distance ranges overlapped. For that reason, no fixed relevance threshold is currently used.

## Audit boundary

`evaluate()` does not write the audit log. On the semantic path it may still update derived Chroma state and call an external LLM provider, so it should not be described as generally pure or side-effect free.

`evaluate_and_log()` evaluates and then persists one audit record.

Audit serialization is explicit rather than a recursive dump of the full `Verdict` object. `ToolCall.parameters` values are excluded by default. A caller may opt selected keys into persistence with `AuditConfig.parameter_allowlist`.

`human_approval_evidenced` is recorded separately as a Threshia-known control state. A logged value of `True` means Threshia received literal `True`; it does not prove authentic human approval.

## Enforcement boundary

A returned `Verdict` is a decision, not enforcement. Direct users of `evaluate()` or `evaluate_and_log()` can still ignore it.

`governed_execute()` provides the enforcement path. It owns only whether the supplied executor may be invoked:

| Verdict | Execution status | Executor behavior |
|---|---|---|
| `ALLOW` | `EXECUTED` | called exactly once |
| `BLOCK` | `DENIED` | never called |
| `FLAG` | `REVIEW_REQUIRED` | never called |

`Verdict` and `ExecutionResult` remain separate because they answer different questions: what governance decided versus what happened at the enforcement boundary.

Threshia does not own the executor implementation, credentials, tool registry, retries, timeouts, queues, or human-review workflow. Executor exceptions propagate as execution failures and are not rewritten into governance verdicts.

Audit logging through `governed_execute()` is optional and uses the same `AuditConfig`/`log_verdict()` path as `evaluate_and_log()`. The audit record is written before an allowed executor is invoked. An `ALLOW` audit entry therefore records authorization; it does not prove that the executor was invoked or that execution succeeded.

## Policy domains

The current repository contains three synthetic policy documents:

| Policy | Domain | Coverage example |
|---|---|---|
| `erp-controlled-actions-001.md` | Finance | ERP reads, gated payment-review actions, and never-permitted payment mutations |
| `hr-restricted-data-001.md` | HR | gated restricted-data access and never-permitted sensitive HR actions |
| `itsm-readonly-001.md` | ITSM | read/recommendation-only ticket operations |
