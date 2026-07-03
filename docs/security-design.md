# Security design record

This document explains the machine-readable
[`security-architecture.json`](security-architecture.json) and its deterministic
[`security-architecture.svg`](security-architecture.svg) projection. The broader product scope,
data and cryptography inventories, release behavior, and test mapping live in
[`product-design.md`](product-design.md) and [`release-test-plan.md`](release-test-plan.md).
This record contains no internal workflow, program identifier, submission version, or approval.

## System scope

Protected CI builds one static HTML, JavaScript, CSS, image, and locale artifact. The primary
delivery path uses a public static host. An alternative integration pins a reviewed course release
and vendors the static tree into a co-located launchable landing page. Both paths execute the course
in the learner browser and connect to required model and NemoClaw services.

Docker Compose files under `deploy/` and services under `cpu/services/` support local authoring and
tests. They are absent from the production static-site pipeline unless a future deployment adds
them. The architecture validator rejects unreviewed production dependencies.

## Browser routing by host

| Course host | Model service | NemoClaw runtime |
|---|---|---|
| Public static host | Direct HTTPS from the browser by default. | HTTPS and WebSocket through the reviewed cross-origin relay. |
| Co-located launchable with a pinned course release | Direct HTTPS using credentials supplied through the launchable startup path and the course's existing browser credential mechanism. | Same-origin direct route to the launchable-created runtime; do not use the relay. |
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
not built into the static artifact or sent to repository CI. Prompts, responses, agent commands, and
events cross the selected service boundaries. The repository adds no production application
database or server-side learner-data store.

Startup-provided material in the co-located path populates the same storage entry consumed by the
course helpers. The course separately caches only a non-authoritative verification result for the
browser session.

## Security controls

- Static validation covers page structure, learner flow, provenance, localization, dependency
  pins, architecture drift, contribution boundaries, and release artifacts.
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
records human ownership. Branch previews are isolated and time-bound. A separate protected-tag path
produces deterministic archives, a release manifest, an SBOM, and checksums.

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
