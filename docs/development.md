# Development and validation

## Reproducible environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.lock
python -m pip install --no-deps -e .
ruff check .
pytest --cov=traceaml --cov-report=term-missing
```

Use Python 3.11, 3.12, or 3.13. CI runs those versions separately. Installing
`.[dev]` remains supported, but the committed snapshots reproduce the validated
version set. Runtime lockfile excludes test tooling. No test uses real customers
or external LLM providers.

## Tests

Tests cover the deterministic engine, transaction validation, graph neighborhoods,
grounded LLM policy/output validation, encrypted storage, immutable audit events,
and both synthetic demo and authenticated service. API tests exercise missing and
expired credentials, role denial, tenant isolation, revision conflicts, human
closure, notes, input limits, invalid host denial, import rollback, investigation,
encrypted exports, wrong-key recovery, and rollback when audit append fails.

The container job starts a provisioned synthetic service, checks readiness,
rejects unauthenticated case reads, reads the three cases with a generated token,
and rejects a 1 MiB-plus request through the real ASGI server. It also verifies
packaged browser assets. This detects deployment/wheel issues that unit tests
alone cannot establish.

## Dependency and image validation

CI installs the snapshot, runs lint/tests, and runs `pip-audit` against runtime
requirements. A finding fails the job; investigate rather than adding an ignore
without a recorded security decision. It also produces `pip inspect` package
metadata as an artifact. That inventory is not a signed container SBOM.

Regenerate snapshots deliberately in a clean environment after reviewing upstream
release/security notes. Run all supported Python versions and scan the resulting
container. Preserve exact source SHA and approved image digests when releasing.
Do not commit local environments, tokens, keys, databases, exports, or backups.

## Local CLI checks

```bash
traceaml --help
traceaml provision --directory demo-server --demo
traceaml serve --config demo-server/service.json
```

The service has no reload mode by default. Restart it after code or principal
changes. The test client uses temporary encrypted workspaces; provisioning
refuses existing directories to prevent accidental key/data replacement.

## Release process

Use a reviewed feature commit, green CI, dependency/image scan records, and the
actual-host acceptance record. The package currently identifies itself as
`0.3.0rc1`. Do not convert it into a final production release or make compliance
claims solely because synthetic tests are green. Record release approval and
independent reviews according to the deploying organization's process.

## Browser acceptance

CI runs `scripts/gui_e2e.cjs` in Chromium against a temporary, newly provisioned
synthetic workspace. It covers sign-in, evidence cards, source inspection,
transaction assessment persistence, notes and safe text rendering, assignment,
valid transitions and closure, JSON rejection/CSV import, account/case creation,
report refresh, audit verification, encrypted downloads, viewer restrictions,
keyboard tab navigation, modal Escape, responsive overflow, and axe WCAG A/AA
checks. Screenshots are uploaded as `workspace-browser-previews`.

To reproduce in a development environment that supports local browsers:

```bash
npm install --no-save --package-lock=false playwright@1.58.2 @axe-core/playwright@4.10.2
npx playwright install --with-deps chromium
node scripts/gui_e2e.cjs
```

Activate the Python environment first. The script uses `python`; set
`TRACEAML_TEST_PYTHON` to a different executable if needed. It starts its own
service on port 8127, never uses your demo database, and deletes its temporary
workspace on completion. Automated accessibility checks are one validation layer,
not certification of every assistive-technology experience.
