---
id: eval-legal-contract-review-001
category: legal
risk_level: low
applicable_tools:
  - Legal.ContractClauseReview
  - Legal.ContractRiskFlag
gated_tools:
  []
never_permitted:
  - approve_contract_clause_waiving_statutory_liability
source: Synthetic evaluation corpus (retrieval-evaluation test fixture, not a shipped runtime policy)
---

# Legal Contract Review Policy

## Context

Governs reviewing and flagging risk in contract clauses. Advisory/read actions
on general contracts (not vendor contract renewal, which has its own policy).

## Rule

Contract clause review and risk flagging are advisory and do not require
approval evidence. Approving a clause that waives statutory liability is never
permitted through this path.
