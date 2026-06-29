# Building Agents · NVIDIA DLI open-source release candidate

This repository is a course packaging and release workspace for NVIDIA DLI material and an
internal candidate for external open-source publication. Publication remains pending OSRB
approval. See [`RELEASE_STATUS.md`](RELEASE_STATUS.md) for the exact boundary.
It keeps the authored course, shared runtime services, deployment configuration, and
release validation in one source tree so a person or an agent can build, serve, audit,
and ship the same artifact.

The course currently selected for the learner release is **Securing Agents with OpenShell and NemoClaw**. The
repo is broader than that one course. Its core release tenet is **surface separation**:
course content is organized by the environment it can assume, and no surface may borrow
runtime assumptions from another surface without declaring that dependency.

## Surface Separation

Each top-level surface states its execution contract before any learner or operator runs
it. This keeps browser-only content portable, lets shared services support a bundle of
courses, and makes higher-compute variants explicit rather than accidental.

| Surface | Contract | Current role |
|---|---|---|
| [`web/`](web/) | Browser plus a lab or hosted proxy. Static pages cannot assume student-provisioned microservices or local keys. | Released browser course, foyer, course scripts, and course-scoped reference packets under [`web/nemoclaw/mats/`](web/nemoclaw/mats/). |
| [`cpu/`](cpu/) | CPU lab box that can run shared microservices for one or more courses. | `llm_client`, OpenClaw/OpenShell, sandbox policy control, Docker lifecycle bridge, and service notebooks. |
| `spark/` | Spark-level compute budget and data-plane assumptions. | Reserved for future courses or labs that need Spark rather than a CPU service stack. |
| `l40s/` or other GPU surfaces | GPU-backed lab capacity with explicit image, driver, and scheduling assumptions. | Reserved for future releases that need GPU runtime rather than a browser or CPU contract. |
| [`deploy/`](deploy/) | Operator surface for standing up the course bundle. | Compose overlays and nginx route config for DLI platform and local compute. |

A page under `web/` should use browser APIs, static assets, and declared proxy routes. It
should not assume that a learner has created a service container. A service under `cpu/`
can assume the compose network and shared volumes. A future `spark/` or GPU surface must
state its own compute contract instead of hiding it in page code.

## Release Flow

The repository keeps curated source and projects it into release formats:

- browser course served through Jupyter static paths and nginx
- standalone bundle generated from the same source
- client-side Pages site for preview or external release
- validation reports that use the same link engine as the browser viewer

Versioned public releases use protected annotated SemVer tags and deterministic archives with a
manifest, resolved-environment SBOM, and checksums. See
[`docs/release_artifacts.md`](docs/release_artifacts.md).

Students enter through the release foyer, [`web/index.html`](web/index.html). It surfaces
only released courses. Today that is [`web/nemoclaw/`](web/nemoclaw/).

For a presentation-led review, open the hosted
[`repository overview`](docs/repository-overview.html). It connects the learner route,
browser artifacts, runtime boundaries, contribution controls, localization workflow, and
release evidence. The downloadable PowerPoint version lives beside it at
[`docs/repository-overview.pptx`](docs/repository-overview.pptx).

Localized course prose lives as a sparse same-branch overlay under [`i18n/`](i18n/).
Canonical `web/` runtime modules, assets, machine-contract pages, and untranslated pages remain shared.
Open [`web/nemoclaw/localization.html`](web/nemoclaw/localization.html) to compare English
and Portuguese page state, then read [`scripts/translate/SKILL.html`](scripts/translate/SKILL.html)
for the review workflow and locale-specific language guidance.

## Deployment

Deployment files live under [`deploy/`](deploy/) so runtime orchestration is separate from
authored course surfaces.

For local CPU bring-up from the repo root:

```bash
cp /path/to/.env-dev .env-dev
COMPOSE_PROJECT_NAME=task1 HOST_PROJECT_DIR=$PWD \
  docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.override.yml up -d --build
```

Use the same `-f deploy/...` files with Podman Compose:

```bash
COMPOSE_PROJECT_NAME=task1 HOST_PROJECT_DIR=$PWD \
  python3 -m podman_compose -f deploy/docker-compose.yml -f deploy/docker-compose.override.yml up -d --build
```

For DLI platform deployment, use the base compose file plus the production overlay:

```bash
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.deployment.yml pull
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.deployment.yml up -d
```

