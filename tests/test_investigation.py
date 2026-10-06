from datetime import UTC, datetime
from unittest import TestCase

from traceaml.domain import Claim, Evidence
from traceaml.investigation import EvidenceIntegrityError, InvestigationBuilder


class InvestigationTests(TestCase):
    def test_rejects_claim_with_unknown_evidence(self) -> None:
        evidence = Evidence("known", "test", "tx", datetime.now(UTC), {})
        with self.assertRaises(EvidenceIntegrityError):
            InvestigationBuilder.validate_claims((Claim("claim", ("missing",)),), (evidence,))

