---
id: eval-support-ticket-lookup-001
category: customer-support
risk_level: low
applicable_tools:
  - Support.TicketLookup
  - Support.TicketHistoryLookup
gated_tools:
  []
never_permitted:
  - export_ticket_data_containing_payment_card_numbers
source: Synthetic evaluation corpus (retrieval-evaluation test fixture, not a shipped runtime policy)
---

# Support Ticket Lookup Policy

## Context

Governs read-only lookups of a customer support ticket and its history. This
does not cover issuing a refund or escalating account access.

## Rule

Ticket lookup and history lookup are read-only and do not require approval
evidence. Exporting ticket data containing payment card numbers is never
permitted through this read path. This policy does not cover refunds or
account escalation.
