# Agent process guardrails

This note is for agents and maintainers working across issues, merge requests, and broad course prose. It turns repeated review feedback into a checklist that can be audited.
Issue anatomy and tracker cadence live in [`issue_standards.md`](issue_standards.md).
Runtime checks live in [`lab_runtime_testing.md`](lab_runtime_testing.md), and the
service-document edit hazard lives in
[`notebook_corruption_prevention.md`](notebook_corruption_prevention.md).

## Start from the tracker

- Use `docs/issue_standards.md` as the issue anatomy and label cadence. Current
  work assumes `web/nemoclaw/` on the CPU service stack, while the repo stays
  shaped as a multi-course bundle.
- Read the issue or MR before editing. If network or auth blocks the read, say that and work from local evidence only.
- Tie the MR to the tracker with `Addresses #N` unless the user explicitly says the change closes the issue. Do not write `Closes #N` for partial hygiene, exploratory prose, or a blast-radius pass.
- Keep the branch name, commit message, and MR note aligned with the issue scope. If the work intentionally touches related issues, name those as related, not solved.

## Contribution authority

- Keep idea intake cheap. A Discussion or structured Issue can carry a question, correction,
  source, or design without requiring code.
- Treat every patch as untrusted input, including patches from maintainers and capable agents.
  Require issue linkage, named surfaces, blast-radius evidence, command results, human ownership,
  risk, rollback, and explicit out-of-scope work.
- Install the hooks, but never claim they secure a repository. Local hooks provide early feedback
  and can be bypassed. Required CI validates the submitted commit; protected refs and environments
  control merge, deploy, and release authority.
- A hook must refuse and explain. It must not rebase, resolve conflicts, force-push, weaken a test,
  or otherwise mutate history to make a contribution pass.
- For contribution, hook, workflow, permission, or release changes, run
  `python3 scripts/validation/contribution_safety_audit.py --self-test` and then the audit itself.
  The JSON report belongs in CI artifacts so a human can inspect the exact boundary that passed.
- For deployment topology, browser proxy, service, storage, privilege, authentication, secret-flow,
  or release-pipeline changes, update `docs/security-architecture.json`, regenerate its SVG, and run
  `python3 scripts/validation/security_architecture_audit.py --self-test` plus the audit. Production
  nodes remain source-backed; local-only Compose services and volumes remain explicitly classified.
- For product scope, data handling, cryptography inventory, release evidence, or lifecycle test-plan
  changes, update `docs/product-design.md`, `docs/release-test-plan.md`, and
  `docs/release-evidence.json` together. Run `python3 scripts/validation/release_evidence_audit.py
  --self-test` and then `python3 scripts/validation/release_evidence_audit.py`. Keep internal ticket
  bodies, program identifiers, scanner details, reviewer records, and approval links outside the repo.

## Course title, abstract, and objectives

- `web/nemoclaw/COURSE_CANON.md` is canonical for the English source course title, abstract, and learning objectives. Do not rewrite, shorten, paraphrase, translate, retitle, or reorder that copy.
- Run `python3 scripts/validation/course_contract.py` after touching the course home, foyer, generated course metadata, title text, abstract text, or learning objectives.
- The required `course_contract` suite in `validate_bundle.py` must fail if this copy drifts. Treat that as a release blocker, not an advisory prose issue.

## Broad prose and taxonomy passes

- Define the vocabulary before rewriting pages. For this course the current split is: NemoClaw is the reference stack, OpenClaw is the agent harness, OpenShell is the sandbox boundary, and the Brev launchable is the hosted course deployment.
- Grep every learner-facing surface for the terms being changed: course pages, generated SKILL descriptors, navigation helpers, edX helper pages, and script docs.
- Avoid replacement framing that creates new buzz. Patterns such as `not X; do Y`, `first-class part`, `peer runtime`, and `closest public sibling` need concrete nouns or should be cut.
- When a title, page order, or generated descriptor changes, update the generator and regenerated SKILL beacon together. Do not hand-edit generated SKILL output without updating its source.
- Run the prose validator on the affected snippets before the full gate when doing taxonomy work.

## Validation ladder

- Always run `git diff --check`.
- Treat `docs/validation/latest.md` and `latest.json` as the current finding inventory.
  Do not maintain a second snapshot of counts or affected files in prose.
