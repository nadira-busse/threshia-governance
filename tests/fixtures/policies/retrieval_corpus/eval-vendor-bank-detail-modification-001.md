---
id: eval-vendor-bank-detail-modification-001
category: procurement
risk_level: high
applicable_tools:
  - Vendor.BankDetailUpdateExecute
  - Vendor.BankDetailUpdatePrepare
gated_tools:
  - Vendor.BankDetailUpdateExecute
never_permitted:
  - modify_vendor_bank_details_without_verification_callback
source: Synthetic evaluation corpus (retrieval-evaluation test fixture, not a shipped runtime policy)
---

# Vendor Bank Detail Modification Policy

## Context

Governs changing the bank account details on file for a vendor. This is a
high-risk financial-fraud surface, distinct from a vendor lookup or a contract
renewal.

## Rule

A vendor bank-detail change requires evidenced approval before execution.
Modifying vendor bank details without an independent verification callback to
the vendor is never permitted, regardless of approval evidence. This policy
does not cover vendor lookups or contract renewal.
