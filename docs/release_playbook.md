# Release playbook

This playbook defines how this course bundle moves from internal GitLab development to an external NVIDIA mirror that can accept student reports and later direct student contributions. The repository stays a course packaging and release workspace: authored content, shared services, deployment, validation, and governance move together.

Current state: internal release candidate, with external publication pending OSRB approval. See
[`RELEASE_STATUS.md`](../RELEASE_STATUS.md). Terms such as `released course` elsewhere in the
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

The repository separates the cost of proposing knowledge from the authority to change a release.

| Stage | Default access | Required evidence | Authority |
|---|---|---|---|
| Discussion | open | question, friction, or idea | none; no code changes |
| Issue | open and structured | location, current/expected behavior, safe evidence | maintainer triage |
| Branch or fork | contributor-owned | focused patch linked to an Issue | no protected-ref access |
| PR or MR | untrusted proposal | surfaces, blast radius, commands and results, owner, risk, rollback | required CI plus human review |
| Merge | restricted | current approved diff and required checks | protected branch or ruleset |
| Pages or release | separately restricted | immutable SHA or tag, built artifact, smoke evidence | protected environment and release manager |

An agent, novice, or maintainer may propose any of these artifacts. Identity or tool quality never
substitutes for evidence. Local hooks push back early but are bypassable. CI validates the submitted
commit. Protected refs, tag rules, and environments hold the irreversible authority.

Host settings are not versioned by this repository. Workflow files can request read-only tokens,
environments, and checks, but only a host administrator can activate rulesets, required reviewers,
prevent self-review, and restrict bypass. The operator must verify both halves: repository policy
with `contribution_safety_audit.py`, then live host settings and Rule Insights before public intake
or release.

For the canonical GitLab project, run the read-only live audit before merging governance work and
before each release train:

```bash
python3 scripts/validation/gitlab_governance_audit.py --self-test
python3 scripts/validation/gitlab_governance_audit.py --project 364401 \
  --report docs/validation/gitlab-governance.json
```

The audit reports every weak host control with its exact setting. Its report is evidence, not a
substitute for the host audit log or a human review of who holds the named roles.

Current issue and MR templates assume `web/nemoclaw/` on the CPU service stack
(`cpu/`, `workspace/`, and `deploy/`) as the active release target. Keep that
explicit in each issue, then mark whether the finding is course-specific or
bundle-wide so the same tracker can scale to future courses.

## Surface ownership

| Surface | Owner lane | Contribution shape | Required gate |
|---|---|---|---|
| `web/` | course content | wording, glossary, learner flow, accessibility, page runtime | `validate_bundle.py --scope ship`, browser harness for runtime |
| `cpu/` | lab services | service docs, notebook repros, gateway behavior | service notebook test or documented repro |
| `deploy/` | release engineering | local startup, DLI platform route, nginx/proxy behavior | compose parse, `run_engine.sh --self-test`, deploy preview if available |
| `scripts/` | tooling | validator, build, runtime harness | targeted script test plus ship gate |
| `web/nemoclaw/mats/` | source governance | citation, provenance, license correction | `source_gate.py`, materials pull/check when available |
| `docs/` | maintainer docs | process, release, contribution docs | `skill_consistency.py`, `validate_layout.py` |

A PR should touch one coherent release concern. A deploy path change can touch `deploy/`, runtime projection, build output, docs, and validators. A wording fix should not.

## External mirror settings

When mirroring to `nvidia-external`, use internal GitLab as canonical and push mirror protected release refs outward.

Required constraints:

- Mirror only protected branches and release tags until external contribution intake is ready.
- Keep divergent refs protected so mirror failures stop instead of overwriting unexpected external state.
- Use SSH or a scoped release-bot token, not a personal account.
- Protect `main`, `release/*`, and tags on the external host.
- Run `source_gate.py` before mirror publication.
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

When the external mirror is public on GitHub, use GitHub-native security features
for public intake and keep NVIDIA-hosted support services for private runtime,
internal registries, confidential advisories, and DLI/Brev deployment evidence.
Do not move secrets, launch URLs, NGC credentials, Cloudflare headers, or private
scanner output to the public mirror.

Baseline for public GitHub availability:

- Enable and monitor the dependency graph. Public repositories have dependency
  graph support by default, and the graph can show direct/transitive dependency
  paths, vulnerable packages, licenses, and SBOM export.
- Enable Dependabot alerts and assign ownership. Dependabot alerts scan default
  branch dependency data when advisory data changes or the dependency graph
  changes; use them for public alert visibility, but keep repo-local SCA because
  not every advisory, transitive path, image layer, or runtime install is covered.
- Add `dependabot.yml` after the mirror has stable branch protection. Start with
  `pip`, `github-actions`, and Docker ecosystem updates. Use grouped updates and
  labels to avoid notification floods.
