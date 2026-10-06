# Operations runbook

## Secrets and identity

Provisioning writes:

| File | Purpose |
| --- | --- |
| `secrets/field.key` | Base64 AES-256 field/export key |
| `secrets/backup.key` | Separate base64 AES-256 whole-database backup key |
| `secrets/principals.json` | Subject, tenant, role, SHA-256 token hash, expiry |
| `secrets/admin.token` | Initial individual's raw access token |
| `service.json` | Local service settings with absolute paths, no raw keys |
| `data/traceaml.db` | Workspace database; WAL/SHM siblings may also exist |

Files are created with mode 0600 on POSIX. On Windows, enforce equivalent NTFS
ACLs manually. Restrict all parent directories and do not put them in source
control. The container's UID must be able to read mounted secrets. Startup rejects
missing, oversized, or group/world-writable secret files. It validates configured
tenants, decryptability, and their audit chains.

Tokens must be high entropy, individual, time-limited, and delivered through an
approved secure channel. Raw tokens never belong in principals.json. To create a
new token, use the operator helper below; it prints only paths, never the token.

```bash
python examples/manage_principal.py server/secrets/principals.json \
  analyst-alex institution analyst server/secrets/alex.token
```

Read the generated token file securely and deliver it to the individual. The
script creates a unique token, stores its SHA-256 hash, assigns the existing tenant,
and sets a 30-day expiry. It refuses an existing token output. Only tenants already
in the workspace may be configured. Bootstrap additional tenants through an
approved offline repository operation before issuing tokens.

Supported roles: viewer (read/verify/export), analyst/admin (case writes and
imports). Admin is not a cross-tenant superuser. After editing on a Docker host, restore UID/GID 10001 ownership and mode 0600
on principals.json and the issued token file. Restart the application after
editing principals because configuration is loaded at process startup.

Revocation: remove the principal entry or set its expiry in the past, then restart
all app processes. Renewal: run the helper with the same subject/tenant and a new
output file; it replaces that subject's entry, then restart. Never share the
initial admin token for ongoing operations. Losing a token does not require
changing the database encryption key.

## Backup

Create an encrypted SQLite online snapshot, including committed WAL data:

```bash
traceaml backup --source server/data/traceaml.db \
  --output backup-2026-10-06.taenc --key-file server/secrets/backup.key
```

Choose a unique timestamped filename for each backup. The command never overwrites
an existing file. It uses SQLite's backup API, then encrypts all database bytes
with an authenticated AES-GCM envelope. A private temporary plaintext snapshot
exists during processing; the host's temporary storage must also be encrypted.

Store backup ciphertext off-host. Escrow the backup key **and the workspace field
key** separately from backups. Restoring whole-database ciphertext needs the backup
key; reading its encrypted metadata also needs the field key. Define a schedule,
retention period, and owner according to business RPO/RTO. No scheduler is enabled
by this repository automatically.

## Restore drill

```bash
traceaml restore --source backup-2026-10-06.taenc \
  --output recovered/traceaml.db --key-file server/secrets/backup.key
```

The destination must not exist. Authentication and SQLite integrity checks run
before any destination is written. An incorrect key or modified ciphertext fails
closed. Start a separate test instance against the restored database with the
matching field key and principals, then verify `/health/ready`, case reads, and
`/v1/audit/verify`. Capture evidence of a successful drill.

For actual recovery, stop the application and all other writers first. Preserve
the original database/WAL/SHM together for investigation. Restore to a fresh data
directory; do not copy a snapshot onto a live database or keep stale WAL files
beside a replacement. Update the Compose mount, restart, and verify tenants before
reopening ingestion.

## Encryption key changes

This candidate has one active field key and no online key rotation/KMS adapter.
Changing `field.key` alone will break decryption; do not do it. For key rotation,
plan and implement a reviewed offline re-encryption migration, validate every
record, preserve audit hashes, and test old backup recovery with escrowed keys.
A requirement for automatic KMS rotation is a rollout blocker until that feature
is implemented for the target organization.

## Monitoring

- Probe `/health/live` for process liveness and `/health/ready` for workspace/audit
  readiness; alert on failure rather than silently restarting around corruption.
- Collect structured application logs from the named `traceaml.access` logger.
  Events include request ID, method, status, actor, and duration; they omit tokens,
  URL parameters, bodies, exception content, and financial data.
- Monitor disk space, WAL growth, backup age, TLS expiry, restart counts, 5xx/429
  rates, and token expiry. Use your platform's log collector and metric agent.
- The container healthcheck probes liveness only. Monitor readiness separately.
  Audit verification scans configured tenants' complete chains; choose a suitable
  probe interval for larger datasets.

## Incident response

Credential exposure: revoke the affected principal and restart, review audit
actors/events, rotate affected tokens, and preserve the incident record. Key
exposure requires a coordinated key migration and review of all recoverable
ciphertext, not merely a service restart.

Audit/readiness failure: stop ingestion and mutations, restrict network access,
preserve database/WAL/SHM and key material, compare off-host backups/checkpoints,
and investigate before restoring service. The audit chain does not protect
against a privileged operator rewriting the database and hashes together.

Storage exhaustion: stop writes, preserve the database, extend encrypted storage,
verify integrity, and resume only after a recovery check. SQLite lock errors mean
capacity/admission controls need review; do not disable durability settings.

Retention/deletion: there is no automated privacy-retention engine. The immutable
audit schema deliberately prevents row deletion. Approve a tenant archival,
crypto-erasure, and backup-retention design before collecting real personal data.
