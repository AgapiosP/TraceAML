"""Offline provisioning, encrypted backups, and synthetic demo seeding."""

from __future__ import annotations

import base64
import json
import os
import secrets
import sqlite3
import tempfile
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

from .demo import SCENARIOS
from .entities import Account, AccountStatus, CaseStatus, InvestigationCase, Tenant
from .pipeline import TraceAMLEngine
from .security import AESGCMFieldCipher
from .storage import SQLiteWorkspace


def write_private(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)


def provision(
    directory: Path, tenant_id: str, tenant_name: str, subject: str, demo: bool = False
) -> dict:
    from .service import Principal

    # Refuse to overwrite any existing workspace or key material.
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if any(directory.iterdir()):
        raise ValueError("provisioning requires an empty directory")
    token = secrets.token_urlsafe(32)
    expiry = datetime.now(UTC) + timedelta(days=30)
    p = Principal(subject, tenant_id, "admin", sha256(token.encode()).hexdigest(), expiry)
    key = secrets.token_bytes(32)
    cipher = AESGCMFieldCipher(key, "server-v1")
    write_private(directory / "secrets/field.key", base64.b64encode(key) + b"\n")
    write_private(
        directory / "secrets/backup.key", base64.b64encode(secrets.token_bytes(32)) + b"\n"
    )
    principal = {**asdict(p), "expires_at": expiry.isoformat()}
    write_private(directory / "secrets/principals.json", json.dumps([principal], indent=2).encode())
    write_private(directory / "secrets/admin.token", token.encode() + b"\n")
    (directory / "data").mkdir(mode=0o700)
    path = directory / "data/traceaml.db"
    with SQLiteWorkspace(path, cipher, production=True) as db, db.atomic():
        db.create_tenant(Tenant(tenant_id, tenant_name, datetime.now(UTC)))
        db.append_audit(tenant_id, "tenant.created", subject, {"demo": demo})
        if demo:
            seed_demo(db, tenant_id, subject)
    path.chmod(0o600)
    config = {
        "TRACEAML_DATABASE": str(path.resolve()),
        "TRACEAML_FIELD_KEY_FILE": str((directory / "secrets/field.key").resolve()),
        "TRACEAML_PRINCIPALS_FILE": str((directory / "secrets/principals.json").resolve()),
        "TRACEAML_ALLOWED_HOSTS": "127.0.0.1,localhost",
        "TRACEAML_KEY_ID": "server-v1",
    }
    write_private(directory / "service.json", json.dumps(config, indent=2).encode())
    return {
        "directory": str(directory),
        "synthetic": demo,
        "token_file": str(directory / "secrets/admin.token"),
        "expires_at": expiry.isoformat(),
    }


def seed_demo(db: SQLiteWorkspace, tenant_id: str, subject: str) -> None:
    now = datetime.now(UTC)
    seen = set()
    for scenario in SCENARIOS:
        engine = TraceAMLEngine()
        for tx in scenario.transactions:
            for aid in (tx.originator_account, tx.beneficiary_account):
                if aid not in seen:
                    db.put_account(
                        Account(
                            tenant_id,
                            aid,
                            None,
                            "Synthetic " + aid,
                            tx.currency,
                            AccountStatus.ACTIVE,
                            now,
                            attributes={"fixture": "synthetic"},
                        )
                    )
                    seen.add(aid)
            db.put_transaction(tenant_id, tx)
            engine.ingest(tx, actor=subject)
        report = engine.investigate(scenario.subject_account, "eu", actor=subject)
        db.put_case(
            InvestigationCase(
                tenant_id,
                scenario.case_id,
                "SYNTHETIC — " + scenario.customer_name,
                CaseStatus.OPEN,
                now,
                now,
                assignee=subject,
                jurisdiction_packs=("eu",),
                attributes={
                    "fixture": "synthetic",
                    "revision": 1,
                    "notes": [],
                    "subject_account": scenario.subject_account,
                    "report": json.loads(json.dumps(asdict(report), default=str)),
                },
            )
        )
        db.append_audit(tenant_id, "demo.case_seeded", subject, {"case_id": scenario.case_id})


def backup(database: Path, destination: Path, key: bytes) -> None:
    """Use SQLite online backup to capture WAL consistently, then encrypt all bytes."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if not database.is_file():
        raise ValueError("source database does not exist")
    if len(key) != 32:
        raise ValueError("backup key must be 32 bytes")
    with tempfile.TemporaryDirectory() as temp:
        snapshot = Path(temp) / "snapshot.db"
        source = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
        target = sqlite3.connect(snapshot)
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()
        nonce = secrets.token_bytes(12)
        blob = (
            b"TAB1"
            + nonce
            + AESGCM(key).encrypt(nonce, snapshot.read_bytes(), b"traceaml:backup:v1")
        )
        write_private(destination, blob)


def restore(source: Path, destination: Path, key: bytes) -> None:
    """Authenticate before writing; never overwrite a live database."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    blob = source.read_bytes()
    if not blob.startswith(b"TAB1"):
        raise ValueError("unsupported backup format")
    plaintext = AESGCM(key).decrypt(blob[4:16], blob[16:], b"traceaml:backup:v1")
    with tempfile.TemporaryDirectory() as temp:
        snapshot = Path(temp) / "restore.db"
        snapshot.write_bytes(plaintext)
        connection = sqlite3.connect(snapshot)
        try:
            if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("backup integrity check failed")
        finally:
            connection.close()
    write_private(destination, plaintext)