- Fix the learner or operator problem. Do not hide a surface, add decorative structure,
  flatten prose into stubs, or remove useful comments only to silence a detector.
- Use advisory findings as review prompts. A lower count is evidence only when the diff is
  clearer, safer, or easier to maintain.
- Run the shared fast ladder with
  `python3 scripts/validation/release_gate.py --tier fast --no-write`; use `--tier ship`
  for the complete deterministic repository gate.
- For governance, contribution, hook, CI, permission, or release changes, run `contribution_safety_audit.py`, its mutation self-test, and the full ship gate.
- For dependency, service image, runtime package, or security-exception changes, run `python3 scripts/security/audit_python_dependencies.py` and `python3 scripts/security/audit_vulnerability_waivers.py` before the full gate.
- For content or navigation changes, run `python3 scripts/skills/skill_consistency.py`, `python3 scripts/validation/validate_layout.py --quiet`, and `python3 scripts/validation/validate_bundle.py --no-write --scope ship`.
- For page title, navigation, or deploy-path changes, run `BUILD_PAGES_LANGS=0 scripts/build/build_pages.sh` before calling the MR ready.
- For Studio, runnable-cell, browser-runtime, or OpenClaw changes, also run the browser/runtime harness named in `AGENT_QUICKSTART.md` and the relevant `scripts/validation/*_audit.py` file.
- For learner-facing code or lab-flow changes, run `learner_flow_audit.py`, its mutation self-test, and `learner_flow_runtime_audit.py` against source and built Pages output. A closure claim needs evidence for disclosure, prerequisite readiness, Run/Stop/Reset, error recovery, and viewport stability; a screenshot of one happy state is insufficient.
- For branch staging, require a passing blocking `test` job, confirm the Pages job SHA matches the live branch head, and probe the deployed course plus both branch manifests. Only paths present in the current classic-Pages artifact may appear in the foyer selector.
- For a stateful browser bug, test the whole lifecycle: enter the state, leave it through a successful sibling result, leave it through an error, remount the component, then reload or navigate. Run that matrix against both source and built Pages output.
- Pair lifecycle gates. A cheap static validator should catch missing selectors, cleanup calls, and CSS contracts; a real browser workflow must prove computed visibility and persisted-state behavior. Neither gate substitutes for the other.

## Visual changes

- Before touching a course image, SVG, diagram, or figure placement, read `web/nemoclaw/assets/SKILL.html` and classify the asset as a theme-aware course/provided SVG or a fixed-white conversion.
- Non-conversion SVGs mount with `fig-embed` / `data-svg-src`; fixed-white conversions use `img` only when provenance marks `connection: "conversion"`.
- Preserve meaningful diagram labels. Remove caption-like prose, contributor/process shorthand, and provenance from learner-facing SVG content; keep captions in page `figcaption` and provenance in `assets/SKILL.html`.
- Preview the rendered result in the active agent harness and show the requester the screenshot, crop, or exact preview artifact path. Verify light and dark theme output when the figure can theme-switch.
- At narrow width, inspect the inline overview and activate the figure lightbox. Labels must remain readable in the enlarged state, horizontal panning must work, and close/Escape controls must remain reachable.
- Run `python3 scripts/validation/figure_audit.py`, `python3 scripts/compliance/source_gate.py`, and `python3 scripts/validation/validate_bundle.py --no-write --scope ship` before calling visual work ready.

## Safe auth and metadata updates

- Do not print token-bearing environment variables. Never run `env | rg TOKEN`, `printenv | grep TOKEN`, or equivalent output-producing probes for GitLab or service credentials.
- Prefer `glab auth status` for GitLab CLI state. If API access is needed and CLI is unavailable, use `git credential fill` in a script that reads the credential and sends it directly to the request without printing the secret.
- If auth fails, report the exact `401`, `403`, host-key, or push-permission error and stop after one careful retry.

## Editing discipline

- Read the current diff before editing. Preserve user changes in touched files.
- Use repo-native tools from WSL for WSL worktrees. Do not use PowerShell `Set-Content` against WSL files.
- If `apply_patch` is unavailable, a short repo-local rewrite script is acceptable, but inspect `git diff` immediately after it runs.
