# Release playbook

This playbook defines how this course bundle moves from internal GitLab development to an external NVIDIA mirror that can accept student reports and later direct student contributions. The repository stays a course packaging and release workspace: authored content, shared services, deployment, validation, and governance move together.

Current state: internal release candidate, with external publication pending OSRB approval. See
[`RELEASE_STATUS.json`](../RELEASE_STATUS.json). Terms such as `released course` elsewhere in the
repository identify courses selected for the learner foyer; they do not assert public publication.
The GitHub Pages and release workflows must run
`contribution_safety_audit.py --require-publication-approved` before external writes.

## Scalable recommendation

Use a staged externalization model:

1. **Internal canonical**: NVIDIA internal GitLab is source of truth. External mirror is off.
2. **External read mirror**: publish a sanitized read mirror. Students can read, fork, and cite. Issues and pull requests stay closed or point to a discussion channel.
3. **External intake**: enable Issues and Discussions. Accept evidence, repros, corrections, and source reports. Merge rights stay internal.
4. **External contribution**: accept pull requests from forks with required checks, owner review, source governance, and release-manager merge.
5. **Release train**: tag public releases, publish Pages from protected refs only, and keep DLI platform deploys internal and manual.

Default rule: **issue-first, patch-second**. Students with domain evidence file structured Issues. Students who can carry a fix through validation open PRs using the structured release process.

## Contribution trust model

[`CONTRIBUTING.md`](../CONTRIBUTING.md) owns intake, submission evidence, signoff, and the
validation ladder. [`issue_standards.md`](issue_standards.md) owns issue shape and tracker
cadence. `README.md` owns maintainer authority; `CODE_OF_CONDUCT.md`, `SUPPORT.md`, and
`DCO.md` own their named public policies. This playbook owns host and release-operator
configuration.

Host settings are not versioned by this repository. Workflow files can request read-only tokens,
environments, and checks, but only a host administrator can activate rulesets, required reviewers,
prevent self-review, and restrict bypass. The operator must verify both halves: repository policy
with `contribution_safety_audit.py`, then live host settings and Rule Insights before public intake
or release.

For the canonical GitLab project, run the read-only live audit before merging governance work and
before each release train:

```bash
python3 scripts/validation/gitlab_governance_audit.py --self-test
python3 scripts/validation/gitlab_governance_audit.py --project "$CI_PROJECT_ID" \
  --report docs/validation/gitlab-governance.json
```

The audit reports every weak host control with its exact setting. Its report is evidence, not a
substitute for the host audit log or a human review of who holds the named roles.

Surface ownership and task-specific gates live in the root `SKILL.html`, `docs/SKILL.html`,
and nearest directory beacon.

## External mirror settings

When mirroring to `nvidia-external`, use internal GitLab as canonical and push mirror protected release refs outward.

Required constraints:

- Mirror only protected branches and release tags until external contribution intake is ready.
- Keep divergent refs protected so mirror failures stop instead of overwriting unexpected external state.
- Use SSH or a scoped release-bot token, not a personal account.
- Protect `main`, `release/*`, and tags on the external host.
- Run `source_gate.py` and `local_path_leak_audit.py` before mirror publication.
- Approve the ancestry strategy before enabling a history-preserving mirror. If internal ancestry is
  not approved for publication, initialize the external repository from the validated release tree
  instead of copying internal commit history.
- Do not mirror CI secrets, DLI deploy credentials, model keys, Cloudflare headers, or private launch URLs.

Branch policy:

| Ref | Source | External writes | Purpose |
|---|---|---|---|
| `main` | internal protected branch | no direct pushes | accepted source |
| `release/*` | release manager | no direct pushes | frozen public release train |
| `student/*` | forks | contributors write in forks | student work in progress |
| `localize/*` | contributor-owned | no protected-ref access | sparse same-branch locale work reviewed with Localization Studio |
| `v*` tags | release manager | no direct pushes | immutable public releases |

## External GitHub settings

Use these when the mirror lands on GitHub:

- Enable Issues at External intake.
- Enable Discussions for questions, learning friction, and broad ideas that are not actionable defects.
- Enable Projects for the triage/release board.
- Add `.github/CODEOWNERS` only after real NVIDIA org/team handles exist. Owners should cover `web/`, `cpu/`, `deploy/`, `scripts/`, `docs/`, and source governance paths.
- Create an active branch ruleset for `main` and `release/*`. Require a pull request, one approval,
  dismissal of stale approvals, approval of the most recent push by someone else, resolved review
  threads, and the strict `test` status from the `pages` workflow. Block deletion and force pushes.
  Give no person an always-bypass lane; if automation needs bypass, scope it to a named GitHub App.
