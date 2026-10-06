# Data model

Every durable record is scoped by `tenant_id`. Identifiers are unique only inside
a tenant, which prevents accidental cross-tenant lookups and allows a customer to
retain its own source-system identifiers. Application methods require the tenant
explicitly; there is no unscoped list API.

## Entities

| Entity | Identity | Important fields | Purpose |
| --- | --- | --- | --- |
| Tenant | `tenant_id` | encrypted name, key ID, creation time | Security and data-ownership boundary |
| Party | `party_id` | kind, encrypted display name and external references, countries | Individual, organization, or unresolved actor |
| Account | `account_id` | optional owner, currency, lifecycle status, encrypted label | Financial account or value-holding instrument |
| Transaction | `transaction_id` | time, amount, currency, originator, beneficiary, countries | Immutable normalized movement of value |
| Relationship | `relationship_id` | typed source/target, relationship type, confidence, observation time | Temporal link for entity resolution and graph analysis |
| Alert | `alert_id` | subject, severity, state, finding IDs | Reviewable output from rules, models, or upstream controls |
| Investigation case | `case_id` | state, alert IDs, assignee, jurisdiction packs, timestamps | Human-owned investigation workflow |
| LLM run | `run_id` | provider/model, classification, hashes, evidence IDs, result state | Reproducibility without storing raw prompts |
| Audit event | `(tenant_id, sequence)` | actor, payload digest, previous hash, event hash | Tamper-evident processing and decision history |

Parties and accounts are separate because ownership can change and a party can own
many accounts. Relationships are polymorphic so devices, addresses, transactions,
and future legal arrangements can participate in the graph without changing every
existing table.

## Sensitive and queryable fields

TraceAML encrypts display metadata, external references, arbitrary attributes,
case titles and assignees with AES-256-GCM. The tenant and record identity are used
as authenticated context, so ciphertext cannot be moved silently between records.

Fields needed for detection—transaction amount, currency, time, account IDs and
country codes—remain queryable in SQLite. Production deployments must therefore
also encrypt the database volume and backups. Application-level field encryption is
defence in depth, not a replacement for full-disk or managed-database encryption.

## Integrity rules

- Accounts can reference only a party in the same tenant.
- Transactions can reference only accounts in the same tenant.
- Duplicate transaction IDs are rejected rather than silently overwritten.
- Confidence is constrained to the inclusive range 0–1.
- Audit rows cannot be updated or deleted through SQLite.
- Case update timestamps cannot predate case creation.

Polymorphic relationship endpoints are validated by the application. A later
migration will add an entity registry to give those endpoints database-level foreign
keys without sacrificing extensibility.


## Case workflow attributes in 0.3.0rc1

Encrypted case attributes carry integer revision (default 1 for older cases),
append-only note objects (ID, author, timestamp, text), optional subject account,
human disposition, latest evidence-linked report, and report scope. This preserves
schema v1 compatibility. The service checks revisions inside the write transaction
and rejects changes after closure. Older offline repository methods remain
operator tools and do not themselves enforce HTTP lifecycle rules.

Reports can be replaced by a new investigation; immutable audit entries identify
the report ID and event, but full historical report payloads are not retained
automatically. Export and retain reviewed versions when your evidence policy
requires historical payloads.
