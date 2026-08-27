# Security Policy

## Reporting a vulnerability

If you find a potential security issue in Threshia, please do not open a public GitHub issue.

Use GitHub Private Vulnerability Reporting for this repository instead.

Include, where possible:

- a short description of the issue;
- the affected component, policy, provider integration, or execution path;
- reproduction details;
- potential impact;
- relevant environment or configuration context.

Do not include API keys, tokens, passwords, or other credentials in a report.

## Security boundaries

Threshia evaluates governance rules and can enforce a decision through
`governed_execute()`, but the integrating system remains responsible for
the external tools, their credentials, and the surrounding runtime.

Approval evidence is supplied by the integrating system. Threshia checks
the expected approval value but does not independently authenticate who
approved an action.

Calls to external semantic providers and local audit persistence are
separate trust boundaries. Tool parameter values are excluded from both
by default and can only be included through explicit configuration.

Deployments are responsible for protecting provider credentials, runtime
files, audit data, and the source of approval evidence.

See [Architecture overview](docs/architecture-overview.md) for the detailed
data-flow and responsibility boundaries.

## Supported version

Security fixes, where applicable, target the current repository state on the default branch.

Older revisions and independently modified deployments are not separately maintained.

## Response expectations

No response-time, remediation-time, or support SLA is provided.

Reports are reviewed according to severity, reproducibility, and the current maintenance scope of the repository.
