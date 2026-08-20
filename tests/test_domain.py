from datetime import datetime, timezone
from decimal import Decimal
from unittest import TestCase

from traceaml.domain import Transaction


class TransactionTests(TestCase):
    def test_normalizes_codes(self) -> None:
        transaction = Transaction(
            transaction_id="tx-1",
            occurred_at=datetime.now(timezone.utc),
            amount=Decimal("1.00"),
            currency="eur",
            originator_account="a",
            beneficiary_account="b",
            originator_country="de",
            beneficiary_country="gb",
        )
        self.assertEqual(transaction.currency, "EUR")
        self.assertEqual(transaction.originator_country, "DE")

    def test_rejects_naive_timestamp(self) -> None:
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            Transaction(
                transaction_id="tx-1",
                occurred_at=datetime(2026, 1, 1),
                amount=Decimal("1.00"),
                currency="EUR",
                originator_account="a",
                beneficiary_account="b",
                originator_country="DE",
                beneficiary_country="GB",
            )

