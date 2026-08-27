---
id: eval-data-classification-review-001
category: data-governance
risk_level: low
applicable_tools:
  - Data.ClassificationReview
  - Data.ClassificationLookup
gated_tools:
  []
never_permitted:
  - reclassify_restricted_dataset_as_public_without_review
source: Synthetic evaluation corpus (retrieval-evaluation test fixture, not a shipped runtime policy)
---

# Data Classification Review Policy

## Context

Governs reviewing or looking up a dataset's current sensitivity
classification. This is a read/analysis action, distinct from export or
deletion.

## Rule

Classification review and lookup are read-only and do not require approval
evidence. Reclassifying a restricted dataset as public without a review step
is never permitted through this path. This policy does not cover export
requests or retention/deletion.
