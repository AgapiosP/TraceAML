import json
from dataclasses import dataclass
from datetime import UTC, datetime
from unittest import TestCase

from traceaml.domain import Evidence
from traceaml.entities import DataClassification
from traceaml.llm import (
    GroundedInvestigator,
    LLMPolicy,
    LLMPolicyError,
    LLMProvider,
    LLMResponseError,
    LLMRouter,
    OllamaProvider,
    OpenAICompatibleProvider,
    ProviderKind,
    ProviderResponse,
)


@dataclass
class StubProvider:
    name: str
    kind: ProviderKind
    content: str
    model: str = "stub-model"

    def generate(self, request):
        return ProviderResponse(self.content, self.model)


def evidence() -> Evidence:
    return Evidence(
        evidence_id="ev-1",
        kind="rule_observation",
        source_id="tx-1",
        observed_at=datetime(2026, 1, 1, tzinfo=UTC),
        facts={"amount": "10000", "currency": "USD"},
    )


class LLMTests(TestCase):
    def test_online_provider_is_denied_for_restricted_data(self) -> None:
        provider: LLMProvider = StubProvider(
            "online", ProviderKind.ONLINE, '{"summary":"x","claims":[]}'
        )
        service = GroundedInvestigator(LLMRouter((provider,)))
        with self.assertRaises(LLMPolicyError):
            service.draft(
                tenant_id="tenant",
                evidence=(evidence(),),
                classification=DataClassification.RESTRICTED,
                provider_name="online",
            )

    def test_explicit_policy_can_allow_confidential_online_processing(self) -> None:
        content = json.dumps(
            {
                "summary": "Review required.",
                "claims": [{"text": "Amount observed.", "evidence_ids": ["ev-1"]}],
            }
        )
        provider: LLMProvider = StubProvider("online", ProviderKind.ONLINE, content)
        router = LLMRouter(
            (provider,),
            LLMPolicy(frozenset({DataClassification.CONFIDENTIAL})),
        )
        result = GroundedInvestigator(router).draft(
            tenant_id="tenant",
            evidence=(evidence(),),
            classification=DataClassification.CONFIDENTIAL,
            provider_name="online",
        )
        self.assertEqual(result.claims[0].evidence_ids, ("ev-1",))

    def test_unknown_evidence_citation_is_rejected(self) -> None:
        provider: LLMProvider = StubProvider(
            "local",
            ProviderKind.LOCAL,
            '{"summary":"Review","claims":[{"text":"Unsupported","evidence_ids":["missing"]}]}',
        )
        with self.assertRaises(LLMResponseError):
            GroundedInvestigator(LLMRouter((provider,))).draft(
                tenant_id="tenant",
                evidence=(evidence(),),
                classification=DataClassification.RESTRICTED,
                provider_name="local",
            )

    def test_endpoint_transport_rules(self) -> None:
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            OpenAICompatibleProvider(
                name="online",
                model="model",
                base_url="http://example.com/v1",
                kind=ProviderKind.ONLINE,
                api_key="secret",
            )
        with self.assertRaisesRegex(ValueError, "loopback"):
            OllamaProvider(name="ollama", model="model", base_url="http://192.0.2.1:11434")

    def test_router_records_hashes_without_raw_prompt(self) -> None:
        class Recorder:
            def __init__(self):
                self.values = []

            def record_llm_run(self, **values):
                self.values.append(values)

        recorder = Recorder()
        provider: LLMProvider = StubProvider(
            "local",
            ProviderKind.LOCAL,
            '{"summary":"Review","claims":[{"text":"Observed","evidence_ids":["ev-1"]}]}',
        )
        GroundedInvestigator(LLMRouter((provider,), recorder=recorder)).draft(
            tenant_id="tenant",
            evidence=(evidence(),),
            classification=DataClassification.RESTRICTED,
            provider_name="local",
        )
        self.assertEqual(len(recorder.values), 1)
        self.assertNotIn("user_content", recorder.values[0])
        self.assertEqual(len(recorder.values[0]["request_hash"]), 64)