- Require `dependency-review-action` on pull requests that change manifests or
  lock files. For public repositories the action can enforce dependency review;
  configure it to fail on vulnerable additions and to honor license allow/deny
  policy when that policy is defined.
- Enable CodeQL/code scanning. Public repositories can use code scanning; upload
  SARIF from third-party tools if CodeQL does not cover a check. Treat code
  scanning as complementary to repo validators, not a replacement.
- Enable secret scanning and push protection. Public repositories get secret
  scanning automatically for supported patterns; add custom patterns only after
  NVIDIA/org-specific token formats are approved for that public repo. Rotate
  leaked credentials immediately; history cleanup is secondary after revocation.
- Keep `SECURITY.md` or the GitHub private vulnerability reporting path clear
  before public intake. Security reports should not go through normal Issues.
- Publish or retain SBOM artifacts from CI. Prefer CycloneDX JSON from the
  resolved environment, and upload/submit dependency data where the host supports
  it. If dependency submission and dependency review both run, run submission
  first or configure retries so PR review does not race missing snapshots.

NVIDIA-hosted support remains appropriate when any of these are true:

- The scan needs private base images, NGC access, internal package indexes, or
  DLI/Brev deployment credentials.
- The report contains non-public component names, private URLs, customer data,
  internal service topology, or sensitive exploit detail.
- The job requires privileged container behavior such as the OpenClaw/OpenShell
  runtime path, Docker socket access, or GPU/CUDA image assembly.
- A finding needs confidential triage before the public mirror can safely show it.

## Security hardening roadmap

The current repo-local guardrails are the floor: fast dependency floor audit,
waiver audit, resolved-environment SCA, SBOM artifacts, source gate, and ship
validation. Work beyond that should be split into small MRs with clear ownership.

| Step | Public GitHub path | NVIDIA/internal path | Notes |
|---|---|---|---|
| Reproducible Python resolution | Add lock or constraints and Dependabot update policy | Use internal CI cache or build image as reference resolver | Reduces drift between local, CI, and lab image. |
| Image SCA | Build public-safe images and scan with Trivy/Grype/OSV, upload SARIF where useful | Scan NGC/private/DLI images in internal CI or registry tooling | Do not publish private layer names or credentials. |
| Dependency review | Require `dependency-review-action` on PRs | Keep GitLab `security_deep_sca` for canonical branch until mirror becomes source | GitHub review is PR-diff oriented; deep SCA is resolved-env oriented. |
| Code scanning | Enable CodeQL default setup plus SARIF uploads for extra tools | Run proprietary or NVIDIA-hosted checks internally when rules are not public-safe | Public alerts should be actionable without exposing private topology. |
| Secret scanning | Use GitHub secret scanning, push protection, and approved custom patterns | Keep internal secret scans for NVIDIA/private token families | Rotate first; do not rely on history rewriting as mitigation. |
| Waivers/VEX | Keep `vulnerability-waivers.json`; consider VEX only if downstream consumers need machine-readable non-affected status | Keep confidential exceptions internal until safe to disclose | Waivers must expire and name owner/source. |
| Governance | CODEOWNERS + protected branches + required checks | GitLab protected refs and confidential issue workflow remain canonical | Add external CODEOWNERS only when real org/team handles exist. |

Legitimate stopping points:

- Do not force full image builds on every documentation PR; schedule them, run them
  on dependency/runtime/image changes, or use cached signed build outputs.
- Do not publish scanner reports that disclose private image names, internal URLs,
  or exploit paths. Summarize public-safe status and keep evidence internal.
- Do not add broad Dependabot automation until branch protection, labels, owners,
  and triage capacity exist. Otherwise update noise hides real risk.
- Do not create permanent waivers for unfixed upstream vulnerabilities. Use
  time-boxed waivers or remove the dependency when the package is unused.

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

## Workflow abstractions

### Intake workflow

1. **Question or discussion**: learner confusion, unclear concept, broad idea, request for explanation.
2. **Issue**: reproducible defect, source correction, content ambiguity, accessibility issue, security/privacy concern.
3. **Triage**: maintainer labels by area, kind, state, severity, and risk.
4. **Decision**: accepted, needs evidence, duplicate, not planned, external-source blocked, or security-private.
5. **Patch**: contributor or maintainer opens PR/MR linked with `Addresses #N`.
6. **Validation**: required gate passes, evidence attached, source/license checked.
7. **Merge**: release manager merges after owner review.
8. **Release**: next release train picks the merged change by milestone.

### Patch workflow

Every PR/MR must answer:

- What issue does this address?
- Which surfaces changed?
- What blast radius was checked?
- Which validators ran?
- Does this touch title, abstract, objectives, source/vendor material, secrets, deployment, or learner runtime?
- What remains out of scope?

