# Customer demonstration

The TraceAML customer demonstration is a read-only investigation workspace powered by
the real deterministic rules, graph, evidence and audit components. It contains three
fictional alert scenarios and must not be used with personal or customer data.

## Launch

Install the project and start the demonstration:

```bash
python -m pip install -e .
traceaml demo-ui
```

The workspace opens in the default browser at `http://127.0.0.1:8765`. To launch it
without opening a browser automatically, use `traceaml demo-ui --no-browser`.

## Suggested five-minute walkthrough

1. Start with the four assurance metrics: open alerts, claim-to-evidence coverage,
   audit integrity and the illustrative review time.
2. Select each alert and explain that the case narrative, transactions and graph are
   rebuilt from that scenario by the TraceAML engine.
3. Show the evidence identifiers beside every finding. Explain that unsupported LLM
   claims are rejected by the investigation layer.
4. Change the jurisdiction selector to demonstrate the global core and versioned
   EU, UK, US and Australia review contexts.
5. Under **Provider routing**, select **Online API** while the classification is
   **Restricted**. The actual routing policy blocks the request before any provider
   can receive data. Select **Public** to show the permitted policy state.
6. Finish with the audit events and reiterate that a human owns every investigation
   and reporting decision.

The built-in **Guided tour** follows the same sequence.

## What is real and what is illustrative

Real implementation demonstrated:

- deterministic high-value and cross-border rules;
- evidence identifiers and claim validation;
- two-hop transaction graph construction;
- versioned jurisdiction-pack loading;
- hash-chained audit verification;
- local/online provider policy evaluation and data classification;
- loopback-only server and restrictive browser security headers.

Illustrative presentation:

- people, organizations, accounts, transactions and alert IDs;
- the displayed risk score and review duration;
- investigator assignment and workflow status;
- the AI provider availability labels.

The demonstration never calls a local or online LLM. Connecting configured providers
belongs in the authenticated production API milestone, where tenant policies and run
records can be enforced consistently.

## Safety and limitations

- The server binds only to the local device and cannot be exposed using `0.0.0.0`.
- Every response is marked `no-store` and carries a restrictive Content Security
  Policy, framing protection and content-type protection.
- There are no write endpoints, uploads, cookies or credentials.
- This is a pre-alpha product demonstration, not a supported production deployment,
  regulatory determination, suspicious-activity filing recommendation or autonomous
  decision system.
