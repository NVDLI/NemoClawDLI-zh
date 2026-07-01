# Security design record

This document supplies the public system context needed to interpret
[`security-architecture.svg`](security-architecture.svg). It is intentionally independent of any
internal review system, program identifier, submission version, or approval state.

## System scope

Protected CI builds one static HTML, JavaScript, CSS, image, and locale artifact. The primary delivery
path uses a public static host. An alternative integration pins a reviewed course release and vendors
the static tree into a co-located launchable landing page. Both paths execute the course in the learner
browser and connect to required model and NemoClaw services.

Docker Compose files under `deploy/` and services under `cpu/services/` support local authoring and
tests. They are absent from the production static-site pipeline unless a future deployment explicitly
adds them. The architecture validator rejects unreviewed production dependencies.

## Deployment variants

| Course host | Model service | NemoClaw runtime |
|---|---|---|
| Public static host | Direct HTTPS from the browser by default. | HTTPS and WebSocket through the reviewed cross-origin relay. |
| Co-located launchable with a pinned course release | Direct HTTPS using credentials supplied through the launchable startup path and the course's existing browser storage mechanism. | Same-origin direct route to the launchable-created runtime. |
| Either host embedded in an iframe | Model relay when explicit iframe proxy mode is enabled. | Follow the host-specific NemoClaw route above. |

## Trust boundaries and data

| Boundary | Transport and data | Authentication | Primary controls |
|---|---|---|---|
| Contributor to protected CI | Git source and commit metadata | Developer identity and protected review | Required validators, DCO, protected merge and release permissions |
| CI to static host | Validated static bundle | Protected deployment identity | Serialized publication, post-deploy checks, human review |
| Static host to learner device | HTTPS pages and assets | Public or host-controlled access | Relative paths, locale integrity, preview isolation, URL checks |
| Browser to model service | HTTPS credential, prompts, and responses | Learner-provided bearer credential | TLS, password input, direct route by default, optional iframe relay |
| Browser to NemoClaw | HTTPS and WebSocket commands, events, and gateway credential | Gateway credential plus hosting identity | Host restriction, credential handling, sandbox policy, host-specific routing |
| Browser to public dependencies | HTTPS JavaScript and CSS | No caller identity | Version pins, SRI where supported, dependency validation |

Credentials are entered through password fields and retained in browser storage for reuse. They are
not built into the static artifact or sent to repository CI. Prompts, responses, agent commands, and
events cross the selected service boundaries. The repository adds no production application database
or server-side learner-data store.

The co-located path reuses the existing browser credential mechanism. Startup-provided material
populates the same storage entry consumed by the course helpers; the course separately caches only a
non-authoritative verification result for the browser session.

## Security controls

- Static validation covers page structure, learner flows, source provenance, localization,
  dependency pins, architecture drift, contribution boundaries, and release artifacts.
- Eligible static dependencies require version pins and subresource integrity.
- Cross-origin relays are restricted to the reviewed route and authentication behavior.
- NemoClaw applies launch authentication, gateway checks, and sandbox policy.
- Secrets, live credentials, internal deployment identifiers, scan output, and approval records do
  not belong in this document or graph.

Operational relay deployment, launchable configuration, identity policy, protected environments, and
provider controls live outside this repository. Operators must compare live configuration with this
design before release.

## Release controls

Required CI validates source, builds the static artifact, checks deployed URLs where configured, and
records human ownership. Branch previews are isolated and time-bound. A separate protected-tag path
produces deterministic archives, a release manifest, an SBOM, and checksums.

Python dependencies support local authoring and tests, not the production browser runtime. Direct
manifests and transitive locks are checked for parity. Scanner tooling uses a separate locked
environment so it does not become runtime inventory. Time-limited exceptions remain in the dedicated
waiver register and are guarded by reachability checks.

## Evidence and reconstruction

[`security-architecture.json`](security-architecture.json) is the source of truth. Every production
node and flow names repository evidence. The SVG is generated; manual edits fail validation. The
validator also derives CI stages, release jobs, browser host roles, dynamic launchable suffixes, and
relay sources from code. Substantial drift fails CI until the graph and design record are reviewed.

An authorized reviewer can reconstruct an internal submission without internal metadata in this
repository:

1. Select the reviewed commit or immutable release tag.
2. Run the renderer and architecture audit.
3. Use the SVG as the system diagram and this file as its design context.
4. Add program identifiers, submission versions, live-control evidence, and approval records only in
   the approved internal workflow.

This package does not claim external-host configuration, provider controls, public-release approval,
or completion of any internal security process. Repository validators support human analysis; they do
not replace it.
