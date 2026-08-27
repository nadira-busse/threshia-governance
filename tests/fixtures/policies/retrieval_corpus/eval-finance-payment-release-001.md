---
id: eval-finance-payment-release-001
category: finance
risk_level: high
applicable_tools:
  - Finance.PaymentReleaseExecute
  - Finance.PaymentReleasePrepare
gated_tools:
  - Finance.PaymentReleaseExecute
never_permitted:
  - release_payment_to_unverified_bank_account
source: Synthetic evaluation corpus (retrieval-evaluation test fixture, not a shipped runtime policy)
---

# Finance Payment Release Policy

## Context

Governs releasing a payment to a vendor or payee. Distinct from vendor bank-
detail modification, which changes the account on file rather than releasing a
payment.

## Rule

Executing a payment release requires evidenced approval before it may proceed.
Releasing a payment to an unverified bank account is never permitted,
regardless of approval evidence.
