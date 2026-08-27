---
id: eval-data-retention-deletion-001
category: data-governance
risk_level: high
applicable_tools:
  - Data.RetentionDeletionExecute
  - Data.RetentionDeletionPrepare
gated_tools:
  - Data.RetentionDeletionExecute
never_permitted:
  - delete_data_under_active_legal_hold
source: Synthetic evaluation corpus (retrieval-evaluation test fixture, not a shipped runtime policy)
---

# Data Retention and Deletion Policy

## Context

Governs deleting data once its retention period has expired. This is distinct
from an export request or a classification review.

## Rule

Executing a retention-driven deletion requires evidenced approval before it
may proceed. Deleting data under an active legal hold is never permitted,
regardless of approval evidence. This policy does not cover export requests or
classification review.
