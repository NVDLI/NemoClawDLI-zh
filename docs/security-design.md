# Security design record

This document explains the machine-readable
[`security-architecture.json`](security-architecture.json) and its deterministic
[`security-architecture.svg`](security-architecture.svg) projection. The broader product scope,
data and cryptography inventories, release behavior, and test mapping live in
[`product-design.md`](product-design.md) and [`release-test-plan.md`](release-test-plan.md).
Aggregate current controls, future candidates, triggers, and verification expectations live in
[`security-control-themes.json`](security-control-themes.json). The shorter human status view is
[`security-control-disposition.md`](security-control-disposition.md).
This record contains no internal workflow, program identifier, submission version, or approval.

## System scope

This security record covers the NemoClaw DLI course repository and the static course artifact it
builds. It does not classify or release the NemoClaw product, launchable, runtime, model service,
or relay deployments. Those systems appear below only as external dependencies and trust
boundaries exercised by course lessons.

The repository owns source and workflow definitions; an external source host and CI service execute
those workflows. They produce one static HTML, JavaScript, CSS, image, and locale artifact. A public
static host or co-located launchable serves that artifact. Course code then runs in the learner's
untrusted browser and connects to external model and NemoClaw services.
The co-located launchable may select a reviewed course release for vendoring, but its intake and
deployment remain external and unattested by this repository.

Docker Compose files under `deploy/` and services under `cpu/services/` support local authoring and
tests. They are absent from the production static-site pipeline unless a future deployment adds
them. The architecture validator rejects unreviewed production dependencies.

## Threat-analysis invariants

Use these statements as the canonical Target of Evaluation summary. A generated summary that
contradicts one of them must be corrected before its risk labels or requirement statuses are
accepted.

- The subject is the DLI course repository and its static course artifact. The NemoClaw product,
  source host and CI service, static host, launchable, runtime, model service, browser environment,
  and relay deployments are external dependencies, not releases or security boundaries owned by
  this repository.
- The intended OSS Type I source and published course artifact are public. Their confidentiality
  after publication is not a security objective. Pre-publication confidentiality and Git transport
  configuration remain host-owned controls, and secrets are forbidden from source and build output.
- The learner browser is untrusted. Model and gateway bearer credentials are JavaScript-readable
  values retained in `localStorage`; browser storage is not a vault. A compromised browser context
  can read them. HttpOnly cookies require a same-origin broker, and proof-of-possession requires
  issuer and service support.
- Proposed-change validation executes untrusted repository code only in read-only jobs. Those jobs
  hold no signing key, model API credential, runtime credential, production-service secret, or
  deployment key. The workflow separates artifact build from a deployment job configured for
  short-lived GitHub OIDC, serialized publication, artifact re-verification, and live-byte
  comparison. Required protected-environment review is live host evidence, not a repository fact.
- CI does not write Git refs or repository content. Logs and test results are job artifacts or
  external records. Branch and merge-request validation is normal; protected annotated tags only
  identify release candidates.
- A protected-environment reviewer is a human actor, not a component. A static host serves bytes;
  repository workflows, not the host, enforce build and deployment gates.
- In the architecture diagram, only solid green nodes are Target of Evaluation components. Dashed
  gray nodes are external context with no live-control attestation. Edges state expected integration
  routes and data, not verified external configuration. External-to-external internals are excluded.
- The repository records a complete SHA-256 inventory and preserves one reviewed artifact through
  deployment. Cryptographic signing or provenance attestation is Not verified; a checksum is not a
  signature.
- Live host, launchable, relay, model-service, and runtime controls are Unknown until their owners
  supply evidence. This design does not assume mTLS, DPoP, zero-retention model processing,
  prompt-injection detection, private Git networking, or a curated private package registry.

## Browser routing by host

| Course host | Model service | NemoClaw runtime |
|---|---|---|
| Public static host | Direct HTTPS to the selected model endpoint. The default is NVIDIA-hosted; a presenter may supply a compatible capacity fallback. | HTTPS and WebSocket through the configured cross-origin relay; live relay controls require operator evidence. |
| Co-located launchable with a pinned course release | Direct HTTPS using the endpoint and credentials supplied through the launchable startup path and the course's existing browser credential mechanism. | Same-origin direct route to the launchable-created runtime; do not use the relay. |
| Either host embedded in an iframe | Model relay when explicit iframe proxy mode is enabled. | Follow the host-specific NemoClaw route above. |

Relays are transport choices, not substitute services. The host changes the route, not the learning
contract.

## Trust boundaries and data

| Boundary | Transport and data | Authentication | Primary controls |
|---|---|---|---|
| Course source to external CI | Public source and commit metadata | Developer identity; live policy requires operator evidence | Repository validators and DCO; live identity and review settings unverified |
| External CI to static host | Static bundle and SHA-256 inventory | Workflow-requested deployment identity; live rules unverified | Bounded artifact, manifest recheck, and post-deploy byte comparison |
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
- Browser dependencies require exact versions, a generated integrity inventory, and same-origin delivery.
- Course code selects reviewed relay routes and authentication behavior; live relay enforcement is Unknown until the operator supplies evidence.
- Course code expects launch authentication, gateway checks, and sandbox policy; their deployed state is Unknown until launchable and runtime owners supply evidence.
- Secrets, live credentials, internal deployment identifiers, scan output, and approval records do
  not belong in this document or graph.

Operational relay deployment, launchable configuration, identity policy, protected environments,
and provider controls live outside this repository. Operators compare live configuration with this
design before release.

## Release controls

Repository workflow definitions validate source, build the static artifact, check configured URLs,
and record human ownership. They request isolated branch previews and manifest-preserving Pages
deployment; live source-host enforcement remains operator evidence. A separate tag workflow produces
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
python3 -m unittest -v tests/validation/test_embedded_validator_suites.py
python3 scripts/validation/security_architecture_audit.py
```

After an intentional graph change, run
`python3 scripts/figures/render_security_architecture.py`. Inspect the source-derived view with
`python3 scripts/validation/security_architecture_audit.py --observed-contract`.

The audit rejects stale projections, unclassified local services or volumes, missing production
nodes, dangling edges, undocumented trust-boundary crossings, unlabeled sensitive flows, broken
evidence anchors, overlaps, and ambiguous collinear flows. The flow register uses three lines per
edge: endpoints, transport and data, then authentication and trust boundary.
