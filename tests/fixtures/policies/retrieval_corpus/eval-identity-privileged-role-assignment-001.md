---
id: eval-identity-privileged-role-assignment-001
category: identity
risk_level: high
applicable_tools:
  - Identity.PrivilegedRoleGrantExecute
  - Identity.PrivilegedRoleGrantPrepare
gated_tools:
  - Identity.PrivilegedRoleGrantExecute
never_permitted:
  - grant_privileged_role_without_time_bound_expiry
source: Synthetic evaluation corpus (retrieval-evaluation test fixture, not a shipped runtime policy)
---

# Privileged Role Assignment Policy

## Context

Governs granting an administrative or privileged role to a user account. This
is an access-escalation action, distinct from a plain account lookup or a
password reset.

## Rule

Granting a privileged role requires evidenced approval before execution.
Granting a privileged role without a time-bound expiry is never permitted,
regardless of approval evidence. This policy does not cover account lookups or
password resets.
