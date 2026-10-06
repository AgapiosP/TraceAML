"""Authenticated, tenant-scoped service for a single private server."""

from __future__ import annotations

import base64
import hmac
import json
import logging
import os
import re
import sqlite3
import time
from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from hashlib import sha256
from importlib.resources import files
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import __version__
from .domain import Transaction
from .entities import Account, AccountStatus, CaseStatus, InvestigationCase
from .security import AESGCMFieldCipher
from .storage import SQLiteWorkspace

LOG = logging.getLogger("traceaml.access")
IDENTIFIER = re.compile(r"^[A-Za-z0-9_.@-]{1,128}$")
ROLES = {"viewer", "analyst", "admin"}
MAX_BODY = 1_048_576


def secret_file(path: str) -> bytes:
    source = Path(path)
    if not source.is_file():
        raise ValueError("secret file must exist")
    # Windows st_mode does not represent NTFS ACLs. Enforce ACLs at the OS level.
    if os.name != "nt" and source.stat().st_mode & 0o022:
        raise ValueError("secret files must not be group/world writable")
    if source.stat().st_size > 131_072:
        raise ValueError("secret file too large")
    return source.read_bytes()


@dataclass(frozen=True)
class Principal:
    subject: str
    tenant_id: str
    role: str
    token_hash: str
    expires_at: datetime

    def __post_init__(self) -> None:
        if not IDENTIFIER.fullmatch(self.subject) or not IDENTIFIER.fullmatch(self.tenant_id):
            raise ValueError("invalid principal or tenant identifier")
        if self.role not in ROLES or not re.fullmatch(r"[0-9a-f]{64}", self.token_hash):
            raise ValueError("invalid role or token hash")
        if self.expires_at.tzinfo is None:
            raise ValueError("token expiry must be timezone-aware")


