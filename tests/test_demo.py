import json
import threading
import urllib.request
from unittest import TestCase

from traceaml.demo import (
    build_demo_snapshot,
    create_demo_server,
    evaluate_demo_policy,
)


class CustomerDemoTests(TestCase):
    def test_snapshot_is_grounded_synthetic_and_pack_aware(self) -> None:
        snapshot = build_demo_snapshot("uk", "case-northstar")

        self.assertTrue(snapshot["safety"]["synthetic"])
        self.assertEqual(snapshot["regulatory"]["pack_id"], "uk")
        self.assertTrue(snapshot["audit"]["valid"])
        self.assertEqual(snapshot["metrics"]["evidence_coverage"], 100)
        evidence_ids = {item["evidence_id"] for item in snapshot["evidence"]}
        self.assertTrue(
            all(
                set(claim["evidence_ids"]).issubset(evidence_ids)
                for claim in snapshot["case"]["claims"]
            )
        )

    def test_alert_selection_changes_the_engine_backed_case(self) -> None:
        snapshot = build_demo_snapshot("eu", "case-orion")

        self.assertEqual(snapshot["case"]["case_id"], "case-orion")
        self.assertEqual(snapshot["case"]["customer"], "Orion Digital Services")
        self.assertEqual(len(snapshot["transactions"]), 2)
        self.assertTrue(any(item["selected"] for item in snapshot["alerts"]))

    def test_online_restricted_is_denied_without_calling_a_provider(self) -> None:
        decision = evaluate_demo_policy("online", "restricted")

        self.assertFalse(decision["allowed"])
        self.assertFalse(decision["provider_called"])

    def test_local_restricted_and_online_public_are_allowed_by_policy(self) -> None:
        self.assertTrue(evaluate_demo_policy("local", "restricted")["allowed"])
        self.assertTrue(evaluate_demo_policy("online", "public")["allowed"])

    def test_http_surface_serves_health_snapshot_and_security_headers(self) -> None:
        server = create_demo_server(port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base_url = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            with urllib.request.urlopen(f"{base_url}/healthz", timeout=2) as response:
                health = json.load(response)
                self.assertEqual(health["status"], "ok")
                self.assertEqual(response.headers["X-Frame-Options"], "DENY")
                self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])
            with urllib.request.urlopen(
                f"{base_url}/api/demo?pack=au&case=case-ember", timeout=2
            ) as response:
                snapshot = json.load(response)
                self.assertEqual(snapshot["case"]["case_id"], "case-ember")
                self.assertEqual(snapshot["regulatory"]["pack_id"], "au")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_server_refuses_network_binding(self) -> None:
        with self.assertRaisesRegex(ValueError, "loopback"):
            create_demo_server("0.0.0.0", 0)
