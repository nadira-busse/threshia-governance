---
id: erp-controlled-actions-001
category: financial
risk_level: high
applicable_tools:
  - ERP.InvoiceApprovalPrepare
  - ERP.PaymentReviewTrigger
  - ERP.InvoiceLookup
  - ERP.PurchaseOrderMatch
gated_tools:
  - ERP.InvoiceApprovalPrepare
  - ERP.PaymentReviewTrigger
never_permitted:
  - approve_invoice
  - approve_payment
  - release_payment
  - modify_vendor_bank_details
  - bypass_purchase_order_matching
  - override_invoice_exception
  - approve_employee_expense
  - create_financial_commitment
source: Kelvior Agent Approval Procedure + Finance Invoice Assistant agent definition (AGT-FIN-INV-001)
---

# ERP Controlled Actions Policy

## Context

Finance-facing agents connected through the ERP connector
(MCP-ERP, Dynamics 365 Business Central) operate under a
`read_with_controlled_actions` access policy. Read operations
(invoice lookups, purchase order matching) are low-risk. Controlled
actions that write to the ERP or move money are high-risk and require
a human approval gate before execution.

## Rule

**Read-only tool calls are allowed without review.**

Tools: `ERP.InvoiceLookup`, `ERP.PurchaseOrderMatch`.

These retrieve or analyze existing records and never write to the ERP.
No human approval gate is required.

**Controlled actions require a human approval gate before execution.**

Tools: `ERP.InvoiceApprovalPrepare`, `ERP.PaymentReviewTrigger`.

These write to the ERP or initiate a payment-related workflow. Per the
approval procedure, any agent action with
`write_access_enabled: true` and `controlled_actions_enabled: true`
must have `human_approval_gate: true` before it may execute
autonomously. Without an evidenced approval gate, these actions must
be flagged for human review rather than allowed to proceed.

**The machine-enforced never-permitted actions for this policy are
defined in the `never_permitted` frontmatter field above, regardless of
approval gate status.** They cover final financial authorization
(invoice approval, payment approval, payment release), vendor bank-detail
changes, purchase-order-match bypass, invoice exception overrides,
employee expense approval, and creating financial commitments.

These represent final financial authorization or exception-override
actions. The segregation-of-duties principle requires a human
to hold this authority — an agent preparing a recommendation is
acceptable; an agent finalizing the decision is not.

## Verdict guidance

| Action pattern | Verdict |
|---|---|
| Read-only ERP lookup or analysis | ALLOW |
| Controlled action, approval gate evidenced | ALLOW |
| Controlled action, approval gate missing or unknown | FLAG |
| Any action matching the never-permitted list above | BLOCK |
