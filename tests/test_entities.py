from datetime import UTC, datetime
from unittest import TestCase

from traceaml.entities import EntityType, Relationship


class EntityTests(TestCase):
    def test_relationship_confidence_is_bounded(self) -> None:
        with self.assertRaisesRegex(ValueError, "confidence"):
            Relationship(
                tenant_id="tenant",
                relationship_id="rel",
                source_type=EntityType.PARTY,
                source_id="party",
                target_type=EntityType.ACCOUNT,
                target_id="account",
                relationship_type="owns",
                observed_at=datetime.now(UTC),
                confidence=1.1,
            )
