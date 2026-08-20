"""Tamper-evident append-only audit events."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class AuditEvent:
    sequence: int
    event_type: str
    actor: str
    occurred_at: datetime
    payload: dict[str, Any]
    previous_hash: str
    event_hash: str


class AuditLog:
    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        self._events: list[AuditEvent] = []
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    @staticmethod
    def _hash(body: dict[str, Any]) -> str:
        canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
        return sha256(canonical.encode()).hexdigest()

    def append(self, event_type: str, actor: str, payload: dict[str, Any]) -> AuditEvent:
        sequence = len(self._events) + 1
        previous_hash = self._events[-1].event_hash if self._events else "GENESIS"
        occurred_at = self._clock()
        body = {
            "sequence": sequence,
            "event_type": event_type,
            "actor": actor,
            "occurred_at": occurred_at.isoformat(),
            "payload": payload,
            "previous_hash": previous_hash,
        }
        event = AuditEvent(
            sequence=sequence,
            event_type=event_type,
            actor=actor,
            occurred_at=occurred_at,
            payload=payload,
            previous_hash=previous_hash,
            event_hash=self._hash(body),
        )
        self._events.append(event)
        return event

    @property
    def events(self) -> tuple[AuditEvent, ...]:
        return tuple(self._events)

    def verify(self) -> bool:
        previous_hash = "GENESIS"
        for event in self._events:
            body = asdict(event)
            event_hash = body.pop("event_hash")
            body["occurred_at"] = event.occurred_at.isoformat()
            if event.previous_hash != previous_hash or self._hash(body) != event_hash:
                return False
            previous_hash = event.event_hash
        return True

