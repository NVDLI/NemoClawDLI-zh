# Security control disposition

This is the short human view of the canonical aggregate register in
[`security-control-themes.json`](security-control-themes.json). The generated review design embeds
the full register so exported reviewers do not need repository links. Private findings remain in the
authorized review system. Scope and trust-boundary detail remains in the
[`security design`](security-design.md).

## Status vocabulary

- **Verified:** repository evidence proves the control.
- **Partially verified:** repository evidence covers only part of the boundary.
- **External evidence required:** an operator must prove the live control.
- **Architecture decision required:** mitigation would change the static-client design.
- **Human review required:** an accountable reviewer must reconcile evidence and status.
- **Not applicable:** the control cannot meet the stated objective in this product boundary.

Current status and evidence take precedence over future work. A future candidate is not
implemented and cannot support a Mitigated status. An external control without current operator
evidence remains Not Mitigated; contradictions resolve to the conservative status.

Repository evidence does not grant Legal, open-source, Export, Privacy, Product Security, source-host,
host, service, or release approval.

## Review synthesis

Generated assessments can misclassify recommendations as current controls or expand the course
boundary. Correct scope, evidence, ownership, and status before accepting their risk output.

Public evidence stays aggregated by control theme. Do not version private review rows one-to-one.

| Theme | State | Why it remains open |
|---|---|---|
| Source and CI trust | Shared verification required | Repository workflows are reviewable; live identity, branch, bypass, and reviewer settings are host evidence. |
| Build supply chain | Partially verified | Exact locks, inventories, SCA, and SBOM exist; hermetic or reproducible build assurance is a release-policy decision. |
| Artifact integrity | Partially verified | Byte continuity is verified; cryptographic signature and provenance attestation are not verified. |
| Static host and browser | Shared verification required | Static code checks are verified; response headers, WAF, cache policy, and availability are host controls. |
| Browser-held credentials | Architecture decision required | JavaScript-readable credentials are inherent to direct browser calls; a broker or proof-of-possession changes other systems. |
| Relay, model, launchable, and runtime | External evidence required | The repository tests client contracts but cannot attest deployed service authorization, isolation, quotas, or retention. |
| Assessment fidelity | Human review required | Generated scope, ownership, and statuses must be reconciled with evidence. |

## Source and contribution controls

- Verified: pull-request jobs are read-only, receive no deployment credentials, use immutable action
  pins, and run required validation with timeouts.
- Host evidence required: MFA, protected branches and tags, required reviewers, bypass restrictions,
  commit-signature policy, and immutable audit history.
- The intended OSS Type I classification applies only to the NemoClaw DLI course repository and its
  static course artifacts. It does not classify or release the NemoClaw product, launchable,
  runtime, relays, or services.

## Build and artifact controls

- Verified: exact dependency locks, dependency inventories, bounded artifacts, safe extraction,
  complete SHA-256 inventory, single-artifact promotion, and post-deploy byte comparison.
- Not verified: an approved signing identity and cryptographic provenance attestation.
- Conditional next step: add a hermetic, reproducible builder and approved package mirror if release
  policy requires stronger dependency-origin assurance.

## Static hosting and browser controls

- Verified: no remote executable dependencies, reviewed URL policy, exact browser dependency
  inventory, and safe model-output rendering.
- Host evidence required: HTTPS and HSTS state, response-header CSP, immutable caching, WAF and
  bandwidth limits, availability, and incident response.
- Not applicable as independent controls: browser certificate pinning and same-origin Subresource
  Integrity. Browser trust stores own certificate validation; replacing same-origin HTML and assets
  together defeats an asset-only hash. Whole-artifact verification covers the repository boundary.
- Endpoint compromise or a malicious browser extension can read browser-visible credentials and
  content. Course code reduces injection opportunities but cannot make a compromised browser safe.

## Relay, model, launchable, and runtime controls

These systems are external dependencies. Their owners must prove, as applicable:

- destination, method, schema, body, frame, deserialization, and object-authorization enforcement;
- credential lifetime, audience, revocation, replay, binding, and mTLS decisions;
- request, token, concurrency, connection, compute, storage, spend, and egress quotas;
- instruction and tool authorization, tenant and sandbox isolation, logging, retention, alerting,
  patching, recovery, and incident response.

The course repository can test route selection and client behavior. It cannot convert missing live
service evidence into a mitigation.

## Publication blockers and retained risks

Before publication, authorized owners must resolve:

- Live source-host rules, identities, reviewers, bypasses, and scheduled public-to-internal sync.
- Artifact signing and provenance policy.
- Static-host security-header, cache, WAF, capacity, and availability decisions.
- Browser credential lifetime, audience, revocation, replay, storage, and shared-device behavior.
- Relay, model-service, launchable, and runtime evidence listed above.
- Authoritative secret, vulnerability, malware, license, privacy, and release reviews.
- Generated scope and status reconciliation against `security-control-themes.json`.

Unknown, partial, architecture-decision, shared-verification, and human-review states remain open.