The only service that receives key material is `llm_client`. Browser pages reach model
services through declared proxy routes or direct learner-supplied keys. Other containers
call the gateway over the compose network.

## Agent Visor

The repo is intentionally agent-readable. Every agent-addressable directory carries a
`SKILL.html` with a `skill-meta` JSON block. The root [`SKILL.html`](SKILL.html) is the
ontology beacon for the bundle. It points to execution surfaces, deployment, tooling,
and process docs. Agents should read [`AGENTS.md`](AGENTS.md), then
[`AGENT_QUICKSTART.md`](AGENT_QUICKSTART.md), then the relevant `SKILL.html` before
changing files.

## Ideas are easy; code is gated

The contribution boundary is intentionally asymmetric. Questions, corrections, teaching
ideas, runtime observations, and source leads should be cheap to submit through structured
Issues. Discussions become available when the external mirror and its intake features are
approved and enabled. No local checkout or patch is required. Security reports use the private path
described in [`SECURITY.md`](SECURITY.md), never a public Issue.

Code is an untrusted proposal until the repository and a human owner accept it. A direct
patch must name an Issue, declare every touched surface and blast radius, produce validation
evidence, and survive local hooks, required CI, protected-ref rules, owner review, and gated
release environments. Local hooks provide early feedback; protected refs and required checks
are the authority because hooks can be skipped. The contract and operator controls live in
[`CONTRIBUTING.md`](CONTRIBUTING.md) and [`docs/release_playbook.md`](docs/release_playbook.md).

## Verification

Run the static release gate before pushing:

```bash
python3 scripts/validation/validate_layout.py --quiet
python3 scripts/skills/skill_consistency.py
python3 scripts/validation/contribution_safety_audit.py --self-test
python3 scripts/validation/contribution_safety_audit.py
python3 scripts/build/assemble_locale_overlay.py --self-test
python3 scripts/validation/localization_audit.py --self-test
python3 scripts/validation/localization_audit.py --locale pt-BR
python3 scripts/validation/slides_audit.py --self-test
python3 scripts/validation/slides_audit.py
python3 scripts/compliance/source_gate.py
python3 scripts/build/package_release.py --self-test
bash scripts/runtime/run_engine.sh --self-test
python3 scripts/validation/validate_bundle.py --scope ship
```

For browser or Studio changes, also use the containerized browser harness:

```bash
scripts/runtime/browser_env_probe.sh
CONTAINER_ENGINE=podman scripts/runtime/lab_runtime_test.sh --render-only
```

For full lab-network checks, start the deploy stack first, then run the page harness
against `http://nginx/lab/static/...`.

## Contributing

If you have domain expertise, contribute first by lodging focused Issues with evidence:
what is wrong, where it appears, what the learner or operator impact is, and what source
or runtime behavior supports the claim. Issue-first contribution helps preserve the course
release process when the right fix crosses content, deployment, validation, or licensing.
Issue shape and label cadence are defined in [`docs/issue_standards.md`](docs/issue_standards.md).

If you are contributing a direct patch, follow the structured release path:

1. Create a branch for one coherent release concern.
2. Update the source surface and every declared blast-radius file.
3. Add or update validators when the same class of problem should not recur.
4. Run the validation ladder above.
5. Open an MR that says `Addresses #N` unless the change truly closes the issue.

The full external-release operating model lives in [`docs/release_playbook.md`](docs/release_playbook.md). Source and licensing rules live in [`scripts/compliance/docs/vendor_policy.md`](scripts/compliance/docs/vendor_policy.md)
and [`scripts/compliance/docs/open_source_readiness.md`](scripts/compliance/docs/open_source_readiness.md).

## Layout

```text
.
├── web/                    browser courses and browser-owned runtime assets
├── cpu/                    CPU service stack and service notebooks
├── deploy/                 compose overlays and nginx route config
├── docs/                   operating docs
├── scripts/                build, validation, runtime, compliance, and material tooling
├── workspace/              lab image, entrypoint, requirements, and test runner
├── SKILL.html              root ontology beacon served at /lab/static/SKILL.html
└── AGENTS.md               cross-harness agent contract
```

## License

The proposed external release uses the [Apache License 2.0](LICENSE.md). External publication
remains subject to [`RELEASE_STATUS.md`](RELEASE_STATUS.md).
