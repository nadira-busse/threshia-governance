---
id: eval-finance-invoice-lookup-001
category: finance
risk_level: low
applicable_tools:
  - Finance.InvoiceLookup
  - Finance.InvoiceHistoryLookup
gated_tools:
  []
never_permitted:
  - export_invoice_dataset_containing_bank_account_numbers
source: Synthetic evaluation corpus (retrieval-evaluation test fixture, not a shipped runtime policy)
---

# Finance Invoice Lookup Policy

## Context

Governs read-only lookups of invoices and invoice history in the finance
system. Distinct from the vendor bank-detail and payment-release policies.

## Rule

Invoice lookup and history lookup are read-only and do not require approval
evidence. Exporting an invoice dataset containing bank account numbers is
never permitted through this read path.
