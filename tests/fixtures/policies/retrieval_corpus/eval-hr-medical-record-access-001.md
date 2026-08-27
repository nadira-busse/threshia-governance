---
id: eval-hr-medical-record-access-001
category: hr
risk_level: high
applicable_tools:
  - HR.MedicalRecordView
  - HR.AbsenceRecordView
gated_tools:
  []
never_permitted:
  - access_medical_record_outside_case_scope
  - share_medical_record_externally
source: Synthetic evaluation corpus (retrieval-evaluation test fixture, not a shipped runtime policy)
---

# Employee Medical and Absence Record Access Policy

## Context

Governs viewing an employee's medical notes or absence/leave records stored in
the HR system. This is a restricted personal-data category, distinct from pay
changes or account deactivation.

## Rule

Medical and absence record access must remain scoped to the specific case or
leave request it concerns. Accessing a record outside that scope, or sharing a
medical record with a party outside the organization, is never permitted
regardless of any approval claim. This policy does not cover compensation
changes or account deactivation.
