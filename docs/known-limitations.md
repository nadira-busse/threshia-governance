# Known Limitations

This document lists unresolved limitations in the current implementation. Deliberate architecture boundaries are documented in [Current Scope](mvp-scope.md) instead.

## Policy coverage is limited

The shipped policies cover a small set of synthetic finance, HR, and ITSM examples.

Tools that are not explicitly covered cannot receive `ALLOW`. They follow the uncovered-tool path and return `FLAG`.

This keeps unknown actions from being authorized, but it also means the shipped policies represent only a small part of the situations a larger governance system might need to handle.

## Semantic retrieval has no relevance threshold

For an uncovered tool, ChromaDB returns the nearest policy documents without applying a minimum similarity or distance threshold.

Retrieval was tested against a larger synthetic policy corpus so that top-k selection could be evaluated beyond the small shipped policy set. The expected policy remained in the retrieved results for the related and deliberately confusable cases that were tested.

Irrelevant queries still returned plausible nearest neighbors, and the distance ranges for relevant and irrelevant results overlapped. Because of that overlap, the current evidence does not support a reliable fixed threshold.

This does not create an authorization risk under the current decision model: provider output is advisory and an uncovered tool still returns `FLAG`. Poor retrieval can, however, make the review context less useful.

The current evaluation also does not establish retrieval behavior for much larger policy corpora or different embedding models.

## Live-provider behavior is not verified in CI

Mistral and OpenAI request and response handling is tested with mocked API responses in the automated suite. Manual scripts are available for live integration checks, but real provider calls are not run on every push or pull request.

Both provider integrations have also been checked manually against the live APIs. Provider reasoning can vary between calls, so these checks are integration evidence rather than deterministic test evidence.

## First semantic use may require a network download

On a fresh environment, ChromaDB's default embedding model may need to be downloaded before semantic indexing can complete. If the model cannot be downloaded or initialized, uncovered tools fall back to `FLAG`.

Directly covered deterministic calls do not depend on this download.

## Audit log has no rotation or size management

`audit.jsonl` is append-only and currently has no built-in rotation, archival policy, or size limit.

Tool parameter values are excluded by default, but retained audit records still accumulate until the operator manages the file externally.

## Packaging verification is manual

A clean wheel install has been manually checked to confirm that packaged policy documents are included and can be loaded outside the source tree. This packaging check is not currently part of GitHub Actions.

A packaging change could therefore break installed policy availability without being detected by the current CI workflow.
