# TraceAML

TraceAML is an open-source, local-first investigation and control-validation
layer for financial-crime teams. It accepts alerts or transactions from existing
systems, explains why activity was flagged, maps relationships, and produces an
evidence-linked investigation record for a human decision.

> **Status:** v0.2 development / pre-alpha. TraceAML is an investigation aid, not
> legal advice, a filing system, or an autonomous decision-maker.

## Why this shape

TraceAML is not intended to replace a bank's transaction-monitoring stack. The
initial product is a modular investigation layer that can sit after existing AML
or fraud controls. The core remains jurisdiction-neutral; versioned regulatory
packs describe local context for the EU, UK, US, and Australia.

## Current capabilities

- normalized transaction ingestion;
- deterministic, explainable rule evaluation;
- account and transaction relationship graphs;
- evidence-first investigation summaries with claim-to-source links;
- tamper-evident, append-only audit events;
- versioned jurisdiction-pack metadata;
- a local CLI demo with no runtime dependencies outside Python.
- tenant-scoped SQLite persistence with versioned migrations;
- detailed party, account, transaction, relationship, alert, and case records;
- authenticated field encryption for sensitive JSON metadata;
- database-enforced immutable audit rows with per-tenant hash chains;
- deny-by-default routing between local and online LLM providers;
- grounded LLM JSON outputs with mandatory evidence references.

Production APIs, user access controls, filing workflows, trained ML models, and
synthetic control testing remain under development. Their extension points are documented in
[`docs/architecture.md`](docs/architecture.md).

## Quick start

Python 3.11 or newer is required.

```bash
python -m pip install -e .
traceaml demo --pack eu
```

Initialize a durable workspace with authenticated encryption. The key must be a
base64-encoded 32-byte random value and is never written to the database:

```bash
export TRACEAML_FIELD_KEY="$(openssl rand -base64 32)"
traceaml workspace-init --database data/traceaml.db \
  --tenant-id example --tenant-name "Example tenant"
```

For synthetic local testing only, `--development-plaintext` bypasses field
encryption. The application refuses that mode when production safeguards are enabled.

Run the tests without installing third-party packages (macOS/Linux):

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

On Windows PowerShell:

```powershell
$env:PYTHONPATH="src"
python -m unittest discover -s tests -v
```

Or, with the development dependencies installed:

```bash
pytest
ruff check .
```

## Repository map

```text
src/traceaml/domain.py       immutable domain records
src/traceaml/rules.py        explainable detection rules
src/traceaml/graph.py        dependency-free relationship graph
src/traceaml/investigation.py evidence-bound report generation
src/traceaml/audit.py        hash-chained audit events
src/traceaml/entities.py     tenant-scoped investigation entities
src/traceaml/storage.py      SQLite migrations and repositories
src/traceaml/security.py     authenticated field encryption
src/traceaml/llm.py          provider policy and grounded LLM outputs
src/traceaml/pipeline.py     application orchestration
src/traceaml/packs/          jurisdiction-pack metadata
tests/                       unit and end-to-end tests
docs/                        architecture, roadmap, and governance notes
```

## Principles

1. Evidence before narrative.
2. Humans own consequential decisions.
3. Every rule, model, prompt, pack, and output is versioned.
4. Local processing and data minimization are defaults.
5. Regulatory claims are scoped, sourced, reviewed, and never implied by the
   software merely operating.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Security issues should follow
[`SECURITY.md`](SECURITY.md).

Architecture references:

- [`docs/data-model.md`](docs/data-model.md)
- [`docs/security.md`](docs/security.md)
- [`docs/llm-providers.md`](docs/llm-providers.md)
- [`docs/deployment.md`](docs/deployment.md)
