---
id: eval-legal-litigation-hold-001
category: legal
risk_level: high
applicable_tools:
  - Legal.LitigationHoldExecute
  - Legal.LitigationHoldPrepare
gated_tools:
  - Legal.LitigationHoldExecute
never_permitted:
  - release_litigation_hold_without_counsel_signoff
source: Synthetic evaluation corpus (retrieval-evaluation test fixture, not a shipped runtime policy)
---

# Litigation Hold Policy

## Context

Governs placing or releasing a legal hold on records relevant to litigation.

## Rule

Executing a litigation hold action requires evidenced approval before it may
proceed. Releasing a litigation hold without counsel sign-off is never
permitted, regardless of approval evidence.
