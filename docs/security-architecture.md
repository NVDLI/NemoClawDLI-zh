# Security architecture

This repository keeps a machine-readable security architecture in
[`security-architecture.json`](security-architecture.json) and a deterministic visual projection in
[`security-architecture.svg`](security-architecture.svg). These files describe the system; they do
not encode a particular internal review workflow, program identifier, submission version, or approval.
Read [`security-design.md`](security-design.md) for the trust-boundary rationale and
[`product-design.md`](product-design.md) for the complete released-product boundary.

The production graph covers three connected concerns:

- Source proposals pass through protected validation into one static course artifact.
- The same artifact can use a public static host or a version-pinned, co-located launchable host.
- The learner browser reaches required model and agent services, optional relays, and pinned browser
  dependencies across explicit trust boundaries.

The Compose stack under `deploy/` and `cpu/services/` supports local authoring and testing. It is not
part of the production static-site topology. The graph classifies those services and volumes as
local-only so an accidental production dependency fails validation.

## Browser routing by host

| Course host | Model service | NemoClaw runtime |
|---|---|---|
| Public static host | Direct browser HTTPS by default. | Use the reviewed cross-origin relay required by the separately hosted runtime. |
| Co-located launchable with a pinned course release | Direct browser HTTPS using startup-provided credentials through the course's existing storage path. | Same-origin direct route to the launchable-created runtime; do not use the relay. |
| Either host embedded in an iframe | Use the model relay when explicit iframe proxy mode is enabled. | Follow the host-specific route above. |

The model service and NemoClaw are required for their respective lessons. Relays are transport
choices, not substitute services. The route changes with the hosting boundary; the learning contract
does not.

## Public evidence boundary

The repository records only information needed to understand and verify the shipped system:

- component roles, trust zones, data classes, authentication classes, and control intent;
- repository evidence paths that substantiate each node and flow;
- source-derived topology inventories used to detect substantial drift; and
- deterministic regeneration and validation commands.

Keep internal program identifiers, review-system URLs, submission versions, scan output, credentials,
deployment identifiers, and approval records outside this repository. An authorized reviewer can
reconstruct a review package by combining this source-backed graph, the security design record, the
reviewed commit, and the organization's approved internal tooling.

## Regenerate and verify

Run from the repository root:

```bash
python3 scripts/figures/render_security_architecture.py --check
python3 scripts/validation/security_architecture_audit.py --self-test
python3 scripts/validation/security_architecture_audit.py
```

After an intentional graph change:

```bash
python3 scripts/figures/render_security_architecture.py
```

The audit rejects stale projection output, unclassified local services or volumes, missing production
nodes, dangling edges, undocumented trust-boundary crossings, unlabeled sensitive flows, broken
evidence anchors, overlapping nodes, and ambiguous collinear flows. It also derives CI stages,
release jobs, browser host roles, dynamic remote-host suffixes, and relay sources from repository
code. Inspect that derived view with:

```bash
python3 scripts/validation/security_architecture_audit.py --observed-contract
```

The flow register uses three lines per edge: endpoints, transport plus data, then authentication plus
trust boundary. Keep those fields concise. The SVG is an index into the JSON source, not a second
prose specification.
