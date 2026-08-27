---
id: hr-restricted-data-001
category: hr
risk_level: high
applicable_tools:
  - HR.EmployeeProfileLookup
  - HR.TrainingStatusLookup
gated_tools:
  - HR.EmployeeProfileLookup
  - HR.TrainingStatusLookup
never_permitted:
  - modify_employee_record
  - approve_hiring_decision
  - approve_employee_status_change
  - change_training_completion_status
  - access_compensation_data
  - access_medical_or_absence_records
  - provide_legal_or_disciplinary_advice
  - send_personalized_hr_guidance_without_review
source: Kelvior Data Governance Policy + HR Onboarding Helper agent definition (AGT-HR-ONB-001)
---

# HR Restricted Data Policy

## Context

The HRMS connector (MCP-HR, Workday) operates under a
`restricted_hr_context` access policy. Employee profile and training
status data are classified `restricted` and `confidential`. Any tool
call that summarizes or forwards this data to an employee-facing
response requires human review before it is sent.

## Rule

**General onboarding questions and policy explanations are allowed
without review.**

These use approved HR policy content only and do not touch restricted
employee-specific records.

**Any tool call that reads or summarizes employee-specific data
(profile, role, manager, training status) requires evidenced human
approval before the lookup is executed.**

Tools: `HR.EmployeeProfileLookup`, `HR.TrainingStatusLookup`.

Per the HR Onboarding Helper's human oversight configuration, both tools
are gated: the engine flags the call itself when no approval evidence is
present, rather than allowing the lookup and gating only the response
sent onward.

**The machine-enforced never-permitted actions for this policy are
defined in the `never_permitted` frontmatter field above.** They cover
modifying employee records, approving hiring or employee-status
decisions, changing training-completion status, accessing compensation
or medical/absence data, and giving legal, disciplinary, or unreviewed
personalized HR guidance.

Compensation, medical, absence and disciplinary data fall outside the
allowed data scope entirely — no approval gate makes these acceptable
for an agent to access or act on.

## Verdict guidance

| Action pattern | Verdict |
|---|---|
| General policy question, no employee-specific data | ALLOW |
| Employee-specific lookup, human review pending | FLAG |
| Employee-specific lookup, human review evidenced | ALLOW |
| Any action matching the never-permitted list above | BLOCK |
