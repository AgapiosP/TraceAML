"""Evidence-first deterministic investigation reporting."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from hashlib import sha256

from .domain import Claim, Evidence, Finding, InvestigationReport
from .packs import JurisdictionPack


class EvidenceIntegrityError(ValueError):
    pass


class InvestigationBuilder:
    def build(
        self,
        subject_account: str,
        findings: Iterable[Finding],
        related_accounts: tuple[str, ...],
        pack: JurisdictionPack,
        created_at: datetime | None = None,
    ) -> InvestigationReport:
        created_at = created_at or datetime.now(UTC)
        finding_list = tuple(findings)
        evidence = tuple(item for finding in finding_list for item in finding.evidence)
        claims = tuple(
            Claim(
                text=(
                    f"{finding.title} (rule {finding.rule_id} "
                    f"v{finding.rule_version}, severity {finding.severity.value})."
                ),
                evidence_ids=tuple(item.evidence_id for item in finding.evidence),
            )
            for finding in finding_list
        )
        self.validate_claims(claims, evidence)
        identity = "|".join(
            [subject_account, pack.pack_id, pack.version]
            + sorted(item.evidence_id for item in evidence)
        )
        report_id = f"report_{sha256(identity.encode()).hexdigest()[:16]}"
        return InvestigationReport(
            report_id=report_id,
            subject_account=subject_account,
            created_at=created_at,
            pack_id=pack.pack_id,
            pack_version=pack.version,
            claims=claims,
            evidence=evidence,
            related_accounts=related_accounts,
            limitations=(
                "Findings are indicators for human review, not a determination of suspicion.",
                "The report uses only the transactions and rules supplied to this run.",
                pack.disclaimer,
            ),
        )

    @staticmethod
    def validate_claims(claims: Iterable[Claim], evidence: Iterable[Evidence]) -> None:
        available = {item.evidence_id for item in evidence}
        for claim in claims:
            if not claim.evidence_ids:
                raise EvidenceIntegrityError("every claim must cite evidence")
            if missing := set(claim.evidence_ids).difference(available):
                raise EvidenceIntegrityError(f"claim cites missing evidence: {sorted(missing)}")
