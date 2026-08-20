"""Synthetic, engine-backed customer demonstration server."""

from __future__ import annotations

import json
import threading
import webbrowser
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from typing import Any
from urllib.parse import parse_qs, urlsplit

from .domain import Finding, Transaction
from .entities import DataClassification
from .llm import LLMPolicy, LLMPolicyError, LLMRequest, ProviderKind
from .packs import load_pack
from .pipeline import TraceAMLEngine

DEMO_CREATED_AT = datetime(2026, 8, 20, 9, 30, tzinfo=UTC)
SUPPORTED_PACKS = ("eu", "uk", "us", "au")


@dataclass(frozen=True, slots=True)
class DemoScenario:
    case_id: str
    alert_id: str
    customer_name: str
    subject_account: str
    segment: str
    owner: str
    opened_at: str
    transactions: tuple[Transaction, ...]


def _transaction(
    transaction_id: str,
    occurred_at: str,
    amount: str,
    currency: str,
    originator_account: str,
    beneficiary_account: str,
    originator_country: str,
    beneficiary_country: str,
    channel: str,
) -> Transaction:
    return Transaction(
        transaction_id=transaction_id,
        occurred_at=datetime.fromisoformat(occurred_at.replace("Z", "+00:00")),
        amount=Decimal(amount),
        currency=currency,
        originator_account=originator_account,
        beneficiary_account=beneficiary_account,
        originator_country=originator_country,
        beneficiary_country=beneficiary_country,
        attributes={"channel": channel, "fixture": "synthetic-customer-demo"},
    )


SCENARIOS = (
    DemoScenario(
        case_id="case-northstar",
        alert_id="ALT-2048",
        customer_name="Northstar Imports Ltd",
        subject_account="ACCT-NORTHSTAR-01",
        segment="SME · Import / export",
        owner="Maya Chen",
        opened_at="20 Aug 2026, 09:30 UTC",
        transactions=(
            _transaction(
                "TX-78421",
                "2026-08-18T08:42:00Z",
                "18750.00",
                "EUR",
                "ACCT-NORTHSTAR-01",
                "ACCT-HARBOR-22",
                "DE",
                "GB",
                "wire",
            ),
            _transaction(
                "TX-78453",
                "2026-08-18T11:16:00Z",
                "4900.00",
                "EUR",
                "ACCT-HARBOR-22",
                "ACCT-WILLOW-08",
                "GB",
                "GB",
                "instant transfer",
            ),
            _transaction(
                "TX-78604",
                "2026-08-19T15:07:00Z",
                "9850.00",
                "EUR",
                "ACCT-NORTHSTAR-01",
                "ACCT-CANAL-41",
                "DE",
                "NL",
                "wire",
            ),
        ),
    ),
    DemoScenario(
        case_id="case-orion",
        alert_id="ALT-2056",
        customer_name="Orion Digital Services",
        subject_account="ACCT-ORION-14",
        segment="Corporate · Technology",
        owner="Leo Martin",
        opened_at="20 Aug 2026, 08:55 UTC",
        transactions=(
            _transaction(
                "TX-79011",
                "2026-08-17T06:20:00Z",
                "24000.00",
                "USD",
                "ACCT-ORION-14",
                "ACCT-MERIDIAN-06",
                "US",
                "SG",
                "wire",
            ),
            _transaction(
                "TX-79044",
                "2026-08-17T07:02:00Z",
                "15200.00",
                "USD",
                "ACCT-MERIDIAN-06",
                "ACCT-SOUTHERN-19",
                "SG",
                "AU",
                "wire",
            ),
        ),
    ),
    DemoScenario(
        case_id="case-ember",
        alert_id="ALT-2071",
        customer_name="Ember Studio Collective",
        subject_account="ACCT-EMBER-05",
        segment="SME · Creative services",
        owner="Unassigned",
        opened_at="19 Aug 2026, 16:10 UTC",
        transactions=(
            _transaction(
                "TX-79308",
                "2026-08-19T14:38:00Z",
                "7200.00",
                "GBP",
                "ACCT-EMBER-05",
                "ACCT-BIRCH-31",
                "GB",
                "IE",
                "online banking",
            ),
            _transaction(
                "TX-79344",
                "2026-08-19T15:04:00Z",
                "1300.00",
                "GBP",
                "ACCT-EMBER-05",
                "ACCT-LANTERN-17",
                "GB",
                "GB",
                "instant transfer",
            ),
        ),
    ),
)


def _scenario(case_id: str) -> DemoScenario:
    return next((item for item in SCENARIOS if item.case_id == case_id), SCENARIOS[0])


