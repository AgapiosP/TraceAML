# Roadmap

## v0.1 — foundation

- [x] domain model and transaction validation
- [x] explainable rules and evidence records
- [x] relationship graph and bounded neighborhood queries
- [x] deterministic evidence-linked investigation report
- [x] hash-chained audit trail
- [x] versioned EU, UK, US, and Australia pack stubs
- [x] tests and local demo

## v0.2 — durable local investigation workspace

- [x] SQLite repositories and migrations
- [x] tenant-scoped party, account, transaction, relationship, alert, and case entities
- [x] sensitive-field encryption and immutable per-tenant audit chains
- [x] policy-controlled local/online LLM adapters and grounded-output validation
- [x] bounded case lifecycle, notes, assignments, and human disposition
- [x] atomic JSON import and CSV conversion with returned validation/quarantine reports
- [x] authenticated local API and minimal investigator UI
- [x] encrypted case export with latest evidence report

## v0.3 — graph and detection depth

- [ ] velocity, fan-in/fan-out, cycles, and pass-through rules
- [ ] entity resolution with explainable match evidence
- [ ] pluggable model scorer, model cards, thresholds, and monitoring
- [ ] alert import adapters and deduplication

## v0.4 — evidence-first AI assistance

- [ ] provider-neutral LLM interface and local-model option
- [ ] retrieval restricted to approved case evidence
- [ ] structured outputs, citation validation, prompt/version logging
- [ ] prompt-injection tests and human approval gates

## v0.5 — control validation

- [ ] synthetic entity and transaction scenario DSL
- [ ] control replay, expected outcomes, coverage, and regression reports
- [ ] jurisdiction-specific scenario libraries reviewed by specialists

No release will claim legal or regulatory compliance. Production readiness
requires security, privacy, model-risk, legal, and operational review.


## 0.3.0rc1 — private-server deployment candidate

- [x] individual expiring tokens, tenant checks, and viewer/write roles
- [x] synthetic encrypted provisioning and operating documentation
- [x] Docker/HTTPS deployment template and encrypted backup/restore
- [x] transactional data/audit units, revision checks, and input bounds
- [x] API security tests and container/dependency CI gates
- [ ] independent security review and actual-host acceptance
- [ ] managed identity/MFA integration and KMS-backed key rotation
- [ ] external signed audit checkpoints and privacy retention/erasure workflow
- [ ] high availability and representative workload/SLA validation

The graph/detection expansion previously labelled v0.3 remains future work;
0.3.0rc1 delivers service/deployment foundations, not those detection features.