- Create an active tag ruleset for `v*`. Restrict tag creation, update, and deletion to the release
  manager or release App. A workflow consumes an existing protected tag; it does not mint one.
- Use GitHub Actions environments for public Pages. Use required reviewers for production and concurrency so only one deploy runs at a time.
- Configure both `github-pages` and `github-release` with required reviewers, prevent self-review,
  disallow administrator bypass, and restrict deployment branches or tags. Review environment and
  ruleset bypass events in Rule Insights after each release.
- Keep fork PR jobs on read-only tokens. Do not expose model, DLI, Cloudflare, or deployment secrets to forked pull requests.

## Public GitHub security baseline

Enable the dependency graph, dependency review, Dependabot alerts, code scanning,
secret scanning, push protection, private vulnerability reporting, and protected
deployment environments before public intake. Fork jobs remain read-only and receive no
secrets. Keep private runtime names, credentials, internal topology, confidential findings,
and restricted scanner output in approved internal systems.

Repository dependency floors, exact locks, SCA layers, waiver handling, SBOM boundaries,
and the hardening backlog live in [`dependency_security.md`](dependency_security.md).
Publication assets and retention live in [`release_artifacts.md`](release_artifacts.md).
The complete release acceptance matrix lives in
[`release-test-plan.md`](release-test-plan.md).

## Internal GitLab settings

Use these while GitLab remains canonical:

- Protect `main`, `nemoclaw-only`, `release/*`, and tags.
- Set `main` push access to No one, disable force push, and allow maintainers to merge only through MRs.
- Require a successful pipeline and resolved discussions. In a one-operator project, require the
  protected manual `human_review` job after the exact commit's live preview smoke; restrict its
  environment to named human operators. With two active maintainers, prefer an independent MR
  approval and keep the protected action as release-owner acceptance.
- Protect `v*` tags and name the eligible human release operators explicitly instead of granting
  tag creation to every Maintainer-role bot.
- When pipeline-triggerer self-approval is enabled for one operator, make the `v*` creator set
  exactly match that sole production deployer. Add or remove operators across tag creation,
  protected production, deployment approval, and human review as one audited change.
- Keep production Pages deploy manual and protect the `production` environment with explicit
  human deployers. In a one-operator project, an environment approval rule naming that sole
  operator must also allow the pipeline triggerer to approve; otherwise every deployment
  deadlocks. When another active operator can supply independent review, disable self-approval
  and require that reviewer. Review environments remain isolated, manual, and short-lived
  without production authority.
- Keep branch preview deploys manual, isolated under branch slug paths, built with production root from a protected ref, and blocked by the required test gate. On classic Pages, expose only preview paths present in the latest combined artifact.
- Use templates in `.gitlab/issue_templates/` and `.gitlab/merge_request_templates/`.
- Use labels and milestones as the project-management source. Mirror the same taxonomy to GitHub.
- Keep `docs/issue_standards.md` aligned with tracker labels, issue templates, and MR templates.

## Release workflow

Issue and patch flow live in [`issue_standards.md`](issue_standards.md) and
[`CONTRIBUTING.md`](../CONTRIBUTING.md). Tag, artifact, promotion, and recovery steps live in
[`release_artifacts.md`](release_artifacts.md). The acceptance sequence and evidence owners live
in [`release-test-plan.md`](release-test-plan.md). Use those contracts rather than maintaining a
second checklist here.

## CI/CD policy

`scripts/validation/release_gate.py` owns the deterministic command sequence used by GitLab,
GitHub Pages, the protected release workflow, and local contributors:

```bash
python3 scripts/validation/release_gate.py --tier fast --no-write --changed-since origin/main
python3 scripts/validation/release_gate.py --tier ship --no-write --changed-since origin/main
```

Proposal gates always run complete current-tree audits. They skip only unaffected mutation suites,
record per-command timing in CI, and keep exact history/metadata checks in host context. Local
pre-push may reuse an identical clean-commit success. CI never trusts that workstation cache.
Release-candidate and tagged-release workflows omit `--changed-since` and run every mutation.

Pages builds normally regenerate the validation report. A downstream build job may reuse the
required upstream report only after checking its schema, commit, ship scope, required findings,
suite status, and clean source tree. This removes a duplicate full scan without weakening artifact
authorization.

Every shared gate verifies committed material snapshots and full SHA-256 provenance without network
access. Host workflows add bounded live-source retries: schedules and protected releases remain
strict, while production-ref pushes may tolerate only classified transient reachability. Drift,
malformed content, unsafe redirects, TLS failures, and committed-provenance mismatches always fail.
Jobs retry runner and control-plane failures, never validation script failures.

