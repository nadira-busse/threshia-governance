---
id: eval-support-refund-issue-001
category: customer-support
risk_level: medium
applicable_tools:
  - Support.RefundIssueExecute
  - Support.RefundIssuePrepare
gated_tools:
  - Support.RefundIssueExecute
never_permitted:
  - issue_refund_exceeding_original_transaction_amount
source: Synthetic evaluation corpus (retrieval-evaluation test fixture, not a shipped runtime policy)
---

# Support Refund Issuance Policy

## Context

Governs issuing a monetary refund to a customer from support tooling. This is
a financial action initiated from the support domain, distinct from a ticket
lookup or account escalation.

## Rule

Executing a refund requires evidenced approval before it may proceed. Issuing
a refund that exceeds the original transaction amount is never permitted,
regardless of approval evidence. This policy does not cover ticket lookups or
account escalation.
