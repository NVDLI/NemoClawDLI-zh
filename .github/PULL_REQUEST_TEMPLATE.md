## Summary

What changed and why?

## Issue link

Addresses #

## Current release target

- Course: `web/nemoclaw/` unless this is bundle-wide
- Runtime: CPU service stack (`cpu/`, `workspace/`, `deploy/`) unless stated otherwise
- Bundle scope: course-specific or bundle-wide

## Surfaces touched

- [ ] `web/`
- [ ] `cpu/`
- [ ] `workspace/`
- [ ] `deploy/`
- [ ] `scripts/`
- [ ] `docs/`
- [ ] `materials/source governance`

## Blast radius checked

Describe related files, generated beacons, docs, validators, and runtime paths checked.

## Validation evidence

Record `PASS`, `FAIL`, or `BLOCKED` beside each command you actually ran. A checked box without
the result is not evidence.

- [ ] `python3 scripts/validation/release_gate.py --tier fast --no-write`
- [ ] `python3 scripts/validation/release_gate.py --tier ship` for cross-cutting or release work
- [ ] Browser/runtime check, if page JS, Studio, OpenClaw, or runnable cells changed
- [ ] Build check, if navigation, deploy path, or Pages output changed

## Security and source impact

Does this change dependencies, permissions, workflows, secrets handling, external sources,
licensing, generated assets, or release/deploy authority? State `none` only after checking.

## Human ownership

Who reviewed the complete diff and can explain every surviving line? Who owns merge and release
approval? Agent output does not satisfy this section.

Every commit must include a matching `Signed-off-by` trailer under [`DCO.md`](../DCO.md). CI checks
the complete pull-request range; a PR-level checkbox does not replace commit-level signoff.

If this targets another unmerged proposal branch, state the maintainer-owned fast-forward or
rebase/cherry-pick plan that preserves the original signed commits. Do not use a host-generated squash
or merge commit for a stacked pull request.

## Release notes

Learner-facing:

Runtime/deploy:

Governance/process:

## Risk and rollback

What could regress? What exact commit, flag, workflow, or artifact restores the previous state?

## Out of scope

Name adjacent work deliberately excluded from this change.
