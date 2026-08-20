from datetime import datetime, timezone
from unittest import TestCase

from traceaml.audit import AuditLog


class AuditTests(TestCase):
    def test_events_form_a_valid_hash_chain(self) -> None:
        moment = datetime(2026, 1, 1, tzinfo=timezone.utc)
        audit = AuditLog(clock=lambda: moment)
        first = audit.append("one", "tester", {"value": 1})
        second = audit.append("two", "tester", {"value": 2})
        self.assertEqual(second.previous_hash, first.event_hash)
        self.assertTrue(audit.verify())

