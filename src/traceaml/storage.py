"""Durable, tenant-scoped SQLite workspace and migration runner."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import Any

from .domain import Severity, Transaction
from .entities import (
    Account,
    AccountStatus,
    Alert,
    AlertStatus,
    CaseStatus,
    DataClassification,
    EntityType,
    InvestigationCase,
    Party,
    PartyKind,
    Relationship,
    Tenant,
)
from .security import FieldCipher, require_secure_cipher

SCHEMA_VERSION = 1


MIGRATION_1 = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
CREATE TABLE tenants (
    tenant_id TEXT PRIMARY KEY,
    name_cipher BLOB NOT NULL,
    key_id TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE parties (
    tenant_id TEXT NOT NULL,
    party_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    countries_json TEXT NOT NULL,
    sensitive_cipher BLOB NOT NULL,
    key_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, party_id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id) ON DELETE RESTRICT
);
CREATE TABLE accounts (
    tenant_id TEXT NOT NULL,
    account_id TEXT NOT NULL,
    party_id TEXT,
    currency TEXT NOT NULL,
    status TEXT NOT NULL,
    sensitive_cipher BLOB NOT NULL,
    key_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, account_id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    FOREIGN KEY (tenant_id, party_id) REFERENCES parties(tenant_id, party_id) ON DELETE RESTRICT
);
CREATE TABLE transactions (
    tenant_id TEXT NOT NULL,
    transaction_id TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    amount TEXT NOT NULL,
    currency TEXT NOT NULL,
    originator_account TEXT NOT NULL,
    beneficiary_account TEXT NOT NULL,
    originator_country TEXT NOT NULL,
    beneficiary_country TEXT NOT NULL,
    attributes_cipher BLOB NOT NULL,
    key_id TEXT NOT NULL,
    PRIMARY KEY (tenant_id, transaction_id),
    FOREIGN KEY (tenant_id, originator_account)
        REFERENCES accounts(tenant_id, account_id) ON DELETE RESTRICT,
    FOREIGN KEY (tenant_id, beneficiary_account)
        REFERENCES accounts(tenant_id, account_id) ON DELETE RESTRICT
);
CREATE INDEX idx_transactions_originator
    ON transactions(tenant_id, originator_account, occurred_at);
CREATE INDEX idx_transactions_beneficiary
    ON transactions(tenant_id, beneficiary_account, occurred_at);
CREATE TABLE relationships (
    tenant_id TEXT NOT NULL,
    relationship_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relationship_type TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    confidence REAL NOT NULL CHECK(confidence >= 0 AND confidence <= 1),
    attributes_cipher BLOB NOT NULL,
    key_id TEXT NOT NULL,
    PRIMARY KEY (tenant_id, relationship_id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id) ON DELETE RESTRICT
);
CREATE INDEX idx_relationships_source
    ON relationships(tenant_id, source_type, source_id);
CREATE INDEX idx_relationships_target
    ON relationships(tenant_id, target_type, target_id);
CREATE TABLE alerts (
    tenant_id TEXT NOT NULL,
    alert_id TEXT NOT NULL,
    subject_type TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    title_cipher BLOB NOT NULL,
    severity TEXT NOT NULL,
    status TEXT NOT NULL,
    finding_ids_json TEXT NOT NULL,
    attributes_cipher BLOB NOT NULL,
    key_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, alert_id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id) ON DELETE RESTRICT
);
CREATE TABLE investigation_cases (
    tenant_id TEXT NOT NULL,
    case_id TEXT NOT NULL,
    status TEXT NOT NULL,
    title_cipher BLOB NOT NULL,
    assignee_cipher BLOB NOT NULL,
    alert_ids_json TEXT NOT NULL,
    packs_json TEXT NOT NULL,
    attributes_cipher BLOB NOT NULL,
    key_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, case_id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id) ON DELETE RESTRICT
);
CREATE TABLE llm_runs (
    tenant_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    provider_kind TEXT NOT NULL,
    classification TEXT NOT NULL,
    purpose TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    response_hash TEXT,
    evidence_ids_json TEXT NOT NULL,
    status TEXT NOT NULL,
    error_code TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, run_id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id) ON DELETE RESTRICT
);
CREATE TABLE audit_events (
    tenant_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    payload_cipher BLOB NOT NULL,
    payload_digest TEXT NOT NULL,
    key_id TEXT NOT NULL,
    previous_hash TEXT NOT NULL,
    event_hash TEXT NOT NULL,
    PRIMARY KEY (tenant_id, sequence),
    UNIQUE (tenant_id, event_hash),
    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id) ON DELETE RESTRICT
);
CREATE TRIGGER audit_events_no_update
BEFORE UPDATE ON audit_events BEGIN
    SELECT RAISE(ABORT, 'audit events are immutable');
END;
CREATE TRIGGER audit_events_no_delete
BEFORE DELETE ON audit_events BEGIN
    SELECT RAISE(ABORT, 'audit events are immutable');
END;
"""


