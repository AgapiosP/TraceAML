# Security policy

TraceAML is pre-alpha and must not be used with production personal or financial
data without an independent security review.

Please report vulnerabilities privately to the project maintainers rather than
opening a public issue. Until a dedicated security address exists, contact the
repository owner through the hosting platform.

The development branch now includes authenticated field encryption, tenant-scoped
storage and immutable audit rows. It does not yet provide production authentication,
authorization, external secrets management, secure evidence-object storage or full
deployment hardening. See `docs/security.md` for the implemented controls and the
remaining production gate.