### Release workflow

Use milestones as release trains:

| Milestone | Purpose | Exit criteria |
|---|---|---|
| `next-patch` | docs, content, validation, small source metadata fixes | required checks pass, no runtime change |
| `next-minor` | new page behavior, deployment shape, contribution workflow | browser/build checks pass, notes drafted |
| `platform-sync` | DLI platform deploy alignment | compose/proxy checks pass, manual deploy evidence |
| `external-ready` | public mirror readiness | source gate clean, templates present, README/CONTRIBUTING coherent |

Release checklist:

1. Confirm `web/nemoclaw/COURSE_CANON.md` unchanged unless formal course-governance approval exists.
2. Run static gate and browser gate for runtime changes.
3. Run `source_gate.py` and confirm no private URLs or provenance gaps.
4. Build Pages with `BUILD_PAGES_LANGS=0 scripts/build/build_pages.sh`.
5. Confirm release foyer surfaces only released courses.
6. Confirm branch/tag protection and mirror direction.
7. Tag release from protected source.
8. Publish release notes grouped by learner-facing, runtime/deploy, governance, and known issues.

### GitHub release runbook

The checked-in `.github/workflows/release.yml` prepares a release but cannot authorize one.
The tag, artifact, retention, and recovery contract lives in
[`docs/release_artifacts.md`](release_artifacts.md).

1. Merge the release candidate through the protected `main` ruleset. Required `pages / test` must
   pass on the final reviewed SHA.
2. Have a release manager create a protected annotated semantic tag such as `v1.2.3` on a commit
   contained in `main`. Do not retarget, delete, or reuse an existing release tag.
3. Run the `release` workflow manually and provide that tag. The read-only job verifies the tag,
   runs the full static/security gate, builds Pages without live material drift, creates a stable
   versioned tar archive, release manifest, resolved-environment CycloneDX SBOM, `SHA256SUMS`, and
   operator-only validation evidence.
4. The write job waits on the protected `github-release` environment. A reviewer other than the
   initiator checks the SHA, tag, validation artifact, checksum, known issues, and release notes.
5. Approval grants `contents: write` only to the final job. It creates or refreshes a **Draft release**.
   The workflow never publishes a release directly.
6. A release manager reviews the draft, edits generated notes into learner-facing, runtime/deploy,
   governance, and known-issue sections, verifies attached checksums, then publishes it in GitHub.
7. Confirm the release and Pages deployment histories, inspect Rule Insights for denied or bypassed
   operations, and record the release URL in the milestone. Any bypass needs an owner and rationale.

Enable immutable releases on the external repository before the first publication. Build the draft
and attach every asset before publishing because immutable release assets cannot be replaced later.

If validation fails, fix through a new Issue-linked PR and create a new tag after merge. Never move a
published tag, weaken a required check, approve your own environment job, or publish an artifact built
from an unreviewed branch.

## CI/CD policy

| Layer | Runs on | Blocks merge | Purpose |
|---|---|---|---|
| Static gate | every branch/PR | yes | structure, links, SKILL, source, course contract |
| Dependency floor gate | every branch/PR | yes | prevent known vulnerable direct floors/pins from entering manifests |
| Waiver gate | every branch/PR | yes | require owned, sourced, unexpired vulnerability exceptions |
| Resolved-environment SCA | schedules, dependency/runtime changes, manual MR job | yes when dependency graph changes; otherwise advisory/manual | install workspace requirements, run `pip-audit --local --strict`, emit CycloneDX SBOM |
| Image SCA | schedules, image/base/runtime changes, release candidates | yes for release candidates; too heavy for every prose PR | scan built service images and base layers |
| Browser/runtime gate | runtime, Studio, OpenClaw, page JS changes | yes when touched | page execution and visual/runtime smoke |
| Deployment gate | protected release branches and manual deploys | release manager | Pages and DLI platform evidence |

Required external PR checks:

```bash
python3 scripts/validation/validate_layout.py --quiet
python3 scripts/skills/skill_consistency.py
python3 scripts/skills/skill_contract.py
python3 scripts/compliance/source_gate.py
python3 scripts/security/audit_python_dependencies.py
python3 scripts/security/audit_vulnerability_waivers.py
bash scripts/runtime/run_engine.sh --self-test
python3 scripts/validation/validate_bundle.py --scope ship
```

For dependency changes, also run the resolved-environment SCA job or equivalent:

```bash
python3 -m venv .sca-venv
.sca-venv/bin/python -m pip install --upgrade pip setuptools wheel
.sca-venv/bin/python -m pip install -r workspace/requirements.txt
.sca-venv/bin/python -m pip install pip-audit cyclonedx-bom
PATH="$PWD/.sca-venv/bin:$PATH" .sca-venv/bin/python scripts/security/run_full_sca.py --execute --python-local --cyclonedx-env --out-dir scripts/security/reports/deep-workspace
```

