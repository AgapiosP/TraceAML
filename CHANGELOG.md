# Changelog

## 0.3.0rc1 — private-server deployment candidate

- Added authenticated FastAPI service and individual expiring tenant/role tokens.
- Added functional case browser: creation, notes, assignment, optimistic revision
  checks, state transitions, human disposition, evidence, and encrypted exports.
- Added account creation, atomic JSON import, CSV conversion helper, and bounded
  deterministic investigations.
- Added uniquely provisioned encrypted synthetic demo data and local run commands.
- Added whole-database encrypted online backup/restore and offline export decryption.
- Made repository operations participate in an atomic service unit of work so
  data mutation and audit append succeed or roll back together.
- Made initial schema creation transactional; rejected non-finite transaction amounts.
- Added non-root Docker packaging, private backend Compose configuration, and HTTPS ingress.
- Added dependency snapshots, cross-version/API tests, dependency audit, and
  container smoke validation.
- Added setup, user/API manuals, administration/recovery runbooks, and explicit
  actual-deployment acceptance criteria.

## Earlier development

v0.1 provided the explainable engine, graph, evidence reports, and audit chain.
v0.2 development added tenant-scoped SQLite, encrypted sensitive fields, LLM
routing/output policy, and the polished synthetic customer demo. Packaging now
retains the MIT license expression without the obsolete license classifier.
