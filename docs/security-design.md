# Security design record

This document explains the machine-readable
[`security-architecture.json`](security-architecture.json) and its deterministic
[`security-architecture.svg`](security-architecture.svg) projection. The broader product scope,
data and cryptography inventories, release behavior, and test mapping live in
[`product-design.md`](product-design.md) and [`release-test-plan.md`](release-test-plan.md).
The review disposition for repository-owned, host-owned, provider-owned, residual, and
non-applicable requirements lives in
[`security-control-disposition.md`](security-control-disposition.md).
This record contains no internal workflow, program identifier, submission version, or approval.

## System scope

This security record covers the NemoClaw DLI course repository and the static course artifact it
builds. It does not classify or release the NemoClaw product, launchable, runtime, model service,
or relay deployments. Those systems appear below only as external dependencies and trust
boundaries exercised by course lessons.

Protected CI builds one static HTML, JavaScript, CSS, image, and locale artifact. The primary
delivery path uses a public static host. An alternative integration pins a reviewed course release
and vendors the static tree into a co-located launchable landing page. Both paths execute the course
in the learner browser and connect to required model and NemoClaw services.

Docker Compose files under `deploy/` and services under `cpu/services/` support local authoring and
tests. They are absent from the production static-site pipeline unless a future deployment adds
them. The architecture validator rejects unreviewed production dependencies.

## Threat-analysis invariants

Use these statements as the canonical Target of Evaluation summary. A generated summary that
contradicts one of them must be corrected before its risk labels or requirement statuses are
accepted.

- The subject is the DLI course repository and its static course artifact. The NemoClaw product,
  launchable, runtime, model service, and relay deployments are external dependencies, not releases
  or security boundaries owned by this repository.
- The intended OSS Type I source and published course artifact are public. Their confidentiality
  after publication is not a security objective. Pre-publication confidentiality and Git transport
  configuration remain host-owned controls, and secrets are forbidden from source and build output.
- The learner browser is untrusted. Model and gateway bearer credentials are JavaScript-readable
  values retained in `localStorage`; browser storage is not a vault. A compromised browser context
  can read them. HttpOnly cookies require a same-origin broker, and proof-of-possession requires
  issuer and service support.
- Proposed-change validation executes untrusted repository code only in read-only jobs. Those jobs
  receive no deployment credentials or release keys. A reviewed protected-branch build produces the
  artifact, and a separately permissioned deployment job uses short-lived GitHub OIDC,
  protected-environment review, serialized publication, artifact re-verification, and live-byte
  comparison.
- The repository records a complete SHA-256 inventory and preserves one reviewed artifact through
  deployment. Cryptographic signing or provenance attestation is Not verified; a checksum is not a
  signature.
- Live host, launchable, relay, model-service, and runtime controls are Unknown until their owners
  supply evidence. This design does not assume mTLS, DPoP, zero-retention model processing,
  prompt-injection detection, private Git networking, or a curated private package registry.

## Browser routing by host

| Course host | Model service | NemoClaw runtime |
|---|---|---|
| Public static host | Direct HTTPS to the selected model endpoint. The default is NVIDIA-hosted; a presenter may supply a compatible capacity fallback. | HTTPS and WebSocket through the reviewed cross-origin relay. |
| Co-located launchable with a pinned course release | Direct HTTPS using the endpoint and credentials supplied through the launchable startup path and the course's existing browser credential mechanism. | Same-origin direct route to the launchable-created runtime; do not use the relay. |
| Either host embedded in an iframe | Model relay when explicit iframe proxy mode is enabled. | Follow the host-specific NemoClaw route above. |

Relays are transport choices, not substitute services. The host changes the route, not the learning
contract.

## Trust boundaries and data

| Boundary | Transport and data | Authentication | Primary controls |
|---|---|---|---|
| Contributor to protected CI | Git source and commit metadata | Developer identity and protected review | Required validators, DCO, protected merge and release permissions |
| CI to static host | Validated static bundle | Protected deployment identity | Serialized publication, post-deploy checks, human review |
| Static host to learner device | HTTPS pages and assets | Public or host-controlled access | Relative paths, locale integrity, preview isolation, URL checks |
| Browser to model service | HTTPS credential, prompts, and responses | Learner-provided bearer credential | TLS, password input, direct route by default, optional iframe relay |
| Browser to NemoClaw | HTTPS and WebSocket commands, events, and gateway credential | Gateway credential plus hosting identity | Host restriction, credential handling, sandbox policy, host-specific routing |
| Static host to browser | Same-origin vendored JavaScript and CSS | Host access policy | Exact lock, license inventory, artifact SHA-256, source-reference validation |

