# ADR 0002: Tenant-scoped SQLite with authenticated field encryption

- Status: accepted
- Date: 2026-08-20

## Decision

Use SQLite as the first durable local workspace, put `tenant_id` into every entity
key, encrypt sensitive JSON fields with AES-256-GCM, and keep transaction fields
required by detection queryable. Require deployment-volume encryption in addition to
application-level encryption.

## Rationale

SQLite preserves the local-first product promise and gives design partners a simple,
auditable deployment. Tenant scoping is introduced now so moving to PostgreSQL does
not require redesigning every entity. Authenticated field encryption limits exposure
from a copied database and detects ciphertext tampering or record substitution.

## Consequences

- Production deployments require the `cryptography` dependency and an external key.
- Queryable transaction fields rely on encrypted storage volumes and backups.
- SQLite is suitable for single-node pilots, not high-volume concurrent ingestion.
- PostgreSQL remains the planned multi-user production adapter.

