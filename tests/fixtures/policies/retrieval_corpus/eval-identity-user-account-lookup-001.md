---
id: eval-identity-user-account-lookup-001
category: identity
risk_level: low
applicable_tools:
  - Identity.UserAccountLookup
  - Identity.UserGroupMembershipLookup
gated_tools:
  []
never_permitted:
  - export_full_directory_credentials_dump
source: Synthetic evaluation corpus (retrieval-evaluation test fixture, not a shipped runtime policy)
---

# User Account Lookup Policy

## Context

Governs read-only lookups of a user's account status and group memberships in
the identity system. This does not cover granting privileged roles or
resetting passwords.

## Rule

User account and group-membership lookups are read-only and do not require
approval evidence. A bulk export of a full directory credentials dump is never
permitted through this read path. This policy does not cover privileged-role
assignment or password resets.
