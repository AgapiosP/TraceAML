import sqlite3
from datetime import UTC, datetime
from decimal import Decimal
from importlib.util import find_spec
from unittest import TestCase, skipUnless

from traceaml.domain import Severity, Transaction
from traceaml.entities import (
    Account,
    AccountStatus,
    Alert,
    AlertStatus,
    CaseStatus,
    EntityType,
    InvestigationCase,
    Party,
    PartyKind,
    Relationship,
    Tenant,
)
from traceaml.security import AESGCMFieldCipher, DevelopmentPlaintextCipher
from traceaml.storage import SQLiteWorkspace

MOMENT = datetime(2026, 1, 1, tzinfo=UTC)


class StorageTests(TestCase):
    def setUp(self) -> None:
        self.workspace = SQLiteWorkspace(
            ":memory:", DevelopmentPlaintextCipher(), clock=lambda: MOMENT
        )
        self.workspace.create_tenant(Tenant("one", "Tenant One", MOMENT))
        self.workspace.create_tenant(Tenant("two", "Tenant Two", MOMENT))

    def tearDown(self) -> None:
        self.workspace.close()

    def _seed_account(self, tenant_id: str, suffix: str) -> Account:
        party = Party(
            tenant_id=tenant_id,
            party_id=f"party-{suffix}",
            kind=PartyKind.INDIVIDUAL,
            display_name=f"Synthetic {suffix}",
            countries=("us",),
            created_at=MOMENT,
        )
        account = Account(
            tenant_id=tenant_id,
            account_id=f"account-{suffix}",
            party_id=party.party_id,
            label=f"Synthetic account {suffix}",
            currency="usd",
            status=AccountStatus.ACTIVE,
            created_at=MOMENT,
        )
        self.workspace.put_party(party)
        self.workspace.put_account(account)
        return account

    def test_records_are_tenant_scoped(self) -> None:
        self._seed_account("one", "same")
        self._seed_account("two", "same")
        one = self.workspace.get_party("one", "party-same")
        two = self.workspace.get_party("two", "party-same")
        assert one is not None and two is not None
        self.assertEqual(one.display_name, "Synthetic same")
        self.assertEqual(two.tenant_id, "two")
        self.assertIsNone(self.workspace.get_party("one", "missing"))

    def test_transaction_round_trip_and_duplicate_rejection(self) -> None:
        originator = self._seed_account("one", "a")
        beneficiary = self._seed_account("one", "b")
        transaction = Transaction(
            transaction_id="tx-1",
            occurred_at=MOMENT,
            amount=Decimal("12.34"),
            currency="USD",
            originator_account=originator.account_id,
            beneficiary_account=beneficiary.account_id,
            originator_country="US",
            beneficiary_country="GB",
            attributes={"synthetic": True},
        )
        self.workspace.put_transaction("one", transaction)
        restored = self.workspace.list_transactions_for_account("one", originator.account_id)
        self.assertEqual(restored, (transaction,))
        self.assertEqual(
            self.workspace.list_transactions_for_account("two", originator.account_id), ()
        )
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.workspace.put_transaction("one", transaction)

    def test_audit_chain_is_immutable_and_verifiable(self) -> None:
        self.workspace.append_audit("one", "case.created", "tester", {"case_id": "c1"})
        self.workspace.append_audit("one", "case.updated", "tester", {"case_id": "c1"})
        self.assertTrue(self.workspace.verify_audit("one"))
        with self.assertRaisesRegex(sqlite3.IntegrityError, "immutable"):
            self.workspace.connection.execute(
                "UPDATE audit_events SET actor = 'attacker' WHERE tenant_id = 'one'"
            )

    def test_relationship_alert_and_case_round_trip(self) -> None:
        self._seed_account("one", "a")
        relationship = Relationship(
            tenant_id="one",
            relationship_id="rel-1",
            source_type=EntityType.PARTY,
            source_id="party-a",
            target_type=EntityType.ACCOUNT,
            target_id="account-a",
            relationship_type="owns",
            observed_at=MOMENT,
            confidence=0.9,
            attributes={"source": "synthetic"},
        )
        alert = Alert(
            tenant_id="one",
            alert_id="alert-1",
            subject_type=EntityType.ACCOUNT,
            subject_id="account-a",
            title="Synthetic alert",
            severity=Severity.HIGH,
            status=AlertStatus.OPEN,
            created_at=MOMENT,
            finding_ids=("finding-1",),
        )
        case = InvestigationCase(
            tenant_id="one",
            case_id="case-1",
            title="Synthetic case",
            status=CaseStatus.IN_REVIEW,
            created_at=MOMENT,
            updated_at=MOMENT,
            alert_ids=(alert.alert_id,),
            assignee="analyst@example.test",
            jurisdiction_packs=("us",),
        )
        self.workspace.put_relationship(relationship)
        self.workspace.put_alert(alert)
        self.workspace.put_case(case)
        self.assertEqual(self.workspace.get_relationship("one", "rel-1"), relationship)
        self.assertEqual(self.workspace.get_alert("one", "alert-1"), alert)
        self.assertEqual(self.workspace.get_case("one", "case-1"), case)

    def test_production_rejects_plaintext_cipher(self) -> None:
        with self.assertRaisesRegex(ValueError, "production"):
            SQLiteWorkspace(":memory:", DevelopmentPlaintextCipher(), production=True)

    @skipUnless(find_spec("cryptography"), "cryptography is installed by project dependencies")
    def test_aes_gcm_cipher_authenticates_record_context(self) -> None:
        from cryptography.exceptions import InvalidTag

        cipher = AESGCMFieldCipher(b"x" * 32, "test-key")
        ciphertext = cipher.encrypt_json({"name": "Sensitive Person"}, "party:t:p1")
        self.assertNotIn(b"Sensitive Person", ciphertext)
        self.assertEqual(
            cipher.decrypt_json(ciphertext, "party:t:p1"), {"name": "Sensitive Person"}
        )
        with self.assertRaises(InvalidTag):
            cipher.decrypt_json(ciphertext, "party:t:p2")
