# Production acceptance record — 0.3.0rc1

The code is a production deployment candidate for a **single private server**.
It is not a claim that your host, identity system, operational process, or
regulatory use is production-approved. Complete and retain this record before
processing real personal or financial data.

## Repository controls supplied

| Capability | Implementation |
| --- | --- |
| Repeatable install | Runtime and validation dependency snapshots |
| Authenticated access | Expiring per-user bearer hashes, tenant and role checks |
| Durable case workflow | Revision checks, notes, assignment, transitions, disposition |
| Audit integrity | Atomic write/event commits, immutable triggers, hash verification |
| Demonstration | Unique encrypted synthetic workspace with no fixed credentials |
| Service packaging | FastAPI/Uvicorn, non-root Docker, private Compose backend |
| TLS template | Caddy ingress; only ports 80/443 published |
| Recovery tools | Encrypted WAL-consistent backup and authenticated restore |
| Validation | Unit/API tests, dependency gate, container smoke test in CI |
| Documentation | Setup, user/API guides, security, operations and deployment runbooks |

## Target deployment gates

Record owner, date, evidence, and outcome for each. A failing or inapplicable
control requires an explicit risk decision by the accountable organization.

1. Approve the intended workload and measure latency, contention, disk use, and
   recovery behavior with representative data volumes.
2. Review authentication requirements; deploy MFA-protected private access or
   implement managed OIDC if required. Issue individual credentials and test
   expiry, revocation/restart, viewer denial, and tenant isolation.
3. Enable encrypted disk and temporary storage; verify secret ACLs/ownership,
   off-host key escrow, and field-key recovery.
4. Check HTTPS certificates, hostname allowlists, network exposure, firewall/VPN
   restrictions, and unauthorized access from outside the private boundary.
5. Restore an off-host encrypted backup into an isolated environment and verify
   all tenants' audit chains and representative records. Record actual RPO/RTO.
6. Pin approved image digests, produce an SBOM, scan/sign images through your
   organization's release process, and archive reproducible source/lockfiles.
7. Install centralized logging/monitoring and alerting; exercise incident and
   credential/key exposure procedures with an identified on-call owner.
8. Review privacy, residency, retention/deletion, backup expiry, and lawful
   processing. Approve handling of plaintext query metadata and immutable audit.
9. Complete independent security testing and remediate findings. Review the
   privilege boundary of offline operators, export decryption, and key custodians.
10. Review investigation rules and jurisdiction packs with domain specialists;
    retain human review and prohibit automated legal/filing claims.

## Explicitly outside this candidate

HA/multi-region recovery, OIDC/MFA inside the app, KMS rotation, object-storage
attachments, external signed audit checkpoints, regulatory filing integrations,
trained ML scoring, automatic alert generation, and automated data erasure.
Organizations requiring these cannot call this version production-ready until
those requirements are implemented and validated.

The supplied synthetic demo can be run immediately. A real-data launch requires
completion of this acceptance record on the actual target environment.
