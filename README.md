# TraceAML

TraceAML is a local-first financial-crime investigation workspace. It imports
transactions, applies deterministic explainable rules, maps account relationships,
and records source-linked evidence for a human investigator.

**Version: 0.3.0rc1 — private-server deployment candidate.** The repository now
includes an authenticated service, durable case workflow, encrypted synthetic demo,
Docker/HTTPS deployment, backups, and operating documentation. It is not an
independently security-certified financial platform. Complete the
[deployment acceptance gates](docs/production-readiness.md) before real-data use.
It never determines legal compliance or makes a filing decision.

## Run the complete demo

Requirements: Python 3.11–3.13, Git, and a browser. On macOS/Linux:

```bash
git clone https://github.com/AgapiosP/TraceAML.git
cd TraceAML
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
traceaml provision --directory demo-server --demo
traceaml serve --config demo-server/service.json
```

On Windows PowerShell, create the same virtual environment with `py -3 -m venv
.venv` and activate it with `.\.venv\Scripts\Activate.ps1`. Then use the same
`python` and `traceaml` commands.

Open **http://127.0.0.1:8000**. Read `demo-server/secrets/admin.token` locally
(`cat` on macOS/Linux or `Get-Content` on PowerShell) and paste it into the sign-in
form. Do not commit, share, or paste that token into an issue. It is generated
uniquely, stored with restrictive permissions, and expires after 30 days.

The encrypted workspace contains three labelled synthetic cases: Northstar,
Orion, and Ember; seven transactions; account records; evidence-linked reports;
and tenant audit events. No real customer data or external LLM calls are used.

Try: select Northstar → **Transactions → Inspect** → save an assessment →
**Manage case** → set **In review** → add a note → refresh the investigation →
verify the audit chain → enter a human disposition → set **Closed** → download
an encrypted case export. Each update is durable and audited. Reload a case if
another investigator has changed its revision.

For the earlier read-only visual walkthrough, `traceaml demo-ui --no-browser`
opens a separate synthetic server on port 8765. It is a local demo only; it has
no authentication and must not be exposed as the production service.

## What is implemented

- Encrypted tenant-scoped SQLite workspace, authenticated JSON fields, and
  immutable hash-chained audit rows.
- Individual expiring bearer tokens stored as SHA-256 hashes in server config;
  viewer, analyst, and admin roles; tenant identity comes from the token.
- Browser case workspace with creation, assignment, revision checks, notes,
  human disposition, immutable closed cases, readable source-linked evidence cards,
  and attributed transaction assessments with a review history.
- Account creation and bounded JSON/CSV browser import with atomic validation;
  CSV-to-JSON conversion helper.
- Deterministic evidence-linked investigations and EU/UK/US/Australia context packs.
- Encrypted case exports and encrypted SQLite-consistent backup/restore commands.
- Single-server Docker packaging, HTTPS Caddy ingress, private backend network,
  non-root application container, health endpoints, and structured access logs.
- Synthetic demo provisioning without hardcoded credentials or encryption keys.

## Documentation

Start at the [documentation index](docs/README.md).

| Task | Guide |
| --- | --- |
| Install and run the demo | [Getting started](docs/getting-started.md) |
| Work cases and import data | [User guide](docs/user-guide.md) |
| Deploy the private server | [Deployment](docs/deployment.md) |
| Integrate with the service | [API reference](docs/api.md) |
| Provision users, rotate tokens, recover data | [Operations runbook](docs/operations.md) |
| Understand controls and limitations | [Security](docs/security.md) |
| Decide whether a real-data rollout can proceed | [Production acceptance](docs/production-readiness.md) |
| Develop and validate changes | [Development and testing](docs/development.md) |
| Understand the records and design | [Data model](docs/data-model.md), [Architecture](docs/architecture.md) |
| Understand LLM boundaries | [LLM provider policy](docs/llm-providers.md) |
| See changes and future scope | [Changelog](CHANGELOG.md), [Roadmap](docs/roadmap.md) |

## Validation

```bash
python -m pip install -r requirements-dev.lock
python -m pip install --no-deps -e .
ruff check .
pytest --cov=traceaml --cov-report=term-missing
```

CI checks Python 3.11, 3.12, and 3.13; audits runtime dependencies; builds the
container; exercises an authenticated synthetic workspace in the container; and
checks browser workflows, responsive layouts, and automated accessibility rules.
The runtime dependency snapshot is in `requirements.lock`; update and audit it
before releasing. This is a single-server, bounded-workload architecture, not
an HA or large-bank monitoring system.
