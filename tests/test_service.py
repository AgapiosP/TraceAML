import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from traceaml.entities import Tenant
from traceaml.operations import backup, provision, restore
from traceaml.security import AESGCMFieldCipher
from traceaml.service import Principal, ServiceConfig, create_app
from traceaml.storage import SQLiteWorkspace


@pytest.fixture
def environment(tmp_path):
    home = tmp_path / "workspace"
    provision(home, "demo", "Synthetic demonstration", "admin", demo=True)
    import base64

    cipher = AESGCMFieldCipher(
        base64.b64decode((home / "secrets/field.key").read_bytes()), "server-v1"
    )
    tokens = {
        "admin": (home / "secrets/admin.token").read_text().strip(),
        "viewer": "v" * 43,
        "other": "o" * 43,
        "expired": "e" * 43,
    }
    with SQLiteWorkspace(home / "data/traceaml.db", cipher, production=True) as db:
        db.create_tenant(Tenant("other", "Other synthetic tenant", datetime.now(UTC)))
    principals = tuple(
        Principal(
            name,
            "other" if name == "other" else "demo",
            "viewer" if name == "viewer" else "admin",
            sha256(token.encode()).hexdigest(),
            datetime.now(UTC) + timedelta(days=-1 if name == "expired" else 1),
        )
        for name, token in tokens.items()
    )
    config = ServiceConfig(home / "data/traceaml.db", cipher, principals, ("testserver",))
    with TestClient(create_app(config)) as client:
        yield client, config, tokens, home


def auth(tokens, role="admin"):
    return {"Authorization": "Bearer " + tokens[role]}


def test_auth_expiry_roles_and_tenant_isolation(environment):
    client, _, tokens, _ = environment
    assert client.get("/v1/cases").status_code == 401
    assert client.get("/v1/cases", headers=auth(tokens, "expired")).status_code == 401
    assert client.get("/v1/cases", headers=auth(tokens, "other")).json()["items"] == []
    assert client.get("/v1/cases/case-northstar", headers=auth(tokens, "other")).status_code == 404
    assert (
        client.post(
            "/v1/cases", json={"title": "attempt"}, headers=auth(tokens, "viewer")
        ).status_code
        == 403
    )
    assert len(client.get("/v1/cases", headers=auth(tokens, "admin")).json()["items"]) == 3
    assert client.get("/v1/cases?limit=101", headers=auth(tokens)).status_code == 422


