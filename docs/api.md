# API reference

Base URL for a local demo: `http://127.0.0.1:8000`. Remote deployments require
HTTPS. Prefix data routes with `/v1`. All data routes require an individual
`Authorization: Bearer <token>` header. The tenant and actor come exclusively
from the configured principal; callers cannot select another tenant in a request.

The live schema is available to authenticated users at `GET /v1/openapi.json`.
There is no unauthenticated Swagger page. The browser uses the same API.

## Routes

| Method | Path | Minimum role | Purpose |
| --- | --- | --- | --- |
| GET | `/health/live` | public | Process liveness and version |
| GET | `/health/ready` | public | Storage integrity and configured tenants' audit validity |
| GET | `/v1/me` | viewer | Current subject, tenant, role |
| GET | `/v1/openapi.json` | viewer | Machine-readable schema |
| GET | `/v1/cases?limit=50&offset=0` | viewer | Case page; limit 1–100 |
| POST | `/v1/cases` | analyst | Create a case |
| GET | `/v1/cases/{case_id}` | viewer | Case and revision |
| PATCH | `/v1/cases/{case_id}` | analyst | State, assignee, disposition |
| POST | `/v1/cases/{case_id}/notes` | analyst | Append an investigator note |
| GET | `/v1/cases/{case_id}/evidence` | viewer | Latest report and direct subject transactions |
| POST | `/v1/cases/{case_id}/investigate` | analyst | Persist explainable report |
| POST | `/v1/cases/{case_id}/export` | viewer | Audited encrypted export |
| POST | `/v1/accounts` | analyst | Create an account |
| POST | `/v1/imports` | analyst | Atomic transaction batch |
| GET | `/v1/audit/verify` | viewer | Verify current tenant's audit chain |

## Examples

Set `TRACEAML_TOKEN` from your private token file in a trusted shell. Never
include real token values in scripts, git, screenshots, or issue reports. Examples
assume `BASE_URL=http://127.0.0.1:8000` for local synthetic use.

Create an account:

```bash
curl -sS "$BASE_URL/v1/accounts" \
  -H "Authorization: Bearer $TRACEAML_TOKEN" -H 'Content-Type: application/json' \
  -d '{"account_id":"account-synthetic","label":"Synthetic account","currency":"EUR"}'
```

Create a case:

```bash
curl -sS "$BASE_URL/v1/cases" \
  -H "Authorization: Bearer $TRACEAML_TOKEN" -H 'Content-Type: application/json' \
  -d '{"title":"Synthetic review","subject_account":"account-synthetic","jurisdiction_packs":["eu"]}'
```

Create body: title (1–200 chars), optional subject account, optional alert IDs
(max 100, all must exist in this tenant), jurisdiction packs (eu/uk/us/au, max 4).
The server generates a case ID, timestamps, initial `open` status, and revision 1.

Update body, using the revision from the last read:

```json
{"revision": 1, "status": "in_review", "assignee": "demo-admin"}
```

A null assignee clears assignment. Omitting assignee preserves it. A disposition
is mandatory on closure. Sending unknown fields is rejected. Status transitions
are documented in the user guide.

Append note:

```json
{"revision": 2, "text": "Synthetic activity reviewed against the supplied evidence."}
```

Investigate:

```json
{"revision": 3, "pack_id": "eu"}
```

Import the supplied example once:

```bash
curl -sS "$BASE_URL/v1/imports" \
  -H "Authorization: Bearer $TRACEAML_TOKEN" -H 'Content-Type: application/json' \
  --data-binary @examples/transactions.synthetic.json
```

Success returns `{"accepted": 1, "errors": []}`. Row validation failure returns
422 with `accepted: 0` and zero-based error row indexes. Duplicate transaction IDs
return 422; missing referenced accounts return 409. Both roll back the entire
batch and its audit event.

## Errors and limits

| Status | Meaning | Client action |
| --- | --- | --- |
| 400 | Host not allowlisted | Correct the deployment host configuration |
| 401 | Missing, invalid, revoked, or expired token | Obtain valid individual credentials |
| 403 | Role does not permit writes | Request the correct role |
| 404 | Case absent in this tenant | Check the ID without assuming cross-tenant existence |
| 409 | Revision conflict, transition conflict, immutable closure, or linked-record conflict | Reload/review input before retrying |
| 413 | Request exceeds 1 MiB | Split into bounded batches |
| 422 | Schema, row, assignment, or disposition validation error | Correct input |
| 429 | Service rate limit | Respect Retry-After |
| 500/503 | Internal/storage/audit readiness error | Escalate using request ID |

Case pages are limited to 100 items; transaction batches to 1,000; notes to
4,000 characters and 1,000 notes per case; investigation inputs to 1,000 direct
transactions. Rate limit: 300 requests/minute per TCP peer, per process. Behind
the supplied proxy that is a shared limit for the server. The server deliberately
does not trust caller-supplied forwarded headers. Add per-user/IP admission
controls at a trusted gateway for higher traffic.

Responses carry `Cache-Control: no-store` and an `X-Request-ID`. Mutations do not
support generic idempotency keys; inspect current state before retrying after a
network interruption. Transaction IDs provide duplicate prevention for imports.
