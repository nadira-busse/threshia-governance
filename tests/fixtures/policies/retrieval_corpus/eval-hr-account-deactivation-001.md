---
id: eval-hr-account-deactivation-001
category: hr
risk_level: medium
applicable_tools:
  - HR.AccountDeactivateExecute
  - HR.AccountDeactivatePrepare
gated_tools:
  - HR.AccountDeactivateExecute
never_permitted:
  - deactivate_employee_account_without_offboarding_ticket
source: Synthetic evaluation corpus (retrieval-evaluation test fixture, not a shipped runtime policy)
---

# Employee Account Deactivation Policy

## Context

Governs disabling an employee's system access (login, badge, email) when
employment ends or is suspended. This is an identity/account lifecycle action
tied to HR offboarding.

## Rule

Deactivating an employee's account requires an evidenced offboarding or
suspension ticket before execution. Preparing a deactivation request for
review does not require approval; executing it does. This policy does not
cover changing what an active employee is paid, nor accessing an employee's
medical or leave records.
