---
id: eval-support-account-escalation-001
category: customer-support
risk_level: medium
applicable_tools:
  - Support.AccountEscalationExecute
  - Support.AccountEscalationPrepare
gated_tools:
  - Support.AccountEscalationExecute
never_permitted:
  - escalate_account_access_beyond_support_tier_scope
source: Synthetic evaluation corpus (retrieval-evaluation test fixture, not a shipped runtime policy)
---

# Support Account Escalation Policy

## Context

Governs escalating a support agent's access to a customer account beyond
standard tooling (e.g. temporary elevated access to resolve an issue).
Distinct from a ticket lookup or a refund.

## Rule

Executing an account-access escalation requires evidenced approval before it
may proceed. Escalating access beyond the requesting agent's support-tier
scope is never permitted. This policy does not cover ticket lookups or
refunds.
