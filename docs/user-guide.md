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

A new case can have an optional existing subject account. The **Run explainable
investigation** action recalculates and persists the case report and advances its
revision. Previously exported reports remain separate immutable files; the case
stores its latest report rather than a complete report-version history.

The browser is a functional case workspace. The legacy polished demonstration
at port 8765 is separate, read-only, and synthetic.

## Import

Create account IDs first using `POST /v1/accounts`; accounts are tenant scoped.
Upload JSON shaped as `{"transactions": [...]}`. The sample in
`examples/transactions.synthetic.json` illustrates mandatory fields. Amounts
are decimal strings; timestamps require timezone offsets; country/currency codes
are normalized. NaN, infinity, non-positive amounts, duplicates, or missing
linked accounts prevent the entire batch from committing.

Limits: 1 MiB request bodies and 1–1,000 rows. Invalid row reports use zero-based
row indexes. The server does not retain rejected input: the returned report is
the quarantine outcome. Preserve the source and error report in your approved
intake system; do not dump rejected personal data into logs.

For CSV, use headers matching the transaction fields and convert first:

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

The workspace shows the first 100 cases. Integrations can page through all cases
using the API. A case supports at most 1,000 notes. Transaction ingestion does
not automatically create alerts or cases; create and investigate a case explicitly.
