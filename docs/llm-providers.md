# LLM provider architecture

TraceAML supports explicit selection of local or online models through one policy
boundary. Provider choice is configuration, never a hidden fallback.

## Data-classification defaults

| Classification | Local provider | Online provider |
| --- | --- | --- |
| Public | Allowed | Allowed by the default policy |
| Internal | Allowed | Denied unless explicitly enabled |
| Confidential | Allowed | Denied unless explicitly enabled |
| Restricted | Allowed | Denied by default; production policy should keep it local |

An institution may define a stricter policy. Enabling an online classification is a
governance decision that should consider contracts, data residency, retention,
subprocessors, model-training terms, professional secrecy and applicable privacy law.

## Supported adapters

- `OllamaProvider` uses Ollama's local chat endpoint and JSON response mode.
- `OpenAICompatibleProvider` supports chat-completions-compatible HTTPS APIs and
  compatible local servers. API keys are passed at runtime and are not recorded.
- Additional providers implement the small `LLMProvider` protocol.

Unencrypted HTTP is accepted only for loopback local-model endpoints. Remote internal
model gateways must use HTTPS.

## Evidence-first contract

The investigator sends a bounded JSON evidence set between explicit untrusted-data
markers. The model must return a JSON object containing a summary and claims. Every
claim needs at least one evidence ID present in that request. Unknown or missing
citations reject the complete output.

This proves traceability, not factual entailment. Evaluation datasets and human review
are still required to test whether a claim is actually supported by its cited evidence.

## Recorded metadata

TraceAML records:

- provider name and local/online classification;
- model name and purpose;
- case-data classification;
- request and response hashes;
- evidence IDs;
- run status and bounded error code;
- timestamp and tenant.

Raw prompts and responses are not stored in the LLM-run table. If a customer chooses
to retain them as evidence, they must go through the encrypted evidence store and its
retention policy.

## Non-goals

LLMs cannot autonomously close cases, change risk ratings, activate detection rules,
file regulatory reports, contact customers, or call external tools. Those actions
require purpose-built services, authorization and human approval.

