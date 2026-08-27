---
id: eval-compliance-audit-log-export-001
category: compliance
risk_level: medium
applicable_tools:
  - Compliance.AuditLogExportExecute
  - Compliance.AuditLogExportPrepare
gated_tools:
  - Compliance.AuditLogExportExecute
never_permitted:
  - export_audit_log_with_unmasked_credentials
source: Synthetic evaluation corpus (retrieval-evaluation test fixture, not a shipped runtime policy)
---

# Compliance Audit Log Export Policy

## Context

Governs exporting system audit logs for a compliance review or external
auditor.

## Rule

Executing an audit-log export requires evidenced approval before it may
proceed. Exporting an audit log with unmasked credentials is never permitted,
regardless of approval evidence.
