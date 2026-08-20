"""Small in-process relationship graph with bounded traversal."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from decimal import Decimal

from .domain import Transaction


@dataclass(frozen=True, slots=True)
class TransferEdge:
    transaction_id: str
    source: str
    target: str
    amount: Decimal
    currency: str


class TransactionGraph:
    def __init__(self) -> None:
        self._outgoing: dict[str, list[TransferEdge]] = defaultdict(list)
        self._incoming: dict[str, list[TransferEdge]] = defaultdict(list)

    def add(self, transaction: Transaction) -> None:
        edge = TransferEdge(
            transaction_id=transaction.transaction_id,
            source=transaction.originator_account,
            target=transaction.beneficiary_account,
            amount=transaction.amount,
            currency=transaction.currency,
        )
        self._outgoing[edge.source].append(edge)
        self._incoming[edge.target].append(edge)

    def neighbors(self, account: str, max_depth: int = 1) -> tuple[str, ...]:
        if max_depth < 0:
            raise ValueError("max_depth cannot be negative")
        seen = {account}
        queue = deque([(account, 0)])
        while queue:
            node, depth = queue.popleft()
            if depth == max_depth:
                continue
            adjacent = [edge.target for edge in self._outgoing[node]]
            adjacent.extend(edge.source for edge in self._incoming[node])
            for other in adjacent:
                if other not in seen:
                    seen.add(other)
                    queue.append((other, depth + 1))
        seen.remove(account)
        return tuple(sorted(seen))

    def edges_for(self, account: str) -> tuple[TransferEdge, ...]:
        edges = self._outgoing[account] + self._incoming[account]
        return tuple(sorted(edges, key=lambda edge: edge.transaction_id))
