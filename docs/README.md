# TraceAML documentation

This manual describes 0.3.0rc1. Commands are run from the repository root unless
stated otherwise. The demo and real-data workspaces must always be separate.

## First use

1. [Getting started](getting-started.md): install, provision synthetic data, run,
   sign in, and reset the demo.
2. [User guide](user-guide.md): cases, evidence, transitions, notes, imports, exports.
3. [API reference](api.md): authentication, schemas, routes, limits, and errors.

## Administration

1. [Deployment](deployment.md): Docker, TLS, secrets, volumes, startup, and upgrades.
2. [Operations](operations.md): individual access tokens, revocation, backup,
   restore, health checks, and incident handling.
3. [Security](security.md): implemented controls, threat boundaries, and limitations.
4. [Production acceptance](production-readiness.md): checks required on the actual
   target server before approving a rollout with sensitive data.

## Engineering

- [Development](development.md): repeatable install, tests, CI, dependency changes.
- [Architecture](architecture.md), [data model](data-model.md), and
  [decisions](decisions/0002-secure-local-workspace.md).
- [LLM policy](llm-providers.md): the production service has no LLM execution route.
- [Regulatory packs](regulatory-packs.md): contextual metadata, not compliance engines.
- [Roadmap](roadmap.md), [changelog](../CHANGELOG.md), and
  [legacy demo walkthrough](customer-demo.md).
