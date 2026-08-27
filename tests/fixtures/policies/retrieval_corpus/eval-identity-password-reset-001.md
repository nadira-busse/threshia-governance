---
id: eval-identity-password-reset-001
category: identity
risk_level: medium
applicable_tools:
  - Identity.PasswordResetExecute
  - Identity.PasswordResetPrepare
gated_tools:
  - Identity.PasswordResetExecute
never_permitted:
  - reset_password_without_identity_verification
source: Synthetic evaluation corpus (retrieval-evaluation test fixture, not a shipped runtime policy)
---

# Password Reset Policy

## Context

Governs resetting a user's account password. This is a credential-recovery
action, distinct from privileged-role assignment or a plain account lookup.

## Rule

Executing a password reset requires evidenced identity verification of the
requesting user before it may proceed. Resetting a password without that
verification is never permitted. This policy does not cover privileged-role
assignment or account lookups.
