"""Immutable domain records and validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True, slots=True)
class Transaction:
    transaction_id: str
    occurred_at: datetime
    amount: Decimal
    currency: str
    originator_account: str
    beneficiary_account: str
    originator_country: str
    beneficiary_country: str
    attributes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.transaction_id.strip():
            raise ValueError("transaction_id is required")
        if self.amount <= 0:
            raise ValueError("amount must be positive")
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("occurred_at must be timezone-aware")
        if len(self.currency) != 3 or not self.currency.isalpha():
            raise ValueError("currency must be a three-letter code")
        for name in ("originator_account", "beneficiary_account"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} is required")
        for name in ("originator_country", "beneficiary_country"):
            value = getattr(self, name)
            if len(value) != 2 or not value.isalpha():
                raise ValueError(f"{name} must be a two-letter country code")
        object.__setattr__(self, "currency", self.currency.upper())
        object.__setattr__(self, "originator_country", self.originator_country.upper())
        object.__setattr__(self, "beneficiary_country", self.beneficiary_country.upper())

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Transaction:
        try:
            occurred_at = datetime.fromisoformat(str(value["occurred_at"]).replace("Z", "+00:00"))
            amount = Decimal(str(value["amount"]))
        except (KeyError, ValueError, InvalidOperation) as exc:
            raise ValueError(f"invalid transaction: {exc}") from exc
        return cls(
            transaction_id=str(value["transaction_id"]),
            occurred_at=occurred_at,
            amount=amount,
            currency=str(value["currency"]),
            originator_account=str(value["originator_account"]),
            beneficiary_account=str(value["beneficiary_account"]),
            originator_country=str(value["originator_country"]),
            beneficiary_country=str(value["beneficiary_country"]),
            attributes=dict(value.get("attributes", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["occurred_at"] = self.occurred_at.astimezone(timezone.utc).isoformat()
        result["amount"] = str(self.amount)
        return result


@dataclass(frozen=True, slots=True)
class Evidence:
    evidence_id: str
    kind: str
    source_id: str
    observed_at: datetime
    facts: dict[str, Any]


@dataclass(frozen=True, slots=True)
class Finding:
    finding_id: str
    rule_id: str
    rule_version: str
    title: str
    severity: Severity
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True, slots=True)
class Claim:
    text: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class InvestigationReport:
    report_id: str
    subject_account: str
    created_at: datetime
    pack_id: str
    pack_version: str
    claims: tuple[Claim, ...]
    evidence: tuple[Evidence, ...]
    related_accounts: tuple[str, ...]
    limitations: tuple[str, ...]