Host workflows also enforce submission shape, commit signoff ranges, protected tags, deployment
approval, and post-deploy smoke because those checks require host context. The full automated,
browser, service, and external-evidence matrix lives in
[`release-test-plan.md`](release-test-plan.md). Dependency resolution and SCA procedures live
in [`dependency_security.md`](dependency_security.md). Pages staging and deployment mechanics
live in [`pages_deploy.md`](pages_deploy.md). Containerized browser and Compose execution live
in [`lab_runtime_testing.md`](lab_runtime_testing.md). Tracker labels and discussion routing
live in [`issue_standards.md`](issue_standards.md).

## Kickstart settings checklist

Before public mirror:

- [ ] Public README explains surface separation, local bring-up, and contribution routes.
- [ ] `CONTRIBUTING.md` has issue-first and structured patch paths.
- [ ] This playbook is linked from docs SKILL and root SKILL.
- [ ] GitLab issue/MR templates exist.
- [ ] GitHub issue/PR templates exist.
- [x] Code of Conduct and a public-safe private platform reporting route are repository-defined; verify host moderation before intake.
- [ ] External repository protects `main` and `release/*`.
- [ ] Active `v*` tag rules restrict create, update, and deletion.
- [ ] Release workflow rejects lightweight tags and packages only annotated SemVer tags contained in `main`.
- [ ] Immutable releases are enabled before the first public version is published.
- [ ] External repository has required checks mapped to the static gate.
- [ ] Dependency graph, Dependabot alerts, dependency review, code scanning, and secret scanning are enabled or explicitly deferred with a reason.
- [x] Repo-owned Dependabot, dependency-review, and CodeQL workflows exist with immutable action pins and fork-safe permissions.
- [ ] Host dependency graph, alerts, code-scanning upload, secret scanning, and push protection are enabled and smoke-tested.
- [ ] Release draft contains the deterministic archive, manifest, resolved-environment SBOM, and `SHA256SUMS`.
- [ ] Image SCA strategy is defined for public-safe images and NVIDIA/internal images separately.
- [ ] External repository has Discussions enabled, with pinned welcome guidance.
- [ ] CODEOWNERS is added after org/team handles are real.
- [ ] Mirror is protected-branch/tag-only until public contribution intake is ready.
- [ ] `source_gate.py` and `local_path_leak_audit.py` pass on the mirrored ref; ancestry strategy is approved.
- [ ] Public Pages deploy uses environment protection and concurrency.
- [ ] `github-pages` and `github-release` require a reviewer, prevent self-review, and disallow admin bypass.
- [ ] A test release produced a Draft release, checksum, validation report, and Rule Insights record.

Before student PR intake:

- [ ] Fork PRs cannot access secrets.
- [ ] Dependency-review check blocks vulnerable dependency additions.
- [ ] Secret scanning push protection is enabled where available; custom patterns are approved before use.
- [ ] PR template asks for issue link, surfaces touched, validation, and source/licensing impact.
- [x] Public support policy states best-effort triage without an unsupported response SLA.
- [x] DCO 1.1 is documented and enforced over every proposed commit range.
- [ ] Labels and milestones are mirrored between GitLab and GitHub.
- [ ] Release note owner exists for each milestone.
- [ ] Security/private reports have a non-public contact path.

## Sources used

- GitLab repository mirroring supports private-to-open-source mirroring, protected-branch-only mirroring, and divergent-ref protection.
- GitLab description templates live under `.gitlab/issue_templates/` and `.gitlab/merge_request_templates/`.
- GitHub CODEOWNERS can request owner review and can be required by branch protection.
- GitHub Actions deployments support environments, protection rules, concurrency, and deployment history.
- GitHub Discussions is for transparent community conversations that are not tracked code work.
- GitHub Projects can provide board-style planning for issues and pull requests.
- GitHub dependency graph is available for public repositories by default and can export SBOMs.
- GitHub dependency review and dependency-review-action are available for public repositories and can block vulnerable dependency additions.
- GitHub code scanning is available for public repositories, with CodeQL or SARIF-uploaded third-party tools.
- GitHub secret scanning runs automatically for public repositories and can be extended with custom patterns and validity checks where available.

Operator references:

- [GitHub ruleset rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets)
- [GitHub ruleset management and Rule Insights](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/managing-rulesets-for-a-repository)
- [GitHub deployment environments](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments)
- [GitHub token least-privilege guidance](https://docs.github.com/en/actions/how-tos/security-for-github-actions/security-guides/use-github_token-in-workflows)
- [GitHub fork pull-request security behavior](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)
- [GitHub private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing/privately-reporting-a-security-vulnerability)
