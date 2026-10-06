# User guide

## Access and responsibilities

Every user has an individual, expiring token bound to one tenant. A viewer can
read cases, evidence, verify audit integrity, and download encrypted exports.
An analyst or admin can create accounts, import transactions, and work cases.
Admin currently has the same HTTP permissions as analyst; user administration
is an offline operator task. There is no cross-tenant administrator API.

The browser stores no token in localStorage or cookies. Reloading the page
requires sign-in again. Use only HTTPS for a remote server and protect token
files as credentials. Shared team tokens undermine attribution and are prohibited.

## Case lifecycle

Allowed transitions:

| Current | Next |
| --- | --- |
| open | in_review |
| in_review | escalated or closed |
| escalated | in_review or closed |
| closed | none |

Notes and assignee changes are allowed while a case is open, in review, or
escalated. Closure requires a human-written disposition. Notes are append-only
through the HTTP API. Closed cases are immutable through the API; create a linked
follow-up case if more investigation is needed. There is no automatic filing,
regulator submission, or automated final decision.

Each write includes the case's current integer `revision`. A concurrent edit
returns 409 and leaves the stale edit unapplied. Reload and review changes before
retrying. A case write and its tenant audit event commit atomically.

Only an analyst/admin principal in the same tenant can be selected as assignee.
Token renewal requires a server restart; a temporarily expired assignee can still
appear in historical records.

## Evidence and reports

Select a case to view its latest stored report, findings, source evidence, and
transactions. Reports are deterministic outputs of the configured rules and
versioned pack metadata. The service's investigation endpoint uses up to 1,000
direct transactions for the case's subject account; it rejects larger inputs.
It does not promise exhaustive multi-hop detection across all tenant activity.
The original seeded reports also include their scenario's downstream transactions.

A new case can have an optional existing subject account. The **Refresh investigation** action recalculates and persists the case report and advances its
revision. Previously exported reports remain separate immutable files; the case
stores its latest report rather than a complete report-version history.

The authenticated workspace has four case sections:

- **Overview**: investigation brief, observed movements, review progress, pack
  context, and audit verification. Counts reflect saved data, not a risk score.
- **Transactions**: search/filter the case movements, choose **Inspect**, examine
  the amount, accounts, date, countries, and source-linked observations, then
  save **Reviewed** or **Escalated for follow-up** with a required rationale.
- **Evidence**: readable finding cards with observed facts, source transaction
  links, evidence IDs, observation time, and report limitations.
- **Activity & notes**: attributed audit events, review rationales, and investigator
  notes. The timeline covers case events in the latest 1,000 tenant audit events.

Transaction assessments are encrypted with the case, retain up to 100 historical
assessments per transaction, advance the case revision, and commit atomically
with an audit event. Escalating a transaction does not change the case status;
use **Manage case** to change its lifecycle and assignment. Reviewers should
reassess affected movements after refreshing an investigation or importing data.
The view includes the subject and accounts in the latest saved report graph,
including downstream movements; it rejects more than 100 accounts or 1,000 unique
transactions instead of silently truncating them. This is broader than the direct
subject input used when recalculating a report.

**Manage case** restricts status choices to valid transitions. Closed cases show
their human disposition in the brief and disable write controls. Viewers can
inspect evidence and transaction histories, but cannot save changes.

The legacy demonstration at port 8765 remains separate, read-only, and synthetic.
The workspace uses semantic tables, keyboard-operable tabs, native modal dialogs,
visible focus states, responsive layouts, and reduced-motion support. Browser CI
checks the core workflows and automated WCAG A/AA rules; these checks do not
replace an independent accessibility audit.

## Import

Create account IDs first using **Import data → Create an account** or
`POST /v1/accounts`; accounts are tenant scoped.
Upload JSON shaped as `{"transactions": [...]}`. The sample in
`examples/transactions.synthetic.json` illustrates mandatory fields. Amounts
are decimal strings; timestamps require timezone offsets; country/currency codes
are normalized. NaN, infinity, non-positive amounts, duplicates, or missing
linked accounts prevent the entire batch from committing.

Limits: 1 MiB request bodies and 1–1,000 rows. Invalid row reports use zero-based
row indexes. The server does not retain rejected input: the returned report is
the quarantine outcome. Preserve the source and error report in your approved
intake system; do not dump rejected personal data into logs.

The browser accepts CSV directly with headers matching the transaction fields.
Quoted fields are supported; the optional `attributes` column must contain a JSON
object. Amounts stay decimal text. Alternatively, convert and validate offline:

```bash
python examples/convert_csv.py input.csv converted.json
```

The conversion validates every row, keeps decimal text, and refuses an existing
output path. It does not write to the server. Upload the resulting JSON only
after checking its validation outcome.

## Exports

Encrypted exports contain the case, notes, latest report, disposition, pack
references, software version, and export time. AES-GCM authenticates the entire
payload. The export event records the ciphertext hash in the tenant audit chain.
Use `traceaml decrypt-export` with the workspace's field key on a trusted machine.
Exports do not include every tenant transaction or a signed third-party audit
checkpoint. Possession of the field key grants decryption access; control it
separately from routine user tokens.

## Browser limits

The queue pages through 25 cases at a time. Search and status filters apply to
the loaded page; total summary cards cover the entire tenant. Integrations can
page through all cases using the API. A case supports at most 1,000 notes. Transaction ingestion does
not automatically create alerts or cases; create and investigate a case explicitly.
