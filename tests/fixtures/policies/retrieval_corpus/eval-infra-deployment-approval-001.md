---
id: eval-infra-deployment-approval-001
category: infrastructure
risk_level: high
applicable_tools:
  - Infra.DeploymentExecute
  - Infra.DeploymentPrepare
gated_tools:
  - Infra.DeploymentExecute
never_permitted:
  - deploy_to_production_without_passing_ci_pipeline
source: Synthetic evaluation corpus (retrieval-evaluation test fixture, not a shipped runtime policy)
---

# Infrastructure Deployment Approval Policy

## Context

Governs deploying a build to production infrastructure.

## Rule

Executing a production deployment requires evidenced approval before it may
proceed. Deploying to production without a passing CI pipeline result is never
permitted, regardless of approval evidence.
