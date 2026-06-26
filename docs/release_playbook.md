# Release playbook

This playbook defines how this course bundle moves from internal GitLab development to an external NVIDIA mirror that can accept student reports and later direct student contributions. The repository stays a course packaging and release workspace: authored content, shared services, deployment, validation, and governance move together.

## Scalable recommendation

Use a staged externalization model:

1. **Internal canonical**: NVIDIA internal GitLab is source of truth. External mirror is off.
2. **External read mirror**: publish a sanitized read mirror. Students can read, fork, and cite. Issues and pull requests stay closed or point to a discussion channel.
3. **External intake**: enable Issues and Discussions. Accept evidence, repros, corrections, and source reports. Merge rights stay internal.
4. **External contribution**: accept pull requests from forks with required checks, owner review, source governance, and release-manager merge.
5. **Release train**: tag public releases, publish Pages from protected refs only, and keep DLI platform deploys internal and manual.

Default rule: **issue-first, patch-second**. Students with domain evidence file structured Issues. Students who can carry a fix through validation open PRs using the structured release process.

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
| `translate-*` | trusted maintainer lane | limited | translation work |
| `v*` tags | release manager | no direct pushes | immutable public releases |

## External GitHub settings

Use these when the mirror lands on GitHub:

- Enable Issues at External intake.
- Enable Discussions for questions, learning friction, and broad ideas that are not actionable defects.
- Enable Projects for the triage/release board.
- Add `.github/CODEOWNERS` only after real NVIDIA org/team handles exist. Owners should cover `web/`, `cpu/`, `deploy/`, `scripts/`, `docs/`, and source governance paths.
- Protect `main` and `release/*` with required status checks, required PR review, required CODEOWNERS review, no force pushes, and no direct pushes except release automation.
- Use GitHub Actions environments for public Pages. Use required reviewers for production and concurrency so only one deploy runs at a time.
- Keep fork PR jobs on read-only tokens. Do not expose model, DLI, Cloudflare, or deployment secrets to forked pull requests.

## Internal GitLab settings

Use these while GitLab remains canonical:

- Protect `main`, `nemoclaw-only`, `release/*`, and tags.
- Keep production Pages deploy manual and protected.
- Keep branch preview deploys manual, isolated under branch slug paths, and built with production root from a protected ref.
- Use templates in `.gitlab/issue_templates/` and `.gitlab/merge_request_templates/`.
- Use labels and milestones as the project-management source. Mirror the same taxonomy to GitHub.

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

## CI/CD policy

| Layer | Runs on | Blocks merge | Purpose |
|---|---|---|---|
| Static gate | every branch/PR | yes | structure, links, SKILL, source, course contract |
| Browser/runtime gate | runtime, Studio, OpenClaw, page JS changes | yes when touched | page execution and visual/runtime smoke |
| Deployment gate | protected release branches and manual deploys | release manager | Pages and DLI platform evidence |

Required external PR checks:

```bash
python3 scripts/validation/validate_layout.py --quiet
python3 scripts/skills/skill_consistency.py
python3 scripts/skills/skill_contract.py
python3 scripts/compliance/source_gate.py
bash scripts/runtime/run_engine.sh --self-test
python3 scripts/validation/validate_bundle.py --scope ship
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
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.override.yml config
```

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
- [ ] External repository protects `main` and `release/*`.
- [ ] External repository has required checks mapped to the static gate.
- [ ] External repository has Discussions enabled, with pinned welcome guidance.
- [ ] CODEOWNERS is added after org/team handles are real.
- [ ] Mirror is protected-branch/tag-only until public contribution intake is ready.
- [ ] `source_gate.py` passes on the mirrored ref.
- [ ] Public Pages deploy uses environment protection and concurrency.

Before student PR intake:

- [ ] Fork PRs cannot access secrets.
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
