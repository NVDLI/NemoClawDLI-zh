# Open-source release readiness

This repository is an internal release candidate prepared for a proposed Apache-2.0
open-source publication. External publication remains pending OSRB approval. The canonical
state is recorded in `RELEASE_STATUS.json`. This guide is
a release-safe operating procedure for contributors and maintainers. It intentionally avoids
private ticket systems, internal wiki links, and company-only process URLs.

## When to Use This Guide

Use this guide before adding or changing course material that may ship outside the private review repository. It applies to source code, notebooks, course pages, images, datasets, models, containers, prompts, generated assets, and reference packets.

Do not use this guide to decide whether a course should be open sourced. That decision belongs to the project owner and approvers before repository preparation begins.

## Required Records

Every release candidate needs these records:

- scope and owner
- source inventory and license disposition
- execution evidence, or a no-execution rationale
- maintenance owner and contribution model
- security and secrets sweep evidence
- unresolved blockers or explicit not-applicable rationale

The product scope and release behavior live in `docs/product-design.md`. The verification
contract lives in `docs/release-test-plan.md`, with its machine-readable ownership map in
`docs/release-evidence.json`. The source inventory lives at
`scripts/compliance/docs/source_inventory.json`. The policy that explains what may be vendored
lives at `scripts/compliance/docs/vendor_policy.md`.

## Roles

- Content owner: defines scope, owns source material, and coordinates review.
- Legal or IP reviewer: reviews third-party material, copyright status, datasets, models, and proposed license terms.
- Maintenance owner: owns issues, pull requests, release cadence, and archival decisions after publication.
- Platform support: validates notebooks, containers, hosted services, API workflows, and browser runtime paths when execution is required.
- Security reviewer: checks for secrets, internal endpoints, vulnerable dependencies, and sensitive data.
- Repository owner: keeps the repository structure, manifests, templates, and gates current.

## Release Preparation Checklist

Each item must be complete, marked not applicable with rationale, or escalated before external publication.

- Confirm scope, source location, target release path, and owner.
- Inventory each artifact planned for release.
- Classify each artifact as authored, generated, third-party, dataset, model, dependency, or cached reference.
- Record owner, source URL when public, license, and redistribution disposition.
- Remove or replace anything with unclear ownership or incompatible terms.
- Confirm that datasets and models have explicit approval for the intended use.
- Confirm the supported execution path from a clean user environment.
- Document required credentials, hardware, and known limitations.
- Confirm the maintenance owner, triage cadence, review expectations, and archive policy.
- Confirm contribution terms and issue or pull request templates.
- Confirm a Code of Conduct and a real enforcement route before public community intake.
- Run the source and security gates.
- Record unresolved questions before submission or publication.

## License Posture

Apache-2.0 is the intended external license. Contributions intentionally submitted for inclusion
are accepted under the checked-in Apache-2.0 terms unless a contributor clearly marks the work
as not a contribution. OSRB approval remains a separate prerequisite for external publication.

Apache-2.0 does not automatically make every copied third-party artifact redistributable. Any external image, text, dataset, model, notebook, or cached page must have its own source and license disposition before it is committed.

Do not create a narrative `NOTICE` file as a second source inventory. Add `NOTICE` only when a
bundled work or another legal requirement creates an attribution notice that downstream users
must preserve. Keep it limited to required notices and set `notice_required` in
`RELEASE_STATUS.json` at the same time.

## Execution Evidence

If a course asks users to run code, maintainers must record enough evidence for another maintainer to reproduce the supported path. Evidence may include command output, container/browser harness output, CI logs, or a no-execution rationale.

## Stop Conditions

Stop and escalate when any of these are true:

- source owner is unclear
- license is unknown or incompatible
- dataset or model approval is missing
- internal URL or private process text would ship
- secret, token, credential, private endpoint, or sensitive data appears in tracked files
- required execution path is broken and no approved no-execution rationale exists
- no maintenance owner exists
