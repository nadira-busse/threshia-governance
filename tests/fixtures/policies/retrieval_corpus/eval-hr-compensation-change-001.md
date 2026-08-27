---
id: eval-hr-compensation-change-001
category: hr
risk_level: high
applicable_tools:
  - HR.CompensationAdjustExecute
  - HR.CompensationAdjustPrepare
gated_tools:
  - HR.CompensationAdjustExecute
never_permitted:
  - backdate_compensation_change
  - self_approve_compensation_change
source: Synthetic evaluation corpus (retrieval-evaluation test fixture, not a shipped runtime policy)
---

# Employee Compensation Change Policy

## Context

Governs changing an employee's salary, bonus, or other compensation figures in
the HR system. This is a pay-record action, distinct from account access or
medical-record access.

## Rule

A compensation change requires evidenced approval from someone other than the
employee whose pay is being changed before it may execute. Backdating a
compensation change or an employee self-approving their own change is never
permitted, regardless of approval evidence. This policy does not cover
deactivating accounts or accessing medical/absence records.
