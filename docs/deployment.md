# Single private server deployment

## Supported target

One private Linux host, Docker Engine with Compose v2, encrypted local disk,
HTTPS ingress, one application process, and a local SQLite database. Start with
small investigation teams and measure workload before increasing traffic.
Do not put SQLite on a shared network filesystem or run multiple replicas.

This guide installs a production deployment candidate. Acceptance on the actual
server, independent security review, retention approval, and recovery testing
remain required; see [production readiness](production-readiness.md).

## Prepare the host

- Install maintained Docker/Compose packages, configure security updates, and
  keep administrator access behind a VPN/private network with MFA.
- Enable encrypted volumes covering the database, WAL, secrets, and backups.
- Choose a DNS hostname for the service. Resolve it to the host and allow inbound
  TCP 80/443 to Caddy. Restrict who can reach the hostname using firewall/VPN policy.
- Configure backup storage, monitoring, and a separate secret/key escrow location.
- Do not expose application port 8000 or the legacy demo port 8765 externally.

## Install and provision

From the repository root, use the Python installation instructions in
[getting started](getting-started.md), then provision a **fresh empty** real-data
workspace without `--demo`:

```bash
traceaml provision --directory server --tenant-id institution \
  --tenant-name "Institution investigation workspace" --subject initial-admin
```

There is no demo data in that database. For a server evaluation with synthetic
fixtures, use a separate checkout/directory and pass `--demo`. Never mix fixtures
and real data in one workspace.

The application container runs as UID/GID 10001. Set ownership and restrict paths
on Linux before starting Compose:

```bash
sudo chown -R 10001:10001 server/data server/secrets
sudo chmod 700 server/data server/secrets
sudo chmod 600 server/secrets/* server/data/traceaml.db
```

The repository root and `server` parent must be traversable by the container's
UID. Keep secret files private even if their parent needs traversal permission.
Keep a secured copy of the field key and backup key off the host. Removing or
replacing the field key makes the stored encrypted fields unreadable.

Configure the actual DNS hostname (not a URL):

```bash
export TRACEAML_DOMAIN=traceaml.example.org
docker compose -f deploy/compose.yml config
docker compose -f deploy/compose.yml build --pull
docker compose -f deploy/compose.yml up -d
```

The example domain must be replaced with a hostname you control. Caddy obtains
and renews certificates when DNS and ACME connectivity are correct. For networks
without public ACME reachability, arrange approved internal PKI and replace the
Caddy TLS configuration accordingly.

Compose publishes only HTTPS/HTTP ingress. The backend network is internal, the
application filesystem is read-only except its data volume and temporary mount,
and the container drops capabilities and denies privilege escalation.

## Acceptance checks

```bash
docker compose -f deploy/compose.yml ps
docker compose -f deploy/compose.yml logs --tail=100 app
curl --fail https://traceaml.example.org/health/live
curl --fail https://traceaml.example.org/health/ready
```

Open the HTTPS workspace and sign in with the initial individual's token. Replace
that temporary credential with per-user principals, using the operations guide.
Check viewer write denial, cross-tenant isolation, case mutation/audit verification,
and an encrypted backup restoration on this installation.

All HTTP traffic terminates at Caddy. The application does not trust forwarded
headers. For controlled production releases, pin the Python base image and Caddy
image by approved SHA-256 digest, scan the resulting images, and archive the
source SHA, lockfile, SBOM, scan output, and deployment acceptance record.
The checked-in floating image tags are build templates rather than signed releases.

## Updates and rollback

1. Take an encrypted backup and verify recovery before an update.
2. Record the current source SHA, images/digests, keys, and configuration.
3. Test the new commit and schema against a restored copy on an isolated host.
4. Stop ingestion, stop the service, build the approved image, and restart it.
5. Check readiness, audit integrity, and a representative tenant read/write workflow.

Never start an older build against a newer schema without proving compatibility.
To roll back incompatible migrations, stop all writers, restore the pre-upgrade
backup to a new path, and pair it with the correct old field key and image.
The service has graceful process shutdown, but clients must handle interrupted
requests by reading current state before retrying.

## Capacity boundaries

This candidate provides one application worker and one local SQLite workspace.
Use a local filesystem, off-host backups, and conservative resource limits.
There is no HA, PostgreSQL migration, task queue, object-store evidence vault,
OIDC/MFA login, KMS integration, or multi-region failover. Do not describe a
single-machine service as resilient to host loss. Benchmark a representative
workload before approving an SLA.
