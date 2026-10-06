"""Local command-line demonstration."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from .domain import Transaction
from .pipeline import TraceAMLEngine


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="traceaml")
    subparsers = parser.add_subparsers(dest="command", required=True)
    demo = subparsers.add_parser("demo", help="run a synthetic local investigation")
    demo.add_argument("--pack", choices=("eu", "uk", "us", "au"), default="eu")
    args = parser.parse_args(argv)
    if args.command == "demo":
        print(json.dumps(run_demo(args.pack), indent=2, default=_json_default))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