For page runtime or Studio changes:

```bash
scripts/runtime/browser_env_probe.sh
CONTAINER_ENGINE=podman scripts/runtime/lab_runtime_test.sh --render-only
```

For deployment changes, parse compose YAML and run Compose config where the plugin exists:

```bash
python3 - <<'PY'
from pathlib import Path
import yaml
for f in Path('deploy').glob('docker-compose*.yml'):
    yaml.safe_load(f.read_text())
    print('yaml ok', f)
PY
```

```bash
COMPOSE_PROJECT_NAME=task1 HOST_PROJECT_DIR=$PWD \
  python3 -m podman_compose -f deploy/docker-compose.yml -f deploy/docker-compose.override.yml config
```

Use `docker compose` or `podman compose` only when `scripts/runtime/browser_env_probe.sh`
shows that native Compose is installed. Docker may exist without Compose v2, and
Podman may exist without `podman compose`; that is why the probe is the first step.

## Label taxonomy

Area labels: `area:web`, `area:cpu`, `area:deploy`, `area:scripts`, `area:docs`, `area:materials`, `area:security`, `area:translation`.

Kind labels: `kind:bug`, `kind:course-content`, `kind:source-correction`, `kind:accessibility`, `kind:question`, `kind:feature`, `kind:release`, `kind:validation`.

State labels: `state:needs-triage`, `state:needs-evidence`, `state:accepted`, `state:blocked-external-source`, `state:blocked-platform`, `state:ready-for-review`, `state:needs-release-note`.

Risk labels: `risk:learner-facing`, `risk:deployment`, `risk:security-privacy`, `risk:license-source`, `risk:generated-output`.

Severity labels: `severity:blocker`, `severity:major`, `severity:minor`, `severity:advisory`.

Board columns: Needs triage, Needs evidence, Accepted, In progress, Review, Ready for release, Released, Closed no action.

## Engagement model

Use Discussions for learning and community signal. Use Issues for tracked work.

Recommended discussion categories: Announcements, Questions, Course feedback, Ideas, Show and tell, Troubleshooting.

Convert to Issue when a discussion identifies a reproducible defect, concrete source correction, course wording problem with a file/page, or validated accessibility/runtime issue. Keep broad learning help and future brainstorming in Discussions.

Response standard:

- Acknowledge with route, not promises.
- Ask for exact page, runtime, command output, or source citation when missing.
- Link relevant docs or validation command.
- Do not ask students to expose API keys, tokens, private DLI URLs, or Cloudflare headers.

## Kickstart settings checklist

Before public mirror:

- [ ] Public README explains surface separation, local bring-up, and contribution routes.
- [ ] `CONTRIBUTING.md` has issue-first and structured patch paths.
- [ ] This playbook is linked from docs SKILL and root SKILL.
- [ ] GitLab issue/MR templates exist.
- [ ] GitHub issue/PR templates exist.
- [ ] Code of Conduct and its enforcement route are approved before public community intake.
- [ ] External repository protects `main` and `release/*`.
- [ ] Active `v*` tag rules restrict create, update, and deletion.
- [ ] Release workflow rejects lightweight tags and packages only annotated SemVer tags contained in `main`.
- [ ] Immutable releases are enabled before the first public version is published.
- [ ] External repository has required checks mapped to the static gate.
- [ ] Dependency graph, Dependabot alerts, dependency review, code scanning, and secret scanning are enabled or explicitly deferred with a reason.
- [ ] `dependabot.yml` exists for public-safe ecosystems after owners and labels exist.
- [ ] Release draft contains the deterministic archive, manifest, resolved-environment SBOM, and `SHA256SUMS`.
- [ ] Image SCA strategy is defined for public-safe images and NVIDIA/internal images separately.
- [ ] External repository has Discussions enabled, with pinned welcome guidance.
- [ ] CODEOWNERS is added after org/team handles are real.
- [ ] Mirror is protected-branch/tag-only until public contribution intake is ready.
- [ ] `source_gate.py` passes on the mirrored ref.
- [ ] Public Pages deploy uses environment protection and concurrency.
- [ ] `github-pages` and `github-release` require a reviewer, prevent self-review, and disallow admin bypass.
- [ ] A test release produced a Draft release, checksum, validation report, and Rule Insights record.

Before student PR intake:

- [ ] Fork PRs cannot access secrets.
- [ ] Dependency-review check blocks vulnerable dependency additions.
- [ ] Secret scanning push protection is enabled where available; custom patterns are approved before use.
- [ ] PR template asks for issue link, surfaces touched, validation, and source/licensing impact.
- [ ] Maintainer triage SLA is defined internally.
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
