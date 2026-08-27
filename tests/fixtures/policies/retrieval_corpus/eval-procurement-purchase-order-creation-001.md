---
id: eval-procurement-purchase-order-creation-001
category: procurement
risk_level: medium
applicable_tools:
  - Procurement.PurchaseOrderCreateExecute
  - Procurement.PurchaseOrderCreatePrepare
gated_tools:
  - Procurement.PurchaseOrderCreateExecute
never_permitted:
  - create_purchase_order_exceeding_budget_authorization
source: Synthetic evaluation corpus (retrieval-evaluation test fixture, not a shipped runtime policy)
---

# Purchase Order Creation Policy

## Context

Governs creating a new purchase order for goods or services. Distinct from the
vendor cluster policies (lookup, contract renewal, bank-detail change).

## Rule

Executing purchase order creation requires evidenced approval before it may
proceed. Creating a purchase order that exceeds the requester's budget
authorization is never permitted, regardless of approval evidence.