def test_workflow_revision_notes_disposition_and_export(environment):
    client, config, tokens, _ = environment
    headers = auth(tokens)
    endpoint = "/v1/cases/case-northstar"
    assert (
        client.patch(
            endpoint, json={"revision": 1, "status": "closed"}, headers=headers
        ).status_code
        == 409
    )
    response = client.patch(
        endpoint, json={"revision": 1, "status": "in_review", "assignee": "admin"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["revision"] == 2
    assert client.patch(endpoint, json={"revision": 1}, headers=headers).status_code == 409
    assert (
        client.post(
            endpoint + "/notes",
            json={"revision": 2, "text": "Synthetic review note"},
            headers=headers,
        ).json()["revision"]
        == 3
    )
    assert (
        client.patch(
            endpoint, json={"revision": 3, "status": "closed"}, headers=headers
        ).status_code
        == 422
    )
    response = client.patch(
        endpoint,
        json={
            "revision": 3,
            "status": "closed",
            "disposition": "Synthetic fixture; no filing decision.",
        },
        headers=headers,
    )
    assert response.status_code == 200
    assert (
        client.post(
            endpoint + "/notes", json={"revision": 4, "text": "after closure"}, headers=headers
        ).status_code
        == 409
    )
    export = client.post(endpoint + "/export", headers=headers)
    assert export.status_code == 200
    assert b"Synthetic review note" not in export.content
    payload = config.cipher.decrypt_json(export.content, "traceaml:case-export:v1")
    assert payload["case"]["attributes"]["notes"][0]["author"] == "admin"
    assert client.get("/v1/audit/verify", headers=headers).json() == {"valid": True}
    with SQLiteWorkspace(config.database, config.cipher, production=True) as db:
        assert (
            b"Synthetic review note"
            not in db.connection.execute(
                "SELECT attributes_cipher FROM investigation_cases WHERE case_id='case-northstar'"
            ).fetchone()[0]
        )


def test_invalid_assignment_and_payload_boundaries(environment):
    client, _, tokens, _ = environment
    endpoint = "/v1/cases/case-northstar"
    assert (
        client.patch(
            endpoint, json={"revision": 1, "assignee": "other"}, headers=auth(tokens)
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/v1/cases", json={"title": "valid", "tenant_id": "other"}, headers=auth(tokens)
        ).status_code
        == 422
    )
    assert (
        client.post("/v1/cases", content=b"x" * 1_048_577, headers=auth(tokens)).status_code == 413
    )
    assert client.get("/", headers={"Host": "evil.invalid"}).status_code == 400
    response = client.get("/")
    assert response.headers["cache-control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert "Open your workspace" in response.text


def transaction(identifier="new"):
    return {
        "transaction_id": identifier,
        "occurred_at": "2026-10-01T10:00:00Z",
        "amount": "15000",
        "currency": "EUR",
        "originator_account": "ACCT-NORTHSTAR-01",
        "beneficiary_account": "ACCT-HARBOR-22",
        "originator_country": "DE",
        "beneficiary_country": "GB",
    }


def test_import_validation_rollback_and_investigation(environment):
    client, config, tokens, _ = environment
    headers = auth(tokens)
    bad = {**transaction("bad"), "amount": "NaN"}
    response = client.post(
        "/v1/imports", json={"transactions": [transaction(), bad]}, headers=headers
    )
    assert response.status_code == 422
    assert response.json()["accepted"] == 0
    with SQLiteWorkspace(config.database, config.cipher) as db:
        assert not db.connection.execute(
            "SELECT 1 FROM transactions WHERE transaction_id='new'"
        ).fetchone()
    assert (
        client.post(
            "/v1/imports", json={"transactions": [transaction(), transaction()]}, headers=headers
        ).status_code
        == 422
    )
    with SQLiteWorkspace(config.database, config.cipher) as db:
        assert not db.connection.execute(
            "SELECT 1 FROM transactions WHERE transaction_id='new'"
        ).fetchone()
    assert (
        client.post(
            "/v1/imports", json={"transactions": [transaction()]}, headers=headers
        ).status_code
        == 201
    )
    response = client.post(
        "/v1/cases/case-northstar/investigate",
        json={"revision": 1, "pack_id": "uk"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["attributes"]["report"]["pack_id"] == "uk"
    assert client.get("/v1/audit/verify", headers=headers).json()["valid"]


def test_atomic_write_rolls_back_when_audit_fails(environment, monkeypatch):
    client, _, tokens, _ = environment

    def fail(*args, **kwargs):
        raise RuntimeError("synthetic audit failure")

    monkeypatch.setattr(SQLiteWorkspace, "append_audit", fail)
    response = client.post("/v1/cases", json={"title": "must roll back"}, headers=auth(tokens))
    assert response.status_code == 500
    assert len(client.get("/v1/cases", headers=auth(tokens)).json()["items"]) == 3
    assert "synthetic audit failure" not in response.text


def test_encrypted_backup_restoration_and_wrong_key(environment, tmp_path):
    _, config, _, _ = environment
    output = tmp_path / "backup.taenc"
    key = b"b" * 32
    backup(config.database, output, key)
    assert not output.read_bytes().startswith(b"SQLite")
    destination = tmp_path / "restored.db"
    restore(output, destination, key)
    with SQLiteWorkspace(destination, config.cipher, production=True) as db:
        assert db.get_case("demo", "case-northstar") is not None
        assert db.verify_audit("demo")
    from cryptography.exceptions import InvalidTag

    with pytest.raises(InvalidTag):
        restore(output, tmp_path / "wrong.db", b"w" * 32)
    assert not (tmp_path / "wrong.db").exists()
    with pytest.raises(FileExistsError):
        restore(output, destination, key)


def test_configuration_fails_closed_and_provisioning_never_overwrites(environment):
    _, config, _, home = environment
    with pytest.raises(ValueError, match="empty"):
        provision(home, "demo", "demo", "admin", demo=True)
    with pytest.raises(ValueError):
        ServiceConfig(config.database, config.cipher, config.principals, ("*",))
    with pytest.raises(ValueError):
        ServiceConfig(Path("missing.db"), config.cipher, config.principals)
    assert "token_hash" in json.loads((home / "secrets/principals.json").read_text())[0]
    assert "admin.token" not in (home / "secrets/principals.json").read_text()


def test_account_provisioning_and_new_case_linkage(environment):
    client, _, tokens, _ = environment
    headers = auth(tokens)
    body = {"account_id": "synthetic-new", "label": "Synthetic new account", "currency": "eur"}
    assert client.post("/v1/accounts", json=body, headers=headers).status_code == 201
    assert client.post("/v1/accounts", json=body, headers=headers).status_code == 409
    case = client.post(
        "/v1/cases",
        headers=headers,
        json={"title": "Synthetic follow-up", "subject_account": "synthetic-new"},
    )
    assert case.status_code == 201
    assert case.json()["attributes"]["subject_account"] == "synthetic-new"
    assert (
        client.post(
            "/v1/cases",
            headers=auth(tokens, "other"),
            json={"title": "Cross tenant", "subject_account": "synthetic-new"},
        ).status_code
        == 422
    )


def test_secret_configuration_and_safe_logs(environment, monkeypatch, caplog):
    import logging

    from traceaml.service import secret_file

    client, config, tokens, home = environment
    settings = json.loads((home / "service.json").read_text())
    for key, value in settings.items():
        monkeypatch.setenv(key, value)
    actual = ServiceConfig.from_environment()
    assert actual.database == config.database
    assert len(actual.principals) == 1
    source = home / "unsafe.json"
    source.write_text("[]")
    source.chmod(0o666)
    import os

    if os.name != "nt":
        with pytest.raises(ValueError, match="writable"):
            secret_file(str(source))
    else:
        assert secret_file(str(source)) == b"[]"
    with caplog.at_level(logging.INFO, logger="traceaml.access"):
        client.get("/v1/cases", headers=auth(tokens))
    assert tokens["admin"] not in caplog.text
    assert "Northstar" not in caplog.text
    assert '"subject": "admin"' in caplog.text


def test_tampered_export_and_backup_are_rejected(environment, tmp_path):
    from cryptography.exceptions import InvalidTag

    client, config, tokens, _ = environment
    blob = client.post("/v1/cases/case-northstar/export", headers=auth(tokens)).content
    corrupted = blob[:-1] + bytes([blob[-1] ^ 1])
    with pytest.raises(InvalidTag):
        config.cipher.decrypt_json(corrupted, "traceaml:case-export:v1")
    output = tmp_path / "backup.taenc"
    backup(config.database, output, b"b" * 32)
    blob = output.read_bytes()
    output.write_bytes(blob[:-1] + bytes([blob[-1] ^ 1]))
    with pytest.raises(InvalidTag):
        restore(output, tmp_path / "corrupt.db", b"b" * 32)
    assert not (tmp_path / "corrupt.db").exists()


def test_windows_secret_reads_use_acl_boundary(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from traceaml import service

    source = tmp_path / "service.json"
    source.write_bytes(b'{"synthetic":true}')
    source.chmod(0o666)
    monkeypatch.setattr(service, "os", SimpleNamespace(name="nt"))
    assert service.secret_file(str(source)) == b'{"synthetic":true}'
    with pytest.raises(ValueError, match="exist"):
        service.secret_file(str(tmp_path / "missing.json"))
    source.write_bytes(b"x" * 131_073)
    with pytest.raises(ValueError, match="large"):
        service.secret_file(str(source))
