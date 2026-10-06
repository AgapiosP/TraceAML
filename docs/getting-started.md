# Getting started

## Install

Use Python 3.11–3.13. Create an isolated environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
traceaml --help
```

Windows PowerShell activation: `.\.venv\Scripts\Activate.ps1`. If activation is
restricted by local policy, invoke `.venv\Scripts\python.exe` and
`.venv\Scripts\traceaml.exe` directly; no system-wide policy change is required.

## Provision synthetic data

```bash
traceaml provision --directory demo-server --demo
traceaml serve --config demo-server/service.json
```

The provisioning directory must be empty. The command refuses to overwrite
existing keys or a database. Provisioning writes unique keys and an expiring
individual admin token, then seeds one tenant, three cases, seven transactions,
and account records in one audited transaction.

Browse to http://127.0.0.1:8000. Read `demo-server/secrets/admin.token` on your own
machine and paste it into the sign-in form. The token is retained only in browser
memory; sign out or reload to clear it. The default tenant is `demo`, the subject
is `demo-admin`, and every seeded case is marked `SYNTHETIC`.

The fixture companies are Northstar Imports, Orion Digital Services, and Ember
Studio Collective. They are invented. Findings illustrate review indicators,
not conclusions that an organization committed an offense.

## Walkthrough

1. Open Northstar and inspect the stored report and transactions.
2. Change `open` to `in_review` and save.
3. Add a synthetic note; the case revision advances.
4. Run an investigation to record a fresh report using direct subject-account
   transactions and the selected case pack.
5. Verify the audit chain.
6. Set a human disposition and close the case. Closed cases cannot be edited.
7. Export and decrypt it offline:

```bash
traceaml decrypt-export --source case-export.taenc \
  --output case-export.json --key-file demo-server/secrets/field.key
```

The output must not already exist. Decrypted exports are sensitive; remove them
when no longer needed according to your retention policy.

## Sample import

Use the workspace's **Import JSON** control to select
`examples/transactions.synthetic.json`. The referenced accounts already exist
in the demo. This sample may be imported once: duplicate transaction IDs are
rejected. Rerun the investigation afterward to incorporate it.

## Restart and reset

Stop the process with Ctrl+C and run the same `serve` command to resume. Case
changes persist in `demo-server/data/traceaml.db`.

For a fresh demo, provision a **new** directory, for example `demo-server-2`.
Do not point the demo at a real-data database. Only delete an old demo directory
once you have confirmed it contains no data or keys you need.

## Troubleshooting

| Symptom | Resolution |
| --- | --- |
| Port 8000 already used | Add `--port 8001`; browse to that port. |
| Invalid/expired token | Verify the token file for this workspace; renew access using the operations guide. |
| Case changed | Reload the selected case and reapply your edit. |
| Invalid transition | Move from open to in_review before escalating or closing. |
| Disposition required | Enter the investigator's rationale before closure. |
| Account not found on import | Create the tenant's accounts through the API before importing. |
| AES authentication failure at startup | Restore the correct field key and database pair; never generate a replacement key over existing data. |
| Provision directory not empty | Choose a new directory; provisioning never overwrites credentials. |
| Encrypted workspace files inaccessible | Check ownership and restrictive file permissions. |

## Update an existing Windows CMD demo

If `demo-server` is already provisioned, keep it: it contains your database, keys,
and access token. Stop the running server with **Ctrl+C**, then run:

```bat
cd C:\Users\agapi\TraceAML
git pull --ff-only
.venv\Scripts\python.exe -m pip install --no-deps -e .
.venv\Scripts\traceaml.exe serve --config demo-server\service.json
```

Open http://127.0.0.1:8000 and press **Ctrl+F5** to reload the browser assets.
Sign in using your existing token from `demo-server\secrets\admin.token`.
The updated workspace uses the existing encrypted cases and adds review records
as you save them; no reprovisioning or database migration is needed.

Choose **Northstar → Transactions → Inspect**, read the supporting observations,
and save a review decision with your rationale. **Evidence** shows the facts as
source-linked cards, while **Activity & notes** records saved assessments and notes.
Use **Manage case** for assignment and lifecycle changes. To close a case, move
it into review first and enter a human disposition.
