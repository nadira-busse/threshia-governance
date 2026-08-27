---
id: eval-itsm-server-restart-001
category: itsm
risk_level: high
applicable_tools:
  - ITSM.ServerRestartExecute
  - ITSM.ServerRestartPrepare
gated_tools:
  - ITSM.ServerRestartExecute
never_permitted:
  - restart_server_flagged_as_production_critical_without_change_window
source: Synthetic evaluation corpus (retrieval-evaluation test fixture, not a shipped runtime policy)
---

# Server Restart Policy

## Context

Governs restarting a managed server through IT operations tooling.

## Rule

Executing a server restart requires evidenced approval before it may proceed.
Restarting a server flagged production-critical outside an approved change
window is never permitted, regardless of approval evidence.
