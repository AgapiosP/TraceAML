from datetime import datetime, timezone
from unittest import TestCase

from traceaml.domain import Claim, Evidence
from traceaml.investigation import EvidenceIntegrityError, InvestigationBuilder


class InvestigationTests(TestCase):
    def test_rejects_claim_with_unknown_evidence(self) -> None:
        evidence = Evidence("known", "test", "tx", datetime.now(timezone.utc), {})
        with self.assertRaises(EvidenceIntegrityError):
            InvestigationBuilder.validate_claims((Claim("claim", ("missing",)),), (evidence,))

