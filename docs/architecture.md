# v0.1 architecture

## Context

TraceAML receives normalized transactions or alerts from a firm's existing
monitoring controls. It enriches them with deterministic findings and graph
context, constructs evidence-bound reports, and records the processing history.
It does not make or file suspicious-activity decisions.

```text
source systems
     |
     v
normalization -> rules / future ML -> graph context -> investigation report
     |                  |                  |                 |
     +------------------+------------------+-----------------+
                                |
                        hash-chained audit log
                                |
                         human disposition
```

## Modules and dependency rule

- **Domain:** immutable, serializable business records. It imports no application
  services.
- **Detection:** rules implement a small protocol and return evidence, not prose.
- **Graph:** an in-process directed multigraph for v0.1. A graph-store adapter can
  replace it without changing the domain.
- **Investigation:** a deterministic report builder. Future LLM adapters must
  produce the same claim/evidence structure and reject unsupported claims.
- **Audit:** chained SHA-256 events. This is tamper-evident, not an immutable
  storage guarantee; production needs signed checkpoints and restricted storage.
- **Packs:** versioned regulatory context. Packs configure presentation and
  review context, not legal conclusions.
- **Pipeline:** coordinates modules and is the only layer that knows the workflow.

## Trust boundaries

All transaction fields, upstream alerts, pack files, model outputs, and retrieved
documents are untrusted input. LLM content must never be treated as instructions,
executable code, or a decision. Connectors and persistence will use ports/adapters
so that secrets and raw data do not leak into domain logic.

## Evidence contract

An investigation `Claim` is valid only when it cites one or more evidence IDs
present in the report. Rules create structured evidence containing the exact
observations and rule version. The report builder validates references before
returning a report. A future LLM can phrase or prioritize grounded claims, but
cannot introduce uncited facts.

## Data and deployment

v0.1 operates in memory and the CLI prints JSON locally. The next persistence
adapter will use SQLite with migration support and application-level encryption
hooks. No telemetry or network request occurs in the core.

## Planned extension ports

- transaction and upstream-alert connectors;
- SQLite/PostgreSQL repositories;
- batch and streaming rule engines;
- calibrated model scorer plus model cards and drift evidence;
- graph-store adapter;
- local and remote LLM adapters behind a redaction/policy boundary;
- signed audit checkpoints and export bundles;
- synthetic scenario generation and control-effectiveness scoring.

