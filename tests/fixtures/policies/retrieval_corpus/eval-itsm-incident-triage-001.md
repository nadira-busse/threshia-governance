---
id: eval-itsm-incident-triage-001
category: itsm
risk_level: low
applicable_tools:
  - ITSM.IncidentTriageAssist
  - ITSM.IncidentClassify
gated_tools:
  []
never_permitted:
  - close_incident_without_root_cause_recorded
source: Synthetic evaluation corpus (retrieval-evaluation test fixture, not a shipped runtime policy)
---

# IT Incident Triage Policy

## Context

Governs triaging and classifying IT service-desk incidents.
Read/recommendation actions only.

## Rule

Incident triage assistance and classification are advisory and do not require
approval evidence. Closing an incident without a recorded root cause is never
permitted through this path.
