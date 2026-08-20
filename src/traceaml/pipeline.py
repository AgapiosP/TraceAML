"""Application service for the v0.1 investigation workflow."""

from __future__ import annotations

from datetime import datetime

from .audit import AuditLog
from .domain import Finding, InvestigationReport, Transaction
from .graph import TransactionGraph
from .investigation import InvestigationBuilder
from .packs import load_pack
from .rules import CrossBorderRule, HighValueRule, RuleEngine


class TraceAMLEngine:
    def __init__(self) -> None:
        self.graph = TransactionGraph()
        self.audit = AuditLog()
        self.rules = RuleEngine((HighValueRule(), CrossBorderRule()))
        self._findings_by_account: dict[str, list[Finding]] = {}
        self._transaction_ids: set[str] = set()

    def ingest(self, transaction: Transaction, actor: str = "system") -> tuple[Finding, ...]:
        if transaction.transaction_id in self._transaction_ids:
            raise ValueError(f"duplicate transaction_id: {transaction.transaction_id}")
        self._transaction_ids.add(transaction.transaction_id)
        self.graph.add(transaction)
        findings = self.rules.evaluate(transaction)
        for account in {transaction.originator_account, transaction.beneficiary_account}:
            self._findings_by_account.setdefault(account, []).extend(findings)
        self.audit.append(
            "transaction.ingested",
            actor,
            {"transaction_id": transaction.transaction_id},
        )
        for finding in findings:
            self.audit.append(
                "finding.created",
                actor,
                {
                    "finding_id": finding.finding_id,
                    "rule_id": finding.rule_id,
                    "rule_version": finding.rule_version,
                },
            )
        return findings

    def investigate(
        self,
        subject_account: str,
        pack_id: str,
        actor: str = "investigator",
        created_at: datetime | None = None,
    ) -> InvestigationReport:
        pack = load_pack(pack_id)
        report = InvestigationBuilder().build(
            subject_account=subject_account,
            findings=self._findings_by_account.get(subject_account, ()),
            related_accounts=self.graph.neighbors(subject_account, max_depth=2),
            pack=pack,
            created_at=created_at,
        )
        self.audit.append(
            "investigation.generated",
            actor,
            {
                "report_id": report.report_id,
                "subject_account": subject_account,
                "pack_id": report.pack_id,
                "pack_version": report.pack_version,
            },
        )
        return report


