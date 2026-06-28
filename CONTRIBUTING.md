# Contributing

This repository is the open-source release workspace for NVIDIA DLI course material.
It packages authored content, shared services, deployment, and validation in one release
tree. Content is organized by execution surface: `web/` is browser-only and remote-service
aware, `cpu/` is the shared microservice stack, and `deploy/` is the operator surface for
standing the bundle up on DLI platform or local compute.

## Two Contribution Paths

The easy path contributes knowledge. The guarded path changes the release.

Use the issue path when you have expertise about the course, platform, security model,
source material, or learner experience but do not already have a release-ready patch.
File a focused Issue with the affected files or URLs, the observed behavior, the expected
behavior, and any source or runtime evidence. The issue anatomy and cadence live in
[`docs/issue_standards.md`](docs/issue_standards.md). This is the preferred path for
cross-cutting course claims, pedagogy, vendor/source concerns, and deployment assumptions.
Use [Discussions](https://github.com/NVIDIA/NemoClawDLIOS/discussions) for questions,
brainstorms, learning friction, and ideas that do not yet have a concrete defect. Neither
route requires code. Report vulnerabilities privately through [`SECURITY.md`](SECURITY.md).

Use the direct patch path when you can carry the change through the structured release
process. The full release and external-mirror model lives in [`docs/release_playbook.md`](docs/release_playbook.md). A direct MR should update the source, declared blast-radius files, and validators
when the failure class should not recur. Link the tracker with `Addresses #N` unless the
change fully closes the issue.

A patch is not trusted because a person or agent produced it, or because it passes one local
command. It becomes eligible to merge only after required CI runs on the submitted commit,
the MR or PR records concrete evidence and remaining risk, review ownership is clear, and
protected-ref policy accepts it. Release and deployment writes require a separate protected
operator action.

Keep the compact submission contract at the top of an MR. GitLab exposes only the leading
description window to CI, so Summary, Issue link, Surfaces touched, Blast radius checked,
Validation evidence, Human ownership, Risk and rollback, and Out of scope must appear before
long rationale, screenshots, or logs.

## Orientation

Read [`AGENT_QUICKSTART.md`](AGENT_QUICKSTART.md) first. Every directory carries a
`SKILL.html` whose `skill-meta` JSON block is the machine-readable brain for that
directory. [`SKILL_CONTRACT.md`](SKILL_CONTRACT.md) specifies that format and
[`QUALITY_DIRECTIVES.md`](QUALITY_DIRECTIVES.md) sets the content bar.

## Structured Release Process

1. Start from a clean branch for one coherent release concern.
2. Read the relevant Issue or MR before editing.
3. Update the source surface and every declared blast-radius file.
4. Keep course title, abstract, and objectives verbatim from [`web/nemoclaw/COURSE_CANON.md`](web/nemoclaw/COURSE_CANON.md).
5. Add or update a validator when the same class of problem should not recur.
6. Run the validation ladder below.
7. Open an MR that names the issue relationship and lists validation results.

## Install the Hooks

```bash
bash scripts/build/install-hooks.sh
```

This resolves Git's real hook directory, including linked worktrees, then installs two hooks:

- `pre-commit`: protected-branch refusal, contribution-boundary audit, corruption guard,
  canvas-HTML validation, and page-runtime smoke checks.
- `pre-push`: behind-branch refusal, mutation-tested contribution and learner-flow contracts,
  SKILL consistency, source/security checks, layout validation, and the release gate.

A local hook is feedback, not authority. Hooks are intentionally early and actionable, but
Git allows them to be bypassed. Required CI, branch or tag rulesets, protected human review,
and protected release actions close that gap.

## Validate Before Pushing

```bash
python3 scripts/validation/validate_layout.py --quiet
python3 scripts/skills/skill_consistency.py
python3 scripts/validation/contribution_safety_audit.py --self-test
python3 scripts/validation/contribution_safety_audit.py
python3 scripts/compliance/source_gate.py
bash scripts/runtime/run_engine.sh --self-test
python3 scripts/validation/validate_bundle.py --scope ship
python3 scripts/validation/tenets.py --check
```

Service-stack notebook tests need the lab services running:

```bash
python3 workspace/run_tests.py services --notebook <notebook>
```

For browser or Studio changes, also run the browser harness described in
[`docs/lab_runtime_testing.md`](docs/lab_runtime_testing.md).

## Conventions

The full operating creed is projected into the root `SKILL.html` skill-meta. Run
`python3 scripts/validation/tenets.py` to inspect the gate that enforces it. Highlights:

- Edit content in place. Scratch work goes to `/tmp` and is never committed.
- Authored prose avoids em-dashes. Rewrite the sentence rather than swap punctuation.
- `web/` stays browser-only and cannot assume student-provisioned microservices.
- `cpu/` owns the shared service stack a course may call through declared routes.
- `deploy/` owns compose and nginx configuration.
- Do not commit lab-generated runtime output, caches, or the `public/` Pages build.

## Contribution Terms

This repository is licensed under Apache-2.0. Unless you clearly mark a submission as
`Not a Contribution`, any contribution intentionally submitted for inclusion is offered
under Apache-2.0, with the contribution terms in [`LICENSE.md`](LICENSE.md).

Do not submit material you do not have the right to contribute. Third-party text, images,
datasets, model artifacts, copied examples, cached web pages, and generated assets need
source and license disposition before they are committed. The governing process is
[`scripts/compliance/docs/vendor_policy.md`](scripts/compliance/docs/vendor_policy.md), and the required gate is:

```bash
python3 scripts/compliance/source_gate.py
```
