from datetime import datetime, timezone
from decimal import Decimal
from unittest import TestCase

from traceaml.domain import Transaction
from traceaml.pipeline import TraceAMLEngine


class PipelineTests(TestCase):
    def test_end_to_end_report_is_grounded_and_audited(self) -> None:
        engine = TraceAMLEngine()
        engine.ingest(
            Transaction(
                transaction_id="synthetic-1",
                occurred_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                amount=Decimal("15000"),
                currency="USD",
                originator_account="a",
                beneficiary_account="b",
                originator_country="US",
                beneficiary_country="GB",
            )
        )
        report = engine.investigate(
            "a", "us", created_at=datetime(2026, 1, 2, tzinfo=timezone.utc)
        )
        self.assertEqual(len(report.claims), 2)
        evidence_ids = {item.evidence_id for item in report.evidence}
        self.assertTrue(all(set(claim.evidence_ids) <= evidence_ids for claim in report.claims))
        self.assertEqual(report.related_accounts, ("b",))
        self.assertTrue(engine.audit.verify())

    def test_duplicate_transaction_is_rejected(self) -> None:
        transaction = Transaction(
            transaction_id="duplicate",
            occurred_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            amount=Decimal("1"),
            currency="USD",
            originator_account="a",
            beneficiary_account="b",
            originator_country="US",
            beneficiary_country="US",
        )
        engine = TraceAMLEngine()
        engine.ingest(transaction)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            engine.ingest(transaction)


