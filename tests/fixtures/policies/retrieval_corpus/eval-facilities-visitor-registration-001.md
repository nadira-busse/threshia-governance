---
id: eval-facilities-visitor-registration-001
category: facilities
risk_level: low
applicable_tools:
  - Facilities.VisitorRegisterExecute
  - Facilities.VisitorRegisterPrepare
gated_tools:
  []
never_permitted:
  - register_visitor_without_photo_identification_on_file
source: Synthetic evaluation corpus (retrieval-evaluation test fixture, not a shipped runtime policy)
---

# Facilities Visitor Registration Policy

## Context

Governs registering a visitor for office entry.

## Rule

Visitor registration does not require approval evidence beyond the visitor-
management workflow itself. Registering a visitor without photo identification
on file is never permitted through this path.
