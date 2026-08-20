"""Tenant-scoped entity records for the durable investigation workspace."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from .domain import Severity


def _required(value: str, name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} is required")
    return normalized


def _countries(values: tuple[str, ...]) -> tuple[str, ...]:
    normalized = tuple(sorted({value.upper() for value in values}))
    if any(len(value) != 2 or not value.isalpha() for value in normalized):
        raise ValueError("countries must contain two-letter country codes")
    return normalized


class PartyKind(StrEnum):
    INDIVIDUAL = "individual"
    ORGANIZATION = "organization"
    UNKNOWN = "unknown"


class AccountStatus(StrEnum):
    ACTIVE = "active"
    DORMANT = "dormant"
    CLOSED = "closed"
    UNKNOWN = "unknown"


class EntityType(StrEnum):
    PARTY = "party"
    ACCOUNT = "account"
    TRANSACTION = "transaction"
    DEVICE = "device"
    ADDRESS = "address"
    CASE = "case"


class AlertStatus(StrEnum):
    OPEN = "open"
    TRIAGED = "triaged"
    ESCALATED = "escalated"
    CLOSED = "closed"


class CaseStatus(StrEnum):
    OPEN = "open"
    IN_REVIEW = "in_review"
    ESCALATED = "escalated"
    CLOSED = "closed"


class DataClassification(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


@dataclass(frozen=True, slots=True)
class Tenant:
    tenant_id: str
    name: str
    created_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "tenant_id", _required(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "name", _required(self.name, "name"))


@dataclass(frozen=True, slots=True)
class Party:
    tenant_id: str
    party_id: str
    kind: PartyKind
    display_name: str
    countries: tuple[str, ...]
    created_at: datetime
    external_refs: dict[str, str] = field(default_factory=dict)
    attributes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "tenant_id", _required(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "party_id", _required(self.party_id, "party_id"))
        object.__setattr__(self, "display_name", _required(self.display_name, "display_name"))
        object.__setattr__(self, "countries", _countries(self.countries))


@dataclass(frozen=True, slots=True)
class Account:
    tenant_id: str
    account_id: str
    party_id: str | None
    label: str
    currency: str
    status: AccountStatus
    created_at: datetime
    external_refs: dict[str, str] = field(default_factory=dict)
    attributes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "tenant_id", _required(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "account_id", _required(self.account_id, "account_id"))
        object.__setattr__(self, "label", _required(self.label, "label"))
        if self.party_id is not None:
            object.__setattr__(self, "party_id", _required(self.party_id, "party_id"))
        if len(self.currency) != 3 or not self.currency.isalpha():
            raise ValueError("currency must be a three-letter code")
        object.__setattr__(self, "currency", self.currency.upper())


@dataclass(frozen=True, slots=True)
class Relationship:
    tenant_id: str
    relationship_id: str
    source_type: EntityType
    source_id: str
    target_type: EntityType
    target_id: str
    relationship_type: str
    observed_at: datetime
    confidence: float = 1.0
    attributes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "tenant_id",
            "relationship_id",
            "source_id",
            "target_id",
            "relationship_type",
        ):
            object.__setattr__(self, name, _required(getattr(self, name), name))
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class Alert:
    tenant_id: str
    alert_id: str
    subject_type: EntityType
    subject_id: str
    title: str
    severity: Severity
    status: AlertStatus
    created_at: datetime
    finding_ids: tuple[str, ...] = ()
    attributes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("tenant_id", "alert_id", "subject_id", "title"):
            object.__setattr__(self, name, _required(getattr(self, name), name))


@dataclass(frozen=True, slots=True)
class InvestigationCase:
    tenant_id: str
    case_id: str
    title: str
    status: CaseStatus
    created_at: datetime
    updated_at: datetime
    alert_ids: tuple[str, ...] = ()
    assignee: str | None = None
    jurisdiction_packs: tuple[str, ...] = ()
    attributes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("tenant_id", "case_id", "title"):
            object.__setattr__(self, name, _required(getattr(self, name), name))
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot precede created_at")
