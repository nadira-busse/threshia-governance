---
id: eval-facilities-access-badge-request-001
category: facilities
risk_level: low
applicable_tools:
  - Facilities.AccessBadgeRequestExecute
  - Facilities.AccessBadgeRequestPrepare
gated_tools:
  - Facilities.AccessBadgeRequestExecute
never_permitted:
  - issue_badge_granting_data_center_access_without_background_check
source: Synthetic evaluation corpus (retrieval-evaluation test fixture, not a shipped runtime policy)
---

# Facilities Access Badge Request Policy

## Context

Governs issuing a physical access badge for office or restricted-area entry.

## Rule

Executing a badge issuance requires evidenced approval before it may proceed.
Issuing a badge granting data-center access without a completed background
check is never permitted, regardless of approval evidence.
