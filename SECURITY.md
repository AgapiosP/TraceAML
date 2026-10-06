# Security policy

0.3.0rc1 is a private-server deployment candidate. It has authenticated tenant
access, encrypted fields/exports/backups, a bounded case workflow, and automated
security-boundary tests. It has not received an independent penetration test or
production-environment acceptance review.

Before processing real personal or financial data, complete
[the deployment acceptance record](docs/production-readiness.md). Review
[the security model](docs/security.md) and [operations runbook](docs/operations.md),
including plaintext SQLite query metadata, offline operator privileges, token
revocation, and field-key recovery. Never expose the legacy unauthenticated demo.

Report vulnerabilities privately to the repository owner through the hosting
platform until a dedicated security address exists. Do not include real customer
data, keys, access tokens, or decrypted evidence in issue reports. Include a
minimal synthetic reproduction, affected commit/version, and expected behavior.
No support SLA or security certification is implied by this repository.
