# Deployment guide

## Synthetic development workspace

```bash
traceaml workspace-init --database data/development.db \
  --tenant-id synthetic --tenant-name "Synthetic tenant" \
  --development-plaintext
```

The flag is intentionally explicit. Never use that database for personal, customer,
financial or otherwise sensitive data.

## Encrypted local workspace

Generate a 32-byte random key with an approved secrets tool and expose its base64
value only to the TraceAML process:

```bash
export TRACEAML_FIELD_KEY="$(openssl rand -base64 32)"
traceaml workspace-init --database data/traceaml.db \
  --tenant-id customer --tenant-name "Customer"
```

Back up the key separately from the database. Losing it makes encrypted metadata
unrecoverable. Reusing a development key in production is prohibited.

## Production gate

The current pre-alpha release is not a supported production deployment. Before a
production pilot, the deployment must add:

1. managed identity, authorization and MFA;
2. KMS-backed key retrieval and rotation;
3. encrypted volumes and encrypted, restoration-tested backups;
4. HTTPS ingress, network policy and restricted administration paths;
5. centralized security logs, metrics, alerts and incident runbooks;
6. signed images, SBOMs and vulnerability gates;
7. data-processing, retention, deletion and subprocessors documentation;
8. an independent penetration test and remediation record.

Container Compose and Kubernetes packaging will be added after the API and worker
boundaries stabilize, avoiding premature operational complexity.

