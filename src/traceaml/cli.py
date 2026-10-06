"""Local command-line demonstration."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any

from .domain import Transaction
from .entities import Tenant
from .pipeline import TraceAMLEngine
from .security import AESGCMFieldCipher, DevelopmentPlaintextCipher
from .storage import SQLiteWorkspace


def _json_default(value: Any) -> str:
    if isinstance(value, (datetime, Decimal)):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f"cannot serialize {type(value).__name__}")


def run_demo(pack_id: str) -> dict[str, Any]:
    engine = TraceAMLEngine()
    transactions = (
        Transaction(
            transaction_id="synthetic-tx-001",
            occurred_at=datetime(2026, 1, 15, 10, 30, tzinfo=UTC),
            amount=Decimal("12500.00"),
            currency="EUR",
            originator_account="synthetic-account-a",
            beneficiary_account="synthetic-account-b",
            originator_country="DE",
            beneficiary_country="GB",
            attributes={"fixture": "synthetic"},
        ),
        Transaction(
            transaction_id="synthetic-tx-002",
            occurred_at=datetime(2026, 1, 15, 11, 0, tzinfo=UTC),
            amount=Decimal("500.00"),
            currency="EUR",
            originator_account="synthetic-account-b",
            beneficiary_account="synthetic-account-c",
            originator_country="GB",
            beneficiary_country="GB",
            attributes={"fixture": "synthetic"},
        ),
    )
    for transaction in transactions:
        engine.ingest(transaction, actor="demo")
    report = engine.investigate(
        "synthetic-account-a",
        pack_id,
        actor="demo-investigator",
        created_at=datetime(2026, 1, 15, 12, 0, tzinfo=UTC),
    )
    return {
        "report": asdict(report),
        "audit": {
            "event_count": len(engine.audit.events),
            "chain_valid": engine.audit.verify(),
            "events": [asdict(event) for event in engine.audit.events],
        },
    }


def initialize_workspace(
    path: str,
    tenant_id: str,
    tenant_name: str,
    development_plaintext: bool,
) -> dict[str, Any]:
    if development_plaintext:
        cipher = DevelopmentPlaintextCipher()
        production = False
    else:
        cipher = AESGCMFieldCipher.from_base64_environment(
            "TRACEAML_FIELD_KEY", key_id="environment-v1"
        )
        production = True
    created_at = datetime.now(UTC)
    with SQLiteWorkspace(path, cipher, production=production) as workspace:
        workspace.create_tenant(Tenant(tenant_id, tenant_name, created_at))
        workspace.append_audit(
            tenant_id,
            "tenant.created",
            "workspace-initializer",
            {"tenant_id": tenant_id, "cipher_key_id": cipher.key_id},
        )
        audit_valid = workspace.verify_audit(tenant_id)
    return {
        "database": path,
        "tenant_id": tenant_id,
        "cipher_key_id": cipher.key_id,
        "audit_valid": audit_valid,
        "development_plaintext": development_plaintext,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="traceaml")
    subparsers = parser.add_subparsers(dest="command", required=True)
    demo = subparsers.add_parser("demo", help="run a synthetic local investigation")
    demo.add_argument("--pack", choices=("eu", "uk", "us", "au"), default="eu")
    workspace = subparsers.add_parser(
        "workspace-init", help="initialize a durable tenant workspace"
    )
    workspace.add_argument("--database", required=True)
    workspace.add_argument("--tenant-id", required=True)
    workspace.add_argument("--tenant-name", required=True)
    workspace.add_argument(
        "--development-plaintext",
        action="store_true",
        help="unsafe; use only with synthetic local data",
    )
    customer_demo = subparsers.add_parser(
        "demo-ui", help="launch the synthetic customer demonstration"
    )
    customer_demo.add_argument("--host", default="127.0.0.1")
    customer_demo.add_argument("--port", type=int, default=8765)
    customer_demo.add_argument("--no-browser", action="store_true")
    provision = subparsers.add_parser("provision", help="create an encrypted server workspace")
    provision.add_argument("--directory", required=True)
    provision.add_argument("--tenant-id", default="demo")
    provision.add_argument("--tenant-name", default="Synthetic demonstration")
    provision.add_argument("--subject", default="demo-admin")
    provision.add_argument("--demo", action="store_true", help="seed synthetic cases")
    serve = subparsers.add_parser("serve", help="run the authenticated private service")
    serve.add_argument("--config", help="private JSON file containing service environment paths")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    for name in ("backup", "restore"):
        command = subparsers.add_parser(name, help="encrypted SQLite " + name)
        command.add_argument("--source", required=True)
        command.add_argument("--output", required=True)
        command.add_argument("--key-file", required=True)
    decrypt = subparsers.add_parser("decrypt-export", help="decrypt a case export offline")
    decrypt.add_argument("--source", required=True)
    decrypt.add_argument("--output", required=True)
    decrypt.add_argument("--key-file", required=True)
    args = parser.parse_args(argv)
    if args.command == "demo":
        print(json.dumps(run_demo(args.pack), indent=2, default=_json_default))
    elif args.command == "workspace-init":
        result = initialize_workspace(
            args.database,
            args.tenant_id,
            args.tenant_name,
            args.development_plaintext,
        )
        print(json.dumps(result, indent=2, default=_json_default))
    elif args.command == "demo-ui":
        from .demo import run_demo_server

        run_demo_server(args.host, args.port, open_browser=not args.no_browser)
    elif args.command == "provision":
        from .operations import provision

        print(
            json.dumps(
                provision(
                    Path(args.directory), args.tenant_id, args.tenant_name, args.subject, args.demo
                ),
                indent=2,
            )
        )
    elif args.command == "serve":
        import logging

        import uvicorn

        logging.basicConfig(level=logging.INFO, format="%(message)s")

        if args.config:
            from .service import secret_file

            settings = json.loads(secret_file(args.config))
            for name, value in settings.items():
                if name.startswith("TRACEAML_"):
                    os.environ[name] = value
        uvicorn.run(
            "traceaml.service:create_app",
            factory=True,
            host=args.host,
            port=args.port,
            workers=1,
            proxy_headers=False,
            access_log=False,
            timeout_keep_alive=5,
        )
    elif args.command in ("backup", "restore"):
        import base64

        from .operations import backup, restore
        from .service import secret_file

        key = base64.b64decode(secret_file(args.key_file).strip(), validate=True)
        operation = backup if args.command == "backup" else restore
        operation(Path(args.source), Path(args.output), key)
        print(json.dumps({"output": args.output, "operation": args.command}))
    elif args.command == "decrypt-export":
        import base64

        from .operations import write_private
        from .service import secret_file

        key = base64.b64decode(secret_file(args.key_file).strip(), validate=True)
        cipher = AESGCMFieldCipher(key, "server-v1")
        payload = cipher.decrypt_json(Path(args.source).read_bytes(), "traceaml:case-export:v1")
        write_private(Path(args.output), json.dumps(payload, indent=2).encode())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
