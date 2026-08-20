# ADR 0001: Begin with a Python modular monolith

- Status: accepted
- Date: 2026-08-20

## Decision

Begin TraceAML as a Python modular monolith with a standard-library-only runtime
core. Keep domain, detection, graph, investigation, audit, packs, and application
orchestration as explicit modules with one-way dependencies.

## Rationale

A financial-crime investigation product needs reproducibility and clear audit
boundaries more urgently than distributed-system scale. A single local process is
easier to inspect, test, secure, and deploy for early users. Python provides a
strong future ecosystem for data processing, graph analytics, and ML without
requiring those dependencies in the first release.

## Consequences

- The v0.1 graph and state are in memory and suitable only for demonstrations.
- Durable repositories, API transport, and worker boundaries can be introduced
  behind module interfaces when real workloads justify them.
- The core makes no network calls and remains usable in an offline environment.
- Future extraction into services requires evidence that process isolation or
  independent scaling is worth the operational and governance cost.