@dataclass(frozen=True)
class ServiceConfig:
    database: Path
    cipher: AESGCMFieldCipher
    principals: tuple[Principal, ...]
    allowed_hosts: tuple[str, ...] = ("localhost", "127.0.0.1")

    def __post_init__(self) -> None:
        if not self.principals or not self.allowed_hosts or "*" in self.allowed_hosts:
            raise ValueError("principals and explicit allowed hosts are required")
        hashes = [p.token_hash for p in self.principals]
        if len(hashes) != len(set(hashes)):
            raise ValueError("token hashes must be unique")
        if not self.database.is_file():
            raise ValueError("initialize the encrypted workspace before starting the service")
        with SQLiteWorkspace(self.database, self.cipher, production=True) as workspace:
            for p in self.principals:
                if workspace.get_tenant(p.tenant_id) is None:
                    raise ValueError("principal references an unknown tenant")
                if not workspace.verify_audit(p.tenant_id):
                    raise ValueError("audit verification failed")

    @classmethod
    def from_environment(cls) -> ServiceConfig:
        key = base64.b64decode(
            secret_file(os.environ["TRACEAML_FIELD_KEY_FILE"]).strip(), validate=True
        )
        cipher = AESGCMFieldCipher(key, os.environ.get("TRACEAML_KEY_ID", "server-v1"))
        records = json.loads(secret_file(os.environ["TRACEAML_PRINCIPALS_FILE"]))
        principals = tuple(
            Principal(
                **{
                    **p,
                    "expires_at": datetime.fromisoformat(p["expires_at"].replace("Z", "+00:00")),
                }
            )
            for p in records
        )
        hosts = tuple(
            h.strip() for h in os.environ["TRACEAML_ALLOWED_HOSTS"].split(",") if h.strip()
        )
        return cls(Path(os.environ["TRACEAML_DATABASE"]), cipher, principals, hosts)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class NewCase(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    subject_account: str | None = Field(default=None, max_length=128)
    alert_ids: list[str] = Field(default_factory=list, max_length=100)
    jurisdiction_packs: list[str] = Field(default_factory=lambda: ["eu"], max_length=4)


class CaseUpdate(StrictModel):
    revision: int = Field(ge=1)
    status: str | None = None
    assignee: str | None = Field(default=None, max_length=128)
    disposition: str | None = Field(default=None, max_length=4000)


class Note(StrictModel):
    revision: int = Field(ge=1)
    text: str = Field(min_length=1, max_length=4000)


class NewAccount(StrictModel):
    account_id: str = Field(min_length=1, max_length=128)
    label: str = Field(min_length=1, max_length=200)
    currency: str = Field(min_length=3, max_length=3)


class Investigation(StrictModel):
    revision: int = Field(ge=1)
    pack_id: str = "eu"


class ImportBatch(StrictModel):
    transactions: list[dict[str, Any]] = Field(min_length=1, max_length=1000)


class BodyLimit:
    """Bound bodies including chunked requests before the framework buffers them."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        chunks = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            size += len(message.get("body", b""))
            if size > MAX_BODY:
                response = JSONResponse({"detail": "request body too large"}, status_code=413)
                return await response(scope, receive, send)
            chunks.append(message.get("body", b""))
            if not message.get("more_body", False):
                break
        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, send)


def create_app(config: ServiceConfig | None = None) -> FastAPI:
    config = config or ServiceConfig.from_environment()
    app = FastAPI(
        title="TraceAML private workspace",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.add_middleware(BodyLimit)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(config.allowed_hosts))
    attempts: OrderedDict[str, tuple[float, int]] = OrderedDict()

    @contextmanager
    def workspace():
        with SQLiteWorkspace(config.database, config.cipher, production=True) as db:
            yield db

    def authorize(request: Request, write: bool = False) -> Principal:
        header = request.headers.get("authorization", "")
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer" or not 32 <= len(token) <= 256:
            raise HTTPException(
                401, "valid bearer token required", headers={"WWW-Authenticate": "Bearer"}
            )
        digest = sha256(token.encode()).hexdigest()
        now = datetime.now(UTC)
        for p in config.principals:
            if hmac.compare_digest(digest, p.token_hash) and p.expires_at > now:
                if write and p.role == "viewer":
                    raise HTTPException(403, "analyst or admin role required")
                request.state.subject = p.subject
                return p
        raise HTTPException(401, "invalid or expired token", headers={"WWW-Authenticate": "Bearer"})

    @app.middleware("http")
    async def controls(request: Request, call_next):
        started = time.monotonic()
        peer = request.client.host if request.client else "unknown"
        window, count = attempts.pop(peer, (started, 0))
        count = 1 if started - window >= 60 else count + 1
        window = started if started - window >= 60 else window
        attempts[peer] = (window, count)
        while len(attempts) > 4096:
            attempts.popitem(last=False)
        request_id = uuid4().hex
        if count > 300:
            response = JSONResponse(
                {"detail": "rate limit exceeded"}, status_code=429, headers={"Retry-After": "60"}
            )
        else:
            try:
                response = await call_next(request)
            except Exception:
                # Avoid logging exception text: it can contain financial data or credentials.
                LOG.error(json.dumps({"request_id": request_id, "event": "internal_error"}))
                response = JSONResponse(
                    {"detail": "internal service error", "request_id": request_id}, status_code=500
                )
        response.headers.update(
            {
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
                "X-Frame-Options": "DENY",
                "Content-Security-Policy": "default-src 'self'; frame-ancestors 'none'; "
                "base-uri 'none'; form-action 'self'",
                "X-Request-ID": request_id,
            }
        )
        LOG.info(
            json.dumps(
                {
                    "request_id": request_id,
                    "method": request.method,
                    "status": response.status_code,
                    "subject": getattr(request.state, "subject", "anonymous"),
                    "duration_ms": round((time.monotonic() - started) * 1000),
                }
            )
        )
        return response

    @app.exception_handler(sqlite3.IntegrityError)
    async def integrity_error(request, exc):
        return JSONResponse({"detail": "record conflict or missing linked record"}, status_code=409)

    @app.exception_handler(ValueError)
    async def validation_error(request, exc):
        return JSONResponse({"detail": "invalid input"}, status_code=422)

    @app.get("/health/live")
    def live():
        return {"status": "ok", "version": __version__}

    @app.get("/health/ready")
    def ready():
        with workspace() as db:
            if db.connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise HTTPException(503, "storage not ready")
            for tenant in {p.tenant_id for p in config.principals}:
                if not db.verify_audit(tenant):
                    raise HTTPException(503, "audit not ready")
        return {"status": "ready"}

    @app.get("/", response_class=HTMLResponse)
    def ui():
        return files("traceaml").joinpath("web/workspace.html").read_text()

    @app.get("/workspace.js")
    def javascript():
        return Response(
            files("traceaml").joinpath("web/workspace.js").read_text(), media_type="text/javascript"
        )

    @app.get("/workspace.css")
    def stylesheet():
        return Response(
            files("traceaml").joinpath("web/workspace.css").read_text(), media_type="text/css"
        )

    @app.get("/v1/me")
    def me(request: Request):
        p = authorize(request)
        return {"subject": p.subject, "tenant_id": p.tenant_id, "role": p.role}

    @app.get("/v1/openapi.json")
    def schema(request: Request):
        authorize(request)
        return app.openapi()

    def find_case(db, tenant, case_id):
        case = db.get_case(tenant, case_id)
        if case is None:
            raise HTTPException(404, "case not found")
        return case

    def revision(case):
        return int(case.attributes.get("revision", 1))

    def check_revision(case, expected):
        if revision(case) != expected:
            raise HTTPException(409, "case changed; reload before updating")
        if case.status == CaseStatus.CLOSED:
            raise HTTPException(409, "closed cases are immutable")

    def case_json(case):
        return {**asdict(case), "revision": revision(case)}

    @app.get("/v1/cases")
    def cases(request: Request, limit: int = 50, offset: int = 0):
        p = authorize(request)
        if not 1 <= limit <= 100 or offset < 0:
            raise HTTPException(422, "invalid pagination")
        with workspace() as db:
            rows = db.connection.execute(
                "SELECT case_id FROM investigation_cases WHERE tenant_id=? "
                "ORDER BY updated_at DESC, case_id LIMIT ? OFFSET ?",
                (p.tenant_id, limit, offset),
            ).fetchall()
            return {"items": [case_json(find_case(db, p.tenant_id, row[0])) for row in rows]}

    @app.post("/v1/cases", status_code=201)
    def new_case(request: Request, body: NewCase):
        p = authorize(request, write=True)
        if not body.title.strip() or not set(body.jurisdiction_packs) <= {"eu", "uk", "us", "au"}:
            raise HTTPException(422, "invalid title or jurisdiction pack")
        now = datetime.now(UTC)
        case = InvestigationCase(
            p.tenant_id,
            "case-" + uuid4().hex,
            body.title.strip(),
            CaseStatus.OPEN,
            now,
            now,
            tuple(body.alert_ids),
            jurisdiction_packs=tuple(body.jurisdiction_packs),
            attributes={"revision": 1, "notes": [], "subject_account": body.subject_account},
        )
        with workspace() as db, db.atomic():
            if body.subject_account and db.get_account(p.tenant_id, body.subject_account) is None:
                raise HTTPException(422, "unknown subject account in this tenant")
            if any(db.get_alert(p.tenant_id, aid) is None for aid in body.alert_ids):
                raise HTTPException(422, "unknown alert in this tenant")
            db.put_case(case)
            db.append_audit(p.tenant_id, "case.created", p.subject, {"case_id": case.case_id})
        return case_json(case)

    @app.get("/v1/cases/{case_id}")
    def get_case(request: Request, case_id: str):
        p = authorize(request)
        with workspace() as db:
            return case_json(find_case(db, p.tenant_id, case_id))

    @app.patch("/v1/cases/{case_id}")
    def update_case(request: Request, case_id: str, body: CaseUpdate):
        p = authorize(request, write=True)
        with workspace() as db, db.atomic():
            case = find_case(db, p.tenant_id, case_id)
            check_revision(case, body.revision)
            state = CaseStatus(body.status) if body.status is not None else case.status
            allowed = {
                CaseStatus.OPEN: {CaseStatus.IN_REVIEW},
                CaseStatus.IN_REVIEW: {CaseStatus.ESCALATED, CaseStatus.CLOSED},
                CaseStatus.ESCALATED: {CaseStatus.IN_REVIEW, CaseStatus.CLOSED},
            }
            if state != case.status and state not in allowed.get(case.status, set()):
                raise HTTPException(409, "invalid case transition")
            if state == CaseStatus.CLOSED and not (body.disposition or "").strip():
                raise HTTPException(422, "human disposition required to close a case")
            assignee = body.assignee if "assignee" in body.model_fields_set else case.assignee
            if assignee is not None and not any(
                x.subject == assignee and x.tenant_id == p.tenant_id and x.role != "viewer"
                for x in config.principals
            ):
                raise HTTPException(422, "assignee must be an analyst in this tenant")
            attrs = {**case.attributes, "revision": body.revision + 1}
            if body.disposition is not None:
                attrs["disposition"] = body.disposition
            updated = replace(
                case,
                status=state,
                assignee=assignee,
                updated_at=datetime.now(UTC),
                attributes=attrs,
            )
            db.put_case(updated)
            db.append_audit(
                p.tenant_id,
                "case.updated",
                p.subject,
                {"case_id": case_id, "status": state.value, "revision": attrs["revision"]},
            )
        return case_json(updated)

    @app.post("/v1/cases/{case_id}/notes", status_code=201)
    def note(request: Request, case_id: str, body: Note):
        p = authorize(request, write=True)
        if not body.text.strip():
            raise HTTPException(422, "note cannot be blank")
        with workspace() as db, db.atomic():
            case = find_case(db, p.tenant_id, case_id)
            check_revision(case, body.revision)
            notes = list(case.attributes.get("notes", []))
            if len(notes) >= 1000:
                raise HTTPException(409, "case note limit reached")
            notes.append(
                {
                    "id": uuid4().hex,
                    "author": p.subject,
                    "text": body.text.strip(),
                    "created_at": datetime.now(UTC).isoformat(),
                }
            )
            updated = replace(
                case,
                updated_at=datetime.now(UTC),
                attributes={**case.attributes, "revision": body.revision + 1, "notes": notes},
            )
            db.put_case(updated)
            db.append_audit(
                p.tenant_id,
                "case.note_added",
                p.subject,
                {"case_id": case_id, "note_id": notes[-1]["id"]},
            )
        return case_json(updated)

    @app.get("/v1/cases/{case_id}/evidence")
    def evidence(request: Request, case_id: str):
        p = authorize(request)
        with workspace() as db:
            case = find_case(db, p.tenant_id, case_id)
            subject = case.attributes.get("subject_account")
            transactions = (
                db.list_transactions_for_account(p.tenant_id, subject, limit=1000)
                if subject
                else ()
            )
            return {
                "report": case.attributes.get("report"),
                "transactions": [t.to_dict() for t in transactions],
            }

    @app.post("/v1/accounts", status_code=201)
    def account(request: Request, body: NewAccount):
        p = authorize(request, write=True)
        if not IDENTIFIER.fullmatch(body.account_id) or not body.label.strip():
            raise HTTPException(422, "invalid account identifier or label")
        item = Account(
            p.tenant_id,
            body.account_id,
            None,
            body.label.strip(),
            body.currency,
            AccountStatus.ACTIVE,
            datetime.now(UTC),
        )
        with workspace() as db, db.atomic():
            if db.get_account(p.tenant_id, body.account_id):
                raise HTTPException(409, "account already exists")
            db.put_account(item)
            db.append_audit(
                p.tenant_id, "account.created", p.subject, {"account_id": body.account_id}
            )
        return asdict(item)

    @app.post("/v1/cases/{case_id}/investigate")
    def investigate(request: Request, case_id: str, body: Investigation):
        from .pipeline import TraceAMLEngine

        p = authorize(request, write=True)
        if body.pack_id not in {"eu", "uk", "us", "au"}:
            raise HTTPException(422, "unknown jurisdiction pack")
        with workspace() as db, db.atomic():
            case = find_case(db, p.tenant_id, case_id)
            check_revision(case, body.revision)
            subject = case.attributes.get("subject_account")
            if not subject:
                raise HTTPException(422, "case requires a subject account")
            transactions = db.list_transactions_for_account(p.tenant_id, subject, limit=1001)
            if len(transactions) > 1000:
                raise HTTPException(409, "account exceeds the 1000-transaction investigation limit")
            engine = TraceAMLEngine()
            for tx in transactions:
                engine.ingest(tx, actor=p.subject)
            report = engine.investigate(subject, body.pack_id, actor=p.subject)
            attrs = {
                **case.attributes,
                "revision": body.revision + 1,
                "report": json.loads(json.dumps(asdict(report), default=str)),
                "report_scope": "up to 1000 direct subject-account transactions",
            }
            updated = replace(
                case,
                updated_at=datetime.now(UTC),
                attributes=attrs,
                jurisdiction_packs=(body.pack_id,),
            )
            db.put_case(updated)
            db.append_audit(
                p.tenant_id,
                "case.investigated",
                p.subject,
                {
                    "case_id": case_id,
                    "report_id": report.report_id,
                    "transaction_count": len(transactions),
                },
            )
        return case_json(updated)

    @app.post("/v1/imports", status_code=201)
    def import_transactions(request: Request, body: ImportBatch):
        p = authorize(request, write=True)
        records = []
        errors = []
        for index, row in enumerate(body.transactions):
            try:
                records.append(Transaction.from_dict(row))
            except (ValueError, TypeError, ArithmeticError):
                errors.append({"row": index, "error": "invalid transaction"})
        if errors:
            # Invalid rows never reach durable storage: quarantine is the returned report.
            return JSONResponse({"accepted": 0, "errors": errors}, status_code=422)
        with workspace() as db, db.atomic():
            for t in records:
                db.put_transaction(p.tenant_id, t)
            db.append_audit(
                p.tenant_id,
                "transactions.imported",
                p.subject,
                {"count": len(records), "ids": [t.transaction_id for t in records]},
            )
        return {"accepted": len(records), "errors": []}

    @app.get("/v1/audit/verify")
    def verify(request: Request):
        p = authorize(request)
        with workspace() as db:
            return {"valid": db.verify_audit(p.tenant_id)}

    @app.post("/v1/cases/{case_id}/export")
    def export(request: Request, case_id: str):
        p = authorize(request)
        with workspace() as db, db.atomic():
            case = find_case(db, p.tenant_id, case_id)
            if not db.verify_audit(p.tenant_id):
                raise HTTPException(409, "audit verification failed")
            payload = {
                "format": "traceaml.case.v1",
                "version": __version__,
                "case": case_json(case),
                "exported_at": datetime.now(UTC).isoformat(),
            }
            # The entire export is encrypted; its AES-GCM envelope authenticates content.
            blob = config.cipher.encrypt_json(
                json.loads(json.dumps(payload, default=str)), "traceaml:case-export:v1"
            )
            db.append_audit(
                p.tenant_id,
                "case.exported",
                p.subject,
                {"case_id": case_id, "sha256": sha256(blob).hexdigest()},
            )
        return Response(
            blob,
            media_type="application/octet-stream",
            headers={"Content-Disposition": 'attachment; filename="case-export.taenc"'},
        )

    return app
