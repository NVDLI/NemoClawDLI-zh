# Securing Agents with OpenShell and NemoClaw

> **This is the Chinese (zh) localization fork** of the NeMoClaw DLI course, maintained at
> [`DLI / expand-the-funnel / NeMoClawDLI-zh`](https://gitlab-master.nvidia.com/dli/expand-the-funnel/nemoclawdli-zh).
> It is adapted for **non-Brev local deployment (WSL2 + Docker)** and will carry Simplified Chinese
> content once the full course is verified to run end-to-end without Brev. Until then, course
> content remains in English. For the upstream English source see
> [`NVDLI/NemoClawDLI`](https://github.com/NVDLI/NemoClawDLI).

This repository contains an NVIDIA Deep Learning Institute course about building agent systems and
applying practical security boundaries with NemoClaw and OpenShell. The course progresses from a
model call to tools, workflows, retrieval, deep research, sandbox policy, and deployment choices.
It is available in English, Brazilian Portuguese, and Spanish.

The planned public home is
[`NVDLI/NemoClawDLI-zh`](https://github.com/NVDLI/NemoClawDLI-zh). Publication remains pending OSRB
approval. [`RELEASE_STATUS.json`](RELEASE_STATUS.json) is the machine-readable source for current
publication state. Passing repository checks does not replace NVIDIA legal, security, or release
approval.

## Take the course

Start at [`web/index.html`](web/index.html), then open the
[`NemoClaw course`](web/nemoclaw/index.html). Interactive model exercises require a user-supplied
NVIDIA API key.

**In this fork (local WSL2 + Docker deployment):** Modules 3 and 4 connect to the local
openshell-sandbox Docker container instead of a Brev launchable. Start all services with
`bash start_proxies.sh` before opening the course pages — see
[`LOCAL_STARTUP_GUIDE.md`](LOCAL_STARTUP_GUIDE.md) for full instructions. No GPU required.

The learner release is a static browser site. It does not vendor learner credentials. The
NemoClaw product and runtime are external dependencies, not releases of this course repository.

## Run it locally (non-Brev, WSL2 + Docker)

This fork is designed to run without a Brev launchable. The full step-by-step startup procedure
is in [`LOCAL_STARTUP_GUIDE.md`](LOCAL_STARTUP_GUIDE.md). Architecture notes and troubleshooting
are in [`LOCAL_DEPLOYMENT_NOTES.md`](LOCAL_DEPLOYMENT_NOTES.md).

**Prerequisites:** WSL2 (Ubuntu 24.04), Docker, NeMoClaw + OpenShell installed, an NVIDIA API key.

**Quick start (every session):**

```bash
# 1. Set your API key
export NVAPI_KEY="nvapi-..."

# 2. Start all background services in one command
bash start_proxies.sh

# 3. Recover the container, set up the forward service, fix iptables rules
#    (see LOCAL_STARTUP_GUIDE.md steps 1c–1f for the full commands)
```

Then open `http://localhost:8081/web/nemoclaw/03a-kickstart.html` and proceed through the pages
in order: 01a, 01b, 02a … 04a, 04b, 04c.

### Original build-based local run

The upstream repo supports a build-based local run (no Docker required) for pages that do not
need a launchable. Install Python 3.11+, Node.js 20+, pnpm, and Chromium, then:

```bash
git clone https://github.com/NVDLI/NemoClawDLI.git
cd NemoClawDLI
bash scripts/build/build_pages.sh public
python3 -m http.server -d public 8000
```

Open `http://localhost:8000/nemoclaw/`. Modules 3 and 4 still require a launchable in this mode.

## Contribute

Questions, corrections, teaching ideas, runtime observations, and source leads belong in structured
Issues. Discussions will accept broader questions after public community intake is approved and
enabled. Security reports must use the private route in [`SECURITY.md`](SECURITY.md), never a public
Issue or Discussion.

Code remains an untrusted proposal until required checks and an authorized human review accept it.
Every patch needs an Issue, a declared blast radius, validation evidence, and DCO signoff. No
contributor, maintainer, or agent may approve its own protected merge or release.
Human approval does not replace a missing control or resolve unverified release risk.

Start with [`CONTRIBUTING.md`](CONTRIBUTING.md). It owns setup, issue and patch paths, signoff,
validation, localization ownership, and contributor credit. The
[`Code of Conduct`](CODE_OF_CONDUCT.md), [`support policy`](SUPPORT.md), and
[`DCO`](DCO.md) define the remaining contributor-facing terms.

## Verify a change

Install the local hooks, then run the fast gate:

```bash
bash scripts/build/install-hooks.sh
python3 scripts/validation/release_gate.py --tier fast --no-write
```

Use `--tier ship` before release or after a cross-cutting contract change. The
[`release test plan`](docs/release-test-plan.md) maps claims to evidence. Browser prerequisites and
render checks live in [`docs/lab_runtime_testing.md`](docs/lab_runtime_testing.md).

Release threat-model evidence lives in [`docs/security-design.md`](docs/security-design.md).
Its source-backed graph covers the learner runtime and release supply chain. CI rejects missing
services, unlabeled trust-boundary flows, broken evidence, connector collisions, and stale output.
The generated review design and diagram carry matching architecture fingerprints. A report that
does not preserve that binding remains Unknown until the submitted attachments are confirmed.
Repository-owned mitigations, unresolved host or provider requirements, residual risks, and
non-applicable recommendations are separated in
[`docs/security-control-disposition.md`](docs/security-control-disposition.md).

## How the repository guides agents

[`AGENTS.md`](AGENTS.md) is the cross-harness contract. Each source directory has a `SKILL.html`
that routes work to the relevant files and checks. Deterministic validators, protected host rules,
and human review remain authoritative when agent context, model behavior, or contributor experience
varies.

The compact design note
[`Rapidly-Evolving Agentic Compliance Suite`](docs/agentic-compliance-suite.md) explains this
workflow pattern, its limits, and how the repository implements it. The name describes an
engineering approach, not a certification, product, or substitute for approval.

## Project map

| Path | Purpose |
| --- | --- |
| [`web/`](web/SKILL.html) | Browser course, shared runtime, figures, materials, and dependency evidence |
| [`i18n/`](i18n/SKILL.html) | Reviewed locale overlays built with the canonical course |
| [`scripts/`](scripts/SKILL.html) | Build, validation, runtime, compliance, and material tooling |
| [`docs/`](docs/SKILL.html) | Design, test, deployment, security, and release contracts |
| [`SKILL.html`](SKILL.html) | Repository map for people and agents |

The repository ships the static course and its validation tools. It does not ship a lab operating
system, service stack, or base container. The
[`browser dependency inventory`](web/nemoclaw/dependencies.html) identifies code learners receive.
[`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md) and
[`THIRD-PARTY-NOTICES.md`](THIRD-PARTY-NOTICES.md) cover software and material relationships.

## Governance, release, and license

The intended public course repository is an NVIDIA-owned Full-OSS-Project, OSS Type I. That
classification applies only to this DLI course repository. The governing system must approve it
before public cutover.

[`docs/release_playbook.md`](docs/release_playbook.md) owns maintainer roles, public GitHub setup,
protected publication, and internal integration cadence. [`CHANGELOG.md`](CHANGELOG.md) records
version history. [`docs/product-design.md`](docs/product-design.md) defines the release boundary,
and [`docs/security-design.md`](docs/security-design.md) defines its trust boundaries.

The proposed public release uses the [Apache License 2.0](LICENSE). Contributions use the same
inbound license with DCO signoff; this project does not require a separate CLA.
