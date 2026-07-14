---
id: itsm-readonly-001
category: it_operations
risk_level: low
applicable_tools:
  - ITSM.IncidentLookup
  - ITSM.ClassificationSuggest
  - ITSM.AssignmentGroupRecommend
source: Kelvior Security Policy + IT Ticket Triage agent definition (AGT-ITO-TKT-001)
---

# ITSM Read-Only Policy

## Context

The Kelvior ITSM Connector (MCP-ITSM, ServiceNow) grants IT Ticket
Triage read-only access to incident data. The agent classifies
incidents, suggests priority and recommends assignment groups, but
never changes a ServiceNow record itself. All actual ticket changes
stay human-controlled. This is the clearest ALLOW case in Kelvior's
agent set: read, recommend, summarize — never write.

## Rule

**Read and recommendation tool calls are allowed without review.**

Tools: `ITSM.IncidentLookup`, `ITSM.ClassificationSuggest`,
`ITSM.AssignmentGroupRecommend`.

These retrieve incident context or produce a suggestion for a human
reviewer. None of them write to ServiceNow, so there is no
irreversible action to gate.

**The following actions are never permitted for an autonomous agent:**

- `close_ticket`
- `update_incident_status`
- `change_priority_without_review`
- `assign_ticket_without_review`
- `trigger_change_request`
- `access_privileged_credentials`
- `modify_production_system`
- `execute_remediation_action`

These write to production systems or bypass the human review step
that the agent's `recommendation`-only scope depends on. An agent that
suggests a priority is in scope; an agent that changes it without
review is not.

## Verdict guidance

| Action pattern | Verdict |
|---|---|
| Read incident context or produce a recommendation | ALLOW |
| Any action matching the never-permitted list above | BLOCK |
