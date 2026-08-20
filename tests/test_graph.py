from datetime import datetime, timezone
from decimal import Decimal
from unittest import TestCase

from traceaml.domain import Transaction
from traceaml.graph import TransactionGraph


def tx(identifier: str, source: str, target: str) -> Transaction:
    return Transaction(
        transaction_id=identifier,
        occurred_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        amount=Decimal("1"),
        currency="USD",
        originator_account=source,
        beneficiary_account=target,
        originator_country="US",
        beneficiary_country="US",
    )


class GraphTests(TestCase):
    def test_bounded_bidirectional_neighborhood(self) -> None:
        graph = TransactionGraph()
        graph.add(tx("1", "a", "b"))
        graph.add(tx("2", "b", "c"))
        graph.add(tx("3", "c", "d"))
        self.assertEqual(graph.neighbors("a", max_depth=1), ("b",))
        self.assertEqual(graph.neighbors("a", max_depth=2), ("b", "c"))


