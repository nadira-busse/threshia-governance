---
id: eval-vendor-contract-renewal-001
category: procurement
risk_level: medium
applicable_tools:
  - Vendor.ContractRenewalPrepare
  - Vendor.ContractRenewalExecute
gated_tools:
  - Vendor.ContractRenewalExecute
never_permitted:
  - renew_contract_past_authorized_term_limit
source: Synthetic evaluation corpus (retrieval-evaluation test fixture, not a shipped runtime policy)
---

# Vendor Contract Renewal Policy

## Context

Governs renewing an existing vendor's contract term. This is a contract-
lifecycle action, distinct from a vendor lookup or a change to a vendor's bank
details.

## Rule

Executing a contract renewal requires evidenced approval before it may
proceed; preparing a renewal draft for review does not. Renewing a contract
past the organization's authorized term limit is never permitted. This policy
does not cover vendor lookups or bank-detail changes.