Credentials are entered through password fields and retained in browser storage for reuse. They are
not built into the static artifact or sent to repository CI. The model destination is visible and
requires an explicit save; a query parameter can only prefill it. Prompts, responses, agent commands,
and events cross the selected service boundaries. The repository adds no production application
database or server-side learner-data store.

Startup-provided material in the co-located path populates the same storage entry consumed by the
course helpers. The course separately caches only a non-authoritative verification result for the
browser session.

An attacker who already executes code in the learner's browser context can read JavaScript-accessible
credentials and observe prompts or responses before transport encryption. The static course cannot
create a stronger secret boundary inside that compromised context. Moving credentials to HttpOnly
cookies would require a same-origin credential broker, while proof-of-possession tokens require
credential-issuer and service support. Those are hosting and service architecture decisions, not a
client-only mitigation. Repository controls instead prevent unreviewed executable dependencies,
constrain credential destinations, render untrusted output safely, and give learners explicit save,
replace, and clear actions.

## Security controls

- Static validation covers page structure, learner flow, provenance, localization, dependency
  pins, architecture drift, contribution boundaries, and release artifacts.
- GitHub Pages builds in a read-only job, rejects unexpected executable references and artifact
  substitution, records every generated file by SHA-256, and exercises the exact tree in Chromium.
- Eligible browser dependencies require exact versions and subresource integrity.
- Cross-origin relays are restricted to reviewed routes and authentication behavior.
- NemoClaw applies launch authentication, gateway checks, and sandbox policy.
- Secrets, live credentials, internal deployment identifiers, scan output, and approval records do
  not belong in this document or graph.

Operational relay deployment, launchable configuration, identity policy, protected environments,
and provider controls live outside this repository. Operators compare live configuration with this
design before release.

## Release controls

Required CI validates source, builds the static artifact, checks configured deployed URLs, and
records human ownership. Branch previews are isolated and time-bound. GitHub Pages deploys only the
immutable artifact that passed generated-tree integrity checks and browser tests; the protected
`github-pages` environment requires human review after those results exist, and the deploy job
rechecks the artifact manifest before publication. A separate protected-tag path produces
deterministic archives, a release manifest, an SBOM, and checksums.

Python dependencies support local authoring and tests, not the production browser runtime. Direct
manifests and transitive locks are checked for parity. Scanner tooling uses a separate locked
environment. Time-limited exceptions remain in the waiver register and are guarded by reachability
checks.

## Evidence and reconstruction

The JSON graph is the source of truth; the SVG is generated. Every production node and flow names
repository evidence. Validation also derives CI stages, release jobs, browser host roles, dynamic
remote-host suffixes, and relay sources from code. Substantial drift fails CI until the graph and
this design are reviewed.

The public record contains component roles, trust zones, data and authentication classes, control
intent, repository evidence paths, and source-derived topology fingerprints.
Keep internal program identifiers and review-system URLs outside the repository. The same boundary
applies to submission versions, scan output, credentials, deployment identifiers, and approval records.

An authorized reviewer can reconstruct a private submission from the reviewed commit:

1. Run the renderer and architecture audit.
2. Review the SVG with this design and the product design.
3. Add live-control evidence and private identifiers only in the approved internal workflow.

Repository validators support human analysis; they do not replace it or claim external-host
configuration, provider controls, publication approval, or completion of a security process.

### Regenerate and verify

```bash
python3 scripts/figures/render_security_architecture.py --check
python3 scripts/validation/security_architecture_audit.py --self-test
python3 scripts/validation/security_architecture_audit.py
```

After an intentional graph change, run
`python3 scripts/figures/render_security_architecture.py`. Inspect the source-derived view with
`python3 scripts/validation/security_architecture_audit.py --observed-contract`.

The audit rejects stale projections, unclassified local services or volumes, missing production
nodes, dangling edges, undocumented trust-boundary crossings, unlabeled sensitive flows, broken
evidence anchors, overlaps, and ambiguous collinear flows. The flow register uses three lines per
edge: endpoints, transport and data, then authentication and trust boundary.