def _risk(findings: tuple[Finding, ...]) -> tuple[int, str]:
    score = min(
        96,
        38 + sum(18 if finding.severity.value == "high" else 9 for finding in findings),
    )
    label = "High" if score >= 70 else "Medium" if score >= 45 else "Low"
    return score, label


def _money(transaction: Transaction) -> str:
    return f"{transaction.currency} {transaction.amount:,.2f}"


def build_demo_snapshot(pack_id: str = "eu", case_id: str = "case-northstar") -> dict[str, Any]:
    """Build a reproducible customer-demo view from the real rules and graph engine."""
    if pack_id not in SUPPORTED_PACKS:
        raise ValueError(f"unsupported jurisdiction pack: {pack_id}")
    scenario = _scenario(case_id)
    engine = TraceAMLEngine()
    findings: list[Finding] = []
    for transaction in scenario.transactions:
        findings.extend(engine.ingest(transaction, actor="demo-ingestion"))
    report = engine.investigate(
        scenario.subject_account,
        pack_id,
        actor="demo-investigator",
        created_at=DEMO_CREATED_AT,
    )
    pack = load_pack(pack_id)
    relevant_findings = tuple(
        finding
        for finding in findings
        if any(
            evidence.source_id in {item.transaction_id for item in scenario.transactions}
            for evidence in finding.evidence
        )
    )
    score, risk_label = _risk(relevant_findings)
    evidence_ids = {evidence.evidence_id for evidence in report.evidence}
    citations_valid = all(set(claim.evidence_ids).issubset(evidence_ids) for claim in report.claims)
    accounts = sorted(
        {
            account
            for transaction in scenario.transactions
            for account in (transaction.originator_account, transaction.beneficiary_account)
        }
    )
    graph_nodes = [
        {
            "id": account,
            "label": "Subject"
            if account == scenario.subject_account
            else account.removeprefix("ACCT-").split("-")[0].title(),
            "kind": "subject" if account == scenario.subject_account else "related",
        }
        for account in accounts
    ]
    graph_edges = [
        {
            "id": transaction.transaction_id,
            "source": transaction.originator_account,
            "target": transaction.beneficiary_account,
            "label": _money(transaction),
        }
        for transaction in scenario.transactions
    ]
    alerts = []
    for item in SCENARIOS:
        item_engine = TraceAMLEngine()
        item_findings = tuple(
            finding
            for transaction in item.transactions
            for finding in item_engine.ingest(transaction, actor="demo-ingestion")
        )
        item_score, item_label = _risk(item_findings)
        alerts.append(
            {
                "case_id": item.case_id,
                "alert_id": item.alert_id,
                "customer": item.customer_name,
                "subject_account": item.subject_account,
                "risk_score": item_score,
                "risk_label": item_label,
                "indicator_count": len(item_findings),
                "selected": item.case_id == scenario.case_id,
            }
        )
    return {
        "product": {
            "name": "TraceAML",
            "environment": "Customer demonstration",
            "data_mode": "Synthetic data only",
            "version": "0.2.0-dev",
        },
        "metrics": {
            "open_alerts": len(SCENARIOS),
            "evidence_coverage": 100 if citations_valid else 0,
            "audit_integrity": "Verified" if engine.audit.verify() else "Failed",
            "review_time": "4m 12s",
        },
        "alerts": alerts,
        "case": {
            "case_id": scenario.case_id,
            "alert_id": scenario.alert_id,
            "customer": scenario.customer_name,
            "subject_account": scenario.subject_account,
            "segment": scenario.segment,
            "owner": scenario.owner,
            "opened_at": scenario.opened_at,
            "status": "In review",
            "risk_score": score,
            "risk_label": risk_label,
            "report_id": report.report_id,
            "summary": (
                f"TraceAML identified {len(report.claims)} explainable indicator"
                f"{'s' if len(report.claims) != 1 else ''} across "
                f"{len(scenario.transactions)} synthetic transactions. "
                f"Every statement below is linked to source evidence for human review."
            ),
            "claims": [asdict(claim) for claim in report.claims],
            "limitations": list(report.limitations),
        },
        "evidence": [
            {
                "evidence_id": evidence.evidence_id,
                "kind": evidence.kind,
                "source_id": evidence.source_id,
                "observed_at": evidence.observed_at.astimezone(UTC).isoformat(),
                "facts": evidence.facts,
            }
            for evidence in report.evidence
        ],
        "transactions": [
            {
                **transaction.to_dict(),
                "display_amount": _money(transaction),
                "channel": transaction.attributes["channel"],
            }
            for transaction in scenario.transactions
        ],
        "graph": {"nodes": graph_nodes, "edges": graph_edges},
        "regulatory": {
            "pack_id": pack.pack_id,
            "name": pack.name,
            "version": pack.version,
            "reviewed_on": pack.reviewed_on,
            "authorities": list(pack.authorities),
            "review_topics": list(pack.review_topics),
            "sources": list(pack.sources),
            "disclaimer": pack.disclaimer,
        },
        "llm": {
            "default_provider": "local",
            "default_classification": "restricted",
            "local_status": "Available for policy evaluation",
            "online_status": "Blocked for restricted data",
            "notice": "This demo evaluates routing policy but does not contact an LLM.",
        },
        "audit": {
            "valid": engine.audit.verify(),
            "events": [
                {
                    "sequence": event.sequence,
                    "event_type": event.event_type,
                    "actor": event.actor,
                    "occurred_at": event.occurred_at.astimezone(UTC).isoformat(),
                    "hash": event.event_hash[:12],
                }
                for event in engine.audit.events
            ],
        },
        "safety": {
            "synthetic": True,
            "autonomous_decision": False,
            "filing_recommendation": False,
        },
    }


