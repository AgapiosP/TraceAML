from datetime import UTC, datetime
from decimal import Decimal
from unittest import TestCase

from traceaml.domain import Severity, Transaction
from traceaml.rules import CrossBorderRule, HighValueRule


def transaction(amount: str = "100", destination: str = "DE") -> Transaction:
    return Transaction(
        transaction_id="tx-1",
        occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
        amount=Decimal(amount),
        currency="EUR",
        originator_account="a",
        beneficiary_account="b",
        originator_country="DE",
        beneficiary_country=destination,
    )


class RuleTests(TestCase):
    def test_high_value_rule_emits_versioned_evidence(self) -> None:
        finding = HighValueRule().evaluate(transaction("10000"))
        self.assertIsNotNone(finding)
        assert finding is not None
        self.assertEqual(finding.severity, Severity.HIGH)
        self.assertEqual(finding.rule_version, "1.0.0")
        self.assertEqual(finding.evidence[0].facts["threshold"], "10000")

    def test_cross_border_rule_ignores_domestic_transfer(self) -> None:
        self.assertIsNone(CrossBorderRule().evaluate(transaction()))

