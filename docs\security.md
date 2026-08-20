# Security architecture

TraceAML handles financial and personal data. The default threat model assumes all
imports, evidence documents, upstream alerts, regulatory-pack content, model output,
and retrieved text may be hostile.

## Implemented controls

- tenant ID on every durable entity and every repository query;
- SQLite foreign keys, bounded queries, parameterized SQL, and migration versions;
- AES-256-GCM sensitive-field encryption with record context as authenticated data;
- no encryption keys stored in the database;
- production-mode rejection of the plaintext development codec;
- immutable audit-table triggers and independently verifiable per-tenant hash chains;
- LLM request/response hashes, provider provenance, model identity, and evidence IDs;
- HTTPS required for online LLM endpoints;
- unencrypted local model endpoints restricted to loopback addresses;
- online LLM processing denied unless its data classification is explicitly allowed;
- no automatic local-to-online fallback;
- strict response-size limits and grounded-output schema validation.

## Trust boundaries

```text
untrusted sources -> validation/normalization -> tenant workspace
                                                   |
                                      evidence policy boundary
                                      /                      \
                              local model              online provider
                         deployment-controlled      explicit opt-in only
```

An LLM is a drafting component, not a principal. It receives no database credentials,
tools, shell, connector access, or authority to change a case. Its output remains
untrusted until schema, citation, and human review gates pass.

## Key management

The current runtime accepts a 32-byte key supplied by the deployment environment.
Production orchestration should retrieve versioned data-encryption keys from a KMS or
secrets manager, inject them only into the application process, and retain old keys
until records have been re-encrypted. Database backups and audit exports require a
separate encryption and retention policy.

## Work still required before production

- OIDC/SAML authentication, MFA integration, RBAC and segregation of duties;
- authorization tests at every service and API boundary;
- external secrets-manager and KMS adapters with rotation;
- secure evidence-object storage, malware scanning and content-type verification;
- retention, deletion, legal-hold and data-subject workflows;
- signed audit checkpoints outside the operational database;
- rate limiting, deployment hardening, monitoring and incident response;
- SBOMs, signed containers, dependency review, SAST/DAST and secret scanning;
- backup restoration and disaster-recovery exercises;
- independent threat modelling, penetration testing and privacy review.

Security claims must describe the deployed configuration. A self-hosted customer is
responsible for host, network, identity-provider, key-management, database-volume and
backup security.