def _utc(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(UTC).isoformat()


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


class SQLiteWorkspace:
    def __init__(
        self,
        path: str | Path,
        cipher: FieldCipher,
        *,
        production: bool = False,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        require_secure_cipher(cipher, production)
        self.path = str(path)
        self.cipher = cipher
        self.clock = clock or (lambda: datetime.now(UTC))
        self.connection = sqlite3.connect(self.path, isolation_level=None)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA busy_timeout = 5000")
        if self.path != ":memory:":
            self.connection.execute("PRAGMA journal_mode = WAL")
            self.connection.execute("PRAGMA synchronous = FULL")
        self._migrate()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> SQLiteWorkspace:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        if self.connection.in_transaction:
            # Repository calls participate in the caller's atomic unit of work.
            yield self.connection
            return
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            yield self.connection
        except Exception:
            self.connection.rollback()
            raise
        else:
            self.connection.commit()

    def atomic(self):
        """Group repository writes and their audit event in one transaction."""
        return self._transaction()

    def _migrate(self) -> None:
        current = self.connection.execute("PRAGMA user_version").fetchone()[0]
        if current > SCHEMA_VERSION:
            raise RuntimeError("database schema is newer than this TraceAML build")
        if current < 1:
            with self._transaction() as connection:
                statement = ""
                for line in MIGRATION_1.splitlines(keepends=True):
                    statement += line
                    if sqlite3.complete_statement(statement):
                        connection.execute(statement)
                        statement = ""
                connection.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (1, _utc(self.clock())),
                )
                connection.execute("PRAGMA user_version = 1")

    def _encrypt(self, value: dict[str, Any], context: str) -> bytes:
        return self.cipher.encrypt_json(value, context)

    def _decrypt(self, value: bytes, context: str) -> dict[str, Any]:
        return self.cipher.decrypt_json(value, context)

    def create_tenant(self, tenant: Tenant) -> None:
        context = f"tenant:{tenant.tenant_id}"
        with self._transaction() as connection:
            connection.execute(
                "INSERT INTO tenants VALUES (?, ?, ?, ?)",
                (
                    tenant.tenant_id,
                    self._encrypt({"name": tenant.name}, context),
                    self.cipher.key_id,
                    _utc(tenant.created_at),
                ),
            )

    def get_tenant(self, tenant_id: str) -> Tenant | None:
        row = self.connection.execute(
            "SELECT * FROM tenants WHERE tenant_id = ?", (tenant_id,)
        ).fetchone()
        if row is None:
            return None
        sensitive = self._decrypt(row["name_cipher"], f"tenant:{tenant_id}")
        return Tenant(tenant_id, sensitive["name"], _parse_time(row["created_at"]))

    def put_party(self, party: Party) -> None:
        context = f"party:{party.tenant_id}:{party.party_id}"
        sensitive = {
            "display_name": party.display_name,
            "external_refs": party.external_refs,
            "attributes": party.attributes,
        }
        with self._transaction() as connection:
            connection.execute(
                """INSERT INTO parties VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(tenant_id, party_id) DO UPDATE SET
                     kind=excluded.kind, countries_json=excluded.countries_json,
                     sensitive_cipher=excluded.sensitive_cipher, key_id=excluded.key_id""",
                (
                    party.tenant_id,
                    party.party_id,
                    party.kind.value,
                    _canonical(party.countries),
                    self._encrypt(sensitive, context),
                    self.cipher.key_id,
                    _utc(party.created_at),
                ),
            )

    def get_party(self, tenant_id: str, party_id: str) -> Party | None:
        row = self.connection.execute(
            "SELECT * FROM parties WHERE tenant_id = ? AND party_id = ?",
            (tenant_id, party_id),
        ).fetchone()
        if row is None:
            return None
        sensitive = self._decrypt(row["sensitive_cipher"], f"party:{tenant_id}:{party_id}")
        return Party(
            tenant_id=tenant_id,
            party_id=party_id,
            kind=PartyKind(row["kind"]),
            display_name=sensitive["display_name"],
            countries=tuple(json.loads(row["countries_json"])),
            external_refs=dict(sensitive["external_refs"]),
            attributes=dict(sensitive["attributes"]),
            created_at=_parse_time(row["created_at"]),
        )

    def put_account(self, account: Account) -> None:
        context = f"account:{account.tenant_id}:{account.account_id}"
        sensitive = {
            "label": account.label,
            "external_refs": account.external_refs,
            "attributes": account.attributes,
        }
        with self._transaction() as connection:
            connection.execute(
                """INSERT INTO accounts VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(tenant_id, account_id) DO UPDATE SET
                     party_id=excluded.party_id, currency=excluded.currency,
                     status=excluded.status, sensitive_cipher=excluded.sensitive_cipher,
                     key_id=excluded.key_id""",
                (
                    account.tenant_id,
                    account.account_id,
                    account.party_id,
                    account.currency,
                    account.status.value,
                    self._encrypt(sensitive, context),
                    self.cipher.key_id,
                    _utc(account.created_at),
                ),
            )

    def get_account(self, tenant_id: str, account_id: str) -> Account | None:
        row = self.connection.execute(
            "SELECT * FROM accounts WHERE tenant_id = ? AND account_id = ?",
            (tenant_id, account_id),
        ).fetchone()
        if row is None:
            return None
        sensitive = self._decrypt(row["sensitive_cipher"], f"account:{tenant_id}:{account_id}")
        return Account(
            tenant_id=tenant_id,
            account_id=account_id,
            party_id=row["party_id"],
            label=sensitive["label"],
            currency=row["currency"],
            status=AccountStatus(row["status"]),
            external_refs=dict(sensitive["external_refs"]),
            attributes=dict(sensitive["attributes"]),
            created_at=_parse_time(row["created_at"]),
        )

    def put_transaction(self, tenant_id: str, transaction: Transaction) -> None:
        context = f"transaction:{tenant_id}:{transaction.transaction_id}"
        with self._transaction() as connection:
            connection.execute(
                """INSERT INTO transactions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(tenant_id, transaction_id) DO NOTHING""",
                (
                    tenant_id,
                    transaction.transaction_id,
                    _utc(transaction.occurred_at),
                    str(transaction.amount),
                    transaction.currency,
                    transaction.originator_account,
                    transaction.beneficiary_account,
                    transaction.originator_country,
                    transaction.beneficiary_country,
                    self._encrypt(transaction.attributes, context),
                    self.cipher.key_id,
                ),
            )
            if connection.execute("SELECT changes()").fetchone()[0] != 1:
                raise ValueError(f"duplicate transaction_id: {transaction.transaction_id}")

    def list_transactions_for_account(
        self, tenant_id: str, account_id: str, limit: int = 100
    ) -> tuple[Transaction, ...]:
        if not 1 <= limit <= 10_000:
            raise ValueError("limit must be between 1 and 10000")
        rows = self.connection.execute(
            """SELECT * FROM transactions
               WHERE tenant_id = ? AND (originator_account = ? OR beneficiary_account = ?)
               ORDER BY occurred_at DESC, transaction_id LIMIT ?""",
            (tenant_id, account_id, account_id, limit),
        ).fetchall()
        return tuple(
            Transaction(
                transaction_id=row["transaction_id"],
                occurred_at=_parse_time(row["occurred_at"]),
                amount=Decimal(row["amount"]),
                currency=row["currency"],
                originator_account=row["originator_account"],
                beneficiary_account=row["beneficiary_account"],
                originator_country=row["originator_country"],
                beneficiary_country=row["beneficiary_country"],
                attributes=self._decrypt(
                    row["attributes_cipher"],
                    f"transaction:{tenant_id}:{row['transaction_id']}",
                ),
            )
            for row in rows
        )

    def put_relationship(self, relationship: Relationship) -> None:
        context = f"relationship:{relationship.tenant_id}:{relationship.relationship_id}"
        with self._transaction() as connection:
            connection.execute(
                """INSERT INTO relationships VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(tenant_id, relationship_id) DO UPDATE SET
                     source_type=excluded.source_type, source_id=excluded.source_id,
                     target_type=excluded.target_type, target_id=excluded.target_id,
                     relationship_type=excluded.relationship_type,
                     observed_at=excluded.observed_at, confidence=excluded.confidence,
                     attributes_cipher=excluded.attributes_cipher, key_id=excluded.key_id""",
                (
                    relationship.tenant_id,
                    relationship.relationship_id,
                    relationship.source_type.value,
                    relationship.source_id,
                    relationship.target_type.value,
                    relationship.target_id,
                    relationship.relationship_type,
                    _utc(relationship.observed_at),
                    relationship.confidence,
                    self._encrypt(relationship.attributes, context),
                    self.cipher.key_id,
                ),
            )

    def get_relationship(self, tenant_id: str, relationship_id: str) -> Relationship | None:
        row = self.connection.execute(
            "SELECT * FROM relationships WHERE tenant_id = ? AND relationship_id = ?",
            (tenant_id, relationship_id),
        ).fetchone()
        if row is None:
            return None
        return Relationship(
            tenant_id=tenant_id,
            relationship_id=relationship_id,
            source_type=EntityType(row["source_type"]),
            source_id=row["source_id"],
            target_type=EntityType(row["target_type"]),
            target_id=row["target_id"],
            relationship_type=row["relationship_type"],
            observed_at=_parse_time(row["observed_at"]),
            confidence=row["confidence"],
            attributes=self._decrypt(
                row["attributes_cipher"],
                f"relationship:{tenant_id}:{relationship_id}",
            ),
        )

    def put_alert(self, alert: Alert) -> None:
        prefix = f"alert:{alert.tenant_id}:{alert.alert_id}"
        with self._transaction() as connection:
            connection.execute(
                """INSERT INTO alerts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(tenant_id, alert_id) DO UPDATE SET
                     title_cipher=excluded.title_cipher, severity=excluded.severity,
                     status=excluded.status, finding_ids_json=excluded.finding_ids_json,
                     attributes_cipher=excluded.attributes_cipher, key_id=excluded.key_id""",
                (
                    alert.tenant_id,
                    alert.alert_id,
                    alert.subject_type.value,
                    alert.subject_id,
                    self._encrypt({"title": alert.title}, prefix + ":title"),
                    alert.severity.value,
                    alert.status.value,
                    _canonical(alert.finding_ids),
                    self._encrypt(alert.attributes, prefix + ":attributes"),
                    self.cipher.key_id,
                    _utc(alert.created_at),
                ),
            )

    def get_alert(self, tenant_id: str, alert_id: str) -> Alert | None:
        row = self.connection.execute(
            "SELECT * FROM alerts WHERE tenant_id = ? AND alert_id = ?",
            (tenant_id, alert_id),
        ).fetchone()
        if row is None:
            return None
        prefix = f"alert:{tenant_id}:{alert_id}"
        title = self._decrypt(row["title_cipher"], prefix + ":title")["title"]
        return Alert(
            tenant_id=tenant_id,
            alert_id=alert_id,
            subject_type=EntityType(row["subject_type"]),
            subject_id=row["subject_id"],
            title=title,
            severity=Severity(row["severity"]),
            status=AlertStatus(row["status"]),
            finding_ids=tuple(json.loads(row["finding_ids_json"])),
            attributes=self._decrypt(row["attributes_cipher"], prefix + ":attributes"),
            created_at=_parse_time(row["created_at"]),
        )

    def put_case(self, case: InvestigationCase) -> None:
        prefix = f"case:{case.tenant_id}:{case.case_id}"
        with self._transaction() as connection:
            connection.execute(
                """INSERT INTO investigation_cases VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(tenant_id, case_id) DO UPDATE SET
                     status=excluded.status, title_cipher=excluded.title_cipher,
                     assignee_cipher=excluded.assignee_cipher,
                     alert_ids_json=excluded.alert_ids_json, packs_json=excluded.packs_json,
                     attributes_cipher=excluded.attributes_cipher, key_id=excluded.key_id,
                     updated_at=excluded.updated_at""",
                (
                    case.tenant_id,
                    case.case_id,
                    case.status.value,
                    self._encrypt({"title": case.title}, prefix + ":title"),
                    self._encrypt({"assignee": case.assignee}, prefix + ":assignee"),
                    _canonical(case.alert_ids),
                    _canonical(case.jurisdiction_packs),
                    self._encrypt(case.attributes, prefix + ":attributes"),
                    self.cipher.key_id,
                    _utc(case.created_at),
                    _utc(case.updated_at),
                ),
            )

    def get_case(self, tenant_id: str, case_id: str) -> InvestigationCase | None:
        row = self.connection.execute(
            "SELECT * FROM investigation_cases WHERE tenant_id = ? AND case_id = ?",
            (tenant_id, case_id),
        ).fetchone()
        if row is None:
            return None
        prefix = f"case:{tenant_id}:{case_id}"
        title = self._decrypt(row["title_cipher"], prefix + ":title")["title"]
        assignee = self._decrypt(row["assignee_cipher"], prefix + ":assignee")["assignee"]
        return InvestigationCase(
            tenant_id=tenant_id,
            case_id=case_id,
            title=title,
            status=CaseStatus(row["status"]),
            created_at=_parse_time(row["created_at"]),
            updated_at=_parse_time(row["updated_at"]),
            alert_ids=tuple(json.loads(row["alert_ids_json"])),
            assignee=assignee,
            jurisdiction_packs=tuple(json.loads(row["packs_json"])),
            attributes=self._decrypt(row["attributes_cipher"], prefix + ":attributes"),
        )

    @staticmethod
    def _audit_hash(body: dict[str, Any]) -> str:
        return sha256(_canonical(body).encode()).hexdigest()

    def append_audit(
        self, tenant_id: str, event_type: str, actor: str, payload: dict[str, Any]
    ) -> str:
        occurred_at = self.clock()
        payload_digest = sha256(_canonical(payload).encode()).hexdigest()
        with self._transaction() as connection:
            previous = connection.execute(
                """SELECT sequence, event_hash FROM audit_events
                   WHERE tenant_id = ? ORDER BY sequence DESC LIMIT 1""",
                (tenant_id,),
            ).fetchone()
            sequence = 1 if previous is None else previous["sequence"] + 1
            previous_hash = "GENESIS" if previous is None else previous["event_hash"]
            body = {
                "tenant_id": tenant_id,
                "sequence": sequence,
                "event_type": event_type,
                "actor": actor,
                "occurred_at": _utc(occurred_at),
                "payload_digest": payload_digest,
                "previous_hash": previous_hash,
            }
            event_hash = self._audit_hash(body)
            connection.execute(
                "INSERT INTO audit_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    tenant_id,
                    sequence,
                    event_type,
                    actor,
                    body["occurred_at"],
                    self._encrypt(payload, f"audit:{tenant_id}:{sequence}"),
                    payload_digest,
                    self.cipher.key_id,
                    previous_hash,
                    event_hash,
                ),
            )
        return event_hash

    def verify_audit(self, tenant_id: str) -> bool:
        rows = self.connection.execute(
            "SELECT * FROM audit_events WHERE tenant_id = ? ORDER BY sequence", (tenant_id,)
        ).fetchall()
        previous_hash = "GENESIS"
        for expected, row in enumerate(rows, 1):
            payload = self._decrypt(row["payload_cipher"], f"audit:{tenant_id}:{row['sequence']}")
            digest = sha256(_canonical(payload).encode()).hexdigest()
            body = {
                "tenant_id": tenant_id,
                "sequence": row["sequence"],
                "event_type": row["event_type"],
                "actor": row["actor"],
                "occurred_at": row["occurred_at"],
                "payload_digest": row["payload_digest"],
                "previous_hash": row["previous_hash"],
            }
            if (
                row["sequence"] != expected
                or row["previous_hash"] != previous_hash
                or digest != row["payload_digest"]
                or self._audit_hash(body) != row["event_hash"]
            ):
                return False
            previous_hash = row["event_hash"]
        return True

    def record_llm_run(
        self,
        *,
        tenant_id: str,
        run_id: str,
        provider: str,
        model: str,
        provider_kind: str,
        classification: DataClassification,
        purpose: str,
        request_hash: str,
        response_hash: str | None,
        evidence_ids: tuple[str, ...],
        status: str,
        error_code: str | None = None,
    ) -> None:
        with self._transaction() as connection:
            connection.execute(
                "INSERT INTO llm_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    tenant_id,
                    run_id,
                    provider,
                    model,
                    provider_kind,
                    classification.value,
                    purpose,
                    request_hash,
                    response_hash,
                    _canonical(evidence_ids),
                    status,
                    error_code,
                    _utc(self.clock()),
                ),
            )

    def list_llm_runs(self, tenant_id: str) -> tuple[dict[str, Any], ...]:
        rows = self.connection.execute(
            """SELECT * FROM llm_runs WHERE tenant_id = ?
               ORDER BY created_at, run_id""",
            (tenant_id,),
        ).fetchall()
        return tuple(
            {
                **dict(row),
                "evidence_ids": tuple(json.loads(row["evidence_ids_json"])),
            }
            for row in rows
        )

