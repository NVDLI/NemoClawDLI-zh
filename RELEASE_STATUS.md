# Release status

This repository is an internal release candidate for a proposed NVIDIA open-source
publication. External publication remains pending OSRB approval.

| Field | Current state |
|---|---|
| Canonical repository | Internal GitLab |
| External mirror | Not published |
| Intended external license | Apache-2.0 |
| OSRB approval | Pending |
| Required `NOTICE` attributions | None currently identified |

The Apache-2.0 text and contribution terms prepare the proposed external release. Their
presence does not replace OSRB approval or authorize someone to mirror, publish, or announce
this repository externally.

Within course metadata, `released course` means selected for the learner foyer and release
build. It does not mean the repository has been approved for public distribution.

Third-party source and license disposition live in
[`scripts/compliance/docs/source_inventory.json`](scripts/compliance/docs/source_inventory.json)
and the relevant provenance beacons. A `NOTICE` file should exist only when a bundled work or
another legal requirement creates an attribution notice that downstream redistributors must
preserve. If that occurs, set `notice_required` in [`RELEASE_STATUS.json`](RELEASE_STATUS.json)
to `true` and add only the required notices.

After approval and external publication, update the machine-readable state, this document,
the public contribution routes, and the release host controls in one reviewed change.
GitHub Pages and release workflows call the publication guard before any external write, so
`pending-osrb-approval` cannot deploy or prepare a release.