@dataclass(frozen=True, slots=True)
class _PolicyProvider:
    name: str
    kind: ProviderKind
    model: str = "demo-policy-check"

    def generate(self, request: LLMRequest) -> Any:  # pragma: no cover - policy only
        raise RuntimeError("the customer demo never invokes an LLM provider")


def evaluate_demo_policy(provider: str, classification: str) -> dict[str, Any]:
    kind = ProviderKind(provider)
    data_classification = DataClassification(classification)
    request = LLMRequest(
        tenant_id="synthetic-demo",
        purpose="draft evidence-grounded investigation summary",
        classification=data_classification,
        system_instruction="Use only cited evidence.",
        user_content="Synthetic policy evaluation only.",
        evidence_ids=(),
    )
    target = _PolicyProvider(f"demo-{kind.value}", kind)
    try:
        LLMPolicy().authorize(target, request)
    except LLMPolicyError as exc:
        return {
            "allowed": False,
            "provider": kind.value,
            "classification": data_classification.value,
            "reason": str(exc),
            "provider_called": False,
        }
    return {
        "allowed": True,
        "provider": kind.value,
        "classification": data_classification.value,
        "reason": "Policy permits this route. No provider was contacted in the demo.",
        "provider_called": False,
    }


class DemoRequestHandler(BaseHTTPRequestHandler):
    """Read-only HTTP surface for the synthetic customer demonstration."""

    server_version = "TraceAML-Demo"

    def _headers(self, content_type: str, length: int) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; font-src 'self'; "
            "object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
        )
        self.end_headers()

    def _json(self, value: dict[str, Any]) -> None:
        payload = json.dumps(value, separators=(",", ":"), default=str).encode()
        self._headers("application/json; charset=utf-8", len(payload))
        self.wfile.write(payload)

    def _asset(self, name: str, content_type: str) -> None:
        payload = files("traceaml").joinpath("web", name).read_bytes()
        self._headers(content_type, len(payload))
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        parsed = urlsplit(self.path)
        query = parse_qs(parsed.query)
        try:
            if parsed.path == "/":
                self._asset("index.html", "text/html; charset=utf-8")
            elif parsed.path == "/app.css":
                self._asset("app.css", "text/css; charset=utf-8")
            elif parsed.path == "/app.js":
                self._asset("app.js", "text/javascript; charset=utf-8")
            elif parsed.path == "/healthz":
                self._json({"status": "ok", "mode": "synthetic-demo"})
            elif parsed.path == "/api/demo":
                self._json(
                    build_demo_snapshot(
                        query.get("pack", ["eu"])[0],
                        query.get("case", ["case-northstar"])[0],
                    )
                )
            elif parsed.path == "/api/policy":
                self._json(
                    evaluate_demo_policy(
                        query.get("provider", ["local"])[0],
                        query.get("classification", ["restricted"])[0],
                    )
                )
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        except (ValueError, KeyError) as exc:
            payload = json.dumps({"error": str(exc)}).encode()
            self.send_response(HTTPStatus.BAD_REQUEST)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    def log_message(self, format: str, *args: Any) -> None:
        return


def create_demo_server(host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("the customer demo binds to loopback only")
    return ThreadingHTTPServer((host, port), DemoRequestHandler)


def run_demo_server(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True) -> None:
    with create_demo_server(host, port) as server:
        url = f"http://{host}:{server.server_address[1]}"
        print(f"TraceAML customer demo: {url}")
        print("Synthetic data only. Press Ctrl+C to stop.")
        if open_browser:
            threading.Timer(0.35, webbrowser.open, args=(url,)).start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
