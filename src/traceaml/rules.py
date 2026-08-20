"""Deterministic detection rules that emit structured evidence."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
from typing import Protocol

from .domain import Evidence, Finding, Severity, Transaction


def _stable_id(prefix: str, *parts: str) -> str:
    digest = sha256("|".join(parts).encode()).hexdigest()[:16]
    return f"{prefix}_{digest}"


class TransactionRule(Protocol):
    rule_id: str
    version: str

    def evaluate(self, transaction: Transaction) -> Finding | None: ...


@dataclass(frozen=True, slots=True)
class HighValueRule:
    threshold: Decimal = Decimal("10000")
    rule_id: str = "high_value_transaction"
    version: str = "1.0.0"

    def evaluate(self, transaction: Transaction) -> Finding | None:
        if transaction.amount < self.threshold:
            return None
        evidence = Evidence(
            evidence_id=_stable_id("ev", self.rule_id, transaction.transaction_id),
            kind="rule_observation",
            source_id=transaction.transaction_id,
            observed_at=transaction.occurred_at,
            facts={
                "amount": str(transaction.amount),
                "currency": transaction.currency,
                "operator": ">=",
                "threshold": str(self.threshold),
            },
        )
        return Finding(
            finding_id=_stable_id("finding", self.rule_id, transaction.transaction_id),
            rule_id=self.rule_id,
            rule_version=self.version,
            title="Transaction meets the configured high-value threshold",
            severity=Severity.HIGH,
            evidence=(evidence,),
        )


@dataclass(frozen=True, slots=True)
class CrossBorderRule:
    rule_id: str = "cross_border_transaction"
    version: str = "1.0.0"

    def evaluate(self, transaction: Transaction) -> Finding | None:
        if transaction.originator_country == transaction.beneficiary_country:
            return None
        evidence = Evidence(
            evidence_id=_stable_id("ev", self.rule_id, transaction.transaction_id),
            kind="rule_observation",
            source_id=transaction.transaction_id,
            observed_at=transaction.occurred_at,
            facts={
                "originator_country": transaction.originator_country,
                "beneficiary_country": transaction.beneficiary_country,
            },
        )
        return Finding(
            finding_id=_stable_id("finding", self.rule_id, transaction.transaction_id),
            rule_id=self.rule_id,
            rule_version=self.version,
            title="Transaction crosses national borders",
            severity=Severity.MEDIUM,
            evidence=(evidence,),
        )


class RuleEngine:
    def __init__(self, rules: tuple[TransactionRule, ...]) -> None:
        self._rules = rules

    def evaluate(self, transaction: Transaction) -> tuple[Finding, ...]:
        return tuple(
            finding
            for rule in self._rules
            if (finding := rule.evaluate(transaction)) is not None
        )

