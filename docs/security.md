# Security model and boundaries

## Implemented controls

- Individual high-entropy bearer credentials, constant-time hash comparison,
  timezone-aware expiration, and tenant/role checks on all data routes.
- Viewer read-only behavior; analyst/admin writes; tenant IDs derived from the
  configured principal rather than request body/path selectors.
- AES-256-GCM sensitive-field encryption with tenant/record authenticated context;
  production service rejects plaintext ciphers.
- Whole-payload authenticated encryption for exports and SQLite-consistent backups.
- Transactional case mutation plus audit append; optimistic revision checks;
  allowed state transitions; required human disposition; closed-case immutability.
- Database foreign keys, unique tenant/entity keys, immutable audit triggers,
  per-tenant chained hashes, and startup/readiness audit validation.
- Explicit Host allowlist, 1 MiB streaming body limit, bounded input lists,
  per-peer rate limit, browser CSP, no-store responses, and safe text-only UI output.
- No browser token persistence, no cookie authentication, no cross-origin API policy,
  and no production LLM execution endpoint.
- Non-root application container, private backend network, read-only image,
  capability restrictions, HTTPS ingress, and mounted secret files.
- Credential/body-free structured logging; generic internal errors with request IDs.

## Encryption coverage

Sensitive JSON metadata, names, labels, case titles, assignees, notes, dispositions,
and stored reports are encrypted at the field level. Queryable identifiers,
amounts, timestamps, currencies, countries, status, and relationship endpoints
remain plaintext in SQLite. WAL and deleted pages may retain this metadata.
**Encrypted host volumes and encrypted backup media remain mandatory.** This is
not whole-database SQLCipher encryption.

Key IDs are metadata; this release is not a multi-key decrypting keyring. Use
matching key/configuration pairs and escrow historical field keys for backups.
There is no online KMS retrieval, automatic key rotation, or hardware key attestation.

## Identity boundary

Tokens authorize anyone who possesses them. The service has no password login,
OIDC, MFA, session revocation propagation, or centralized directory. Tokens are
loaded once; revocation requires a restart. An MFA-protected private gateway/VPN
is a deployment requirement for human users when organizational policy requires
MFA. If app-level managed identity is mandatory, this candidate is not sufficient.

The app never trusts arbitrary forwarded identity, host, or IP headers. Do not
add a trusted-header identity adapter without validating the gateway boundary.
Do not run the unauthenticated legacy demo on a public interface.

## Audit boundary

Hash chains detect ordinary modifications; database triggers block API-level
update/delete of audit events. A privileged actor who can alter the database,
triggers, keys, and hashes can rewrite history or truncate a chain. There is no
external signed checkpoint, WORM vault, or independent timestamp authority.
Use external append-only collection/checkpoints if your evidentiary requirements
need protection against host administrators.

## Limits and required reviews

This is a bounded single-server investigation service, with no HA or workload
SLA established. Independent penetration testing, threat modeling, dependency and
image scans, key recovery drills, identity policy review, and privacy/retention
approval are not replaced by passing unit tests. Regulatory packs are context
stubs and need specialist review for any legal interpretation.

The service API is the authorization boundary. Offline CLI/repository access is
an operator privilege that can bypass workflow rules. Limit filesystem, shell,
and key access independently of HTTP roles. There is no field-level export
entitlement: viewers may export encrypted cases and operators with field keys
may decrypt them.

A dependency vulnerability gate and container smoke test run in CI. Floating
container tags, manual secret delivery, and a single host are remaining release
engineering/deployment responsibilities, not claims of verified infrastructure.
Report vulnerabilities privately according to [SECURITY.md](../SECURITY.md).

## Technical references

- https://fastapi.tiangolo.com/deployment/https/
- https://fastapi.tiangolo.com/advanced/behind-a-proxy/
- https://docs.python.org/3/library/sqlite3.html#sqlite3.Connection.backup
- https://cryptography.io/en/latest/hazmat/primitives/aead/
