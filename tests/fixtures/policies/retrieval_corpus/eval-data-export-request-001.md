---
id: eval-data-export-request-001
category: data-governance
risk_level: medium
applicable_tools:
  - Data.ExportRequestPrepare
  - Data.ExportRequestExecute
gated_tools:
  - Data.ExportRequestExecute
never_permitted:
  - export_dataset_classified_as_restricted
source: Synthetic evaluation corpus (retrieval-evaluation test fixture, not a shipped runtime policy)
---

# Data Export Request Policy

## Context

Governs exporting a dataset out of the organization's managed systems for an
internal or external requester. This is distinct from retention/deletion or
classification review.

## Rule

Executing a data export requires evidenced approval before it may proceed.
Exporting a dataset classified as restricted is never permitted through this
path regardless of approval evidence. This policy does not cover
retention/deletion schedules or classification review.
