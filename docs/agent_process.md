# Agent process guardrails

This note is for agents and maintainers working across issues, merge requests, and broad course prose. It turns repeated review feedback into a checklist that can be audited.

## Start from the tracker

- Read the issue or MR before editing. If network or auth blocks the read, say that and work from local evidence only.
- Tie the MR to the tracker with `Addresses #N` unless the user explicitly says the change closes the issue. Do not write `Closes #N` for partial hygiene, exploratory prose, or a blast-radius pass.
- Keep the branch name, commit message, and MR note aligned with the issue scope. If the work intentionally touches related issues, name those as related, not solved.

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
- For content or navigation changes, run `python3 scripts/skills/skill_consistency.py`, `python3 scripts/validation/validate_layout.py --quiet`, and `python3 scripts/validation/validate_bundle.py --no-write --scope ship`.
- For page title, navigation, or deploy-path changes, run `BUILD_PAGES_LANGS=0 scripts/build/build_pages.sh` before calling the MR ready.
- For Studio, runnable-cell, browser-runtime, or OpenClaw changes, also run the browser/runtime harness named in `AGENT_QUICKSTART.md` and the relevant `scripts/validation/*_audit.py` file.

## Safe auth and metadata updates

- Do not print token-bearing environment variables. Never run `env | rg TOKEN`, `printenv | grep TOKEN`, or equivalent output-producing probes for GitLab or service credentials.
- Prefer `glab auth status` for GitLab CLI state. If API access is needed and CLI is unavailable, use `git credential fill` in a script that reads the credential and sends it directly to the request without printing the secret.
- If auth fails, report the exact `401`, `403`, host-key, or push-permission error and stop after one careful retry.

## Editing discipline

- Read the current diff before editing. Preserve user changes in touched files.
- Use repo-native tools from WSL for WSL worktrees. Do not use PowerShell `Set-Content` against WSL files.
- If `apply_patch` is unavailable, a short repo-local rewrite script is acceptable, but inspect `git diff` immediately after it runs.
