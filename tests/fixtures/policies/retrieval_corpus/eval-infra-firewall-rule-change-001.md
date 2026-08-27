---
id: eval-infra-firewall-rule-change-001
category: infrastructure
risk_level: high
applicable_tools:
  - Infra.FirewallRuleChangeExecute
  - Infra.FirewallRuleChangePrepare
gated_tools:
  - Infra.FirewallRuleChangeExecute
never_permitted:
  - open_firewall_rule_to_unrestricted_public_internet
source: Synthetic evaluation corpus (retrieval-evaluation test fixture, not a shipped runtime policy)
---

# Firewall Rule Change Policy

## Context

Governs modifying a network firewall rule.

## Rule

Executing a firewall rule change requires evidenced approval before it may
proceed. Opening a firewall rule to unrestricted public internet access is
never permitted, regardless of approval evidence.
