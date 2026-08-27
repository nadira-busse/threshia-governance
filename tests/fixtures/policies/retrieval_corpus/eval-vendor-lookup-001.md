---
id: eval-vendor-lookup-001
category: procurement
risk_level: low
applicable_tools:
  - Vendor.ProfileLookup
  - Vendor.PaymentHistoryLookup
gated_tools:
  []
never_permitted:
  - export_vendor_bank_details_in_bulk
source: Synthetic evaluation corpus (retrieval-evaluation test fixture, not a shipped runtime policy)
---

# Vendor Lookup Policy

## Context

Governs read-only lookups of vendor profile and payment-history records in the
procurement system. This does not cover changing a vendor's contract terms or
bank details.

## Rule

Vendor profile and payment-history lookups are read-only and do not require
approval evidence. Bulk export of vendor bank details is never permitted
through this read path. This policy does not cover contract renewal or bank-
detail modification.
