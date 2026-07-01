# Agent quickstart: Building Agents

Read this once per session. Then sample `SKILL.html` in the directory you're working in. For issue, MR, taxonomy, or broad prose work, read [`docs/agent_process.md`](docs/agent_process.md) before editing. The English course title, abstract, and learning objectives live in [`web/nemoclaw/COURSE_CANON.md`](web/nemoclaw/COURSE_CANON.md) and are immutable.

This is the internal release candidate for a proposed open-source publication of NVIDIA's
Building Agents course. External publication remains pending OSRB approval. Every path is
relative to the repository root; read [`RELEASE_STATUS.md`](RELEASE_STATUS.md) before changing
publication, licensing, contribution, or release claims.

Before proposing code, read [`GOVERNANCE.json`](GOVERNANCE.json), [`CONTRIBUTING.md`](CONTRIBUTING.md),
and [`DCO.md`](DCO.md). Agents must preserve the commit signoff, conduct, support, ownership,
independent-review, and protected-release boundaries. An agent cannot act as the human owner.

---

## Contribution safety first-touch

Ideas are cheap to submit through Discussions or Issues. Code is not trusted because an agent
or experienced maintainer wrote it. Before editing, identify the Issue, human owner, surfaces,
blast radius, validators, and runtime evidence. Work on a topic branch. The pre-commit hook
refuses commits on protected refs; pre-push refuses a stale base and never rewrites history.
Required CI and protected host settings remain authoritative because local hooks are bypassable.
Run `python3 scripts/validation/contribution_safety_audit.py --self-test` whenever governance,
templates, hooks, CI, permissions, or release workflows change.

---

## The brain

Every agent-addressable directory has a **`SKILL.html`** at its root.
It carries human-facing prose AND a machine-readable JSON contract.

```
SKILL.html                   ← ontology beacon for the whole repo
web/SKILL.html               ← web surface hub
web/nemoclaw/SKILL.html      ← the course brain (course-skill/1.0)
cpu/SKILL.html               ← cpu surface hub (the shared services)
```

To work in the course: open `web/nemoclaw/SKILL.html`, parse the
`<script type="application/json" id="skill-meta">` block.
That JSON gives you the page list, models, services, directives, and
known issues. Everything else in this quickstart is the repo-level rules.

Schema spec: [`SKILL_CONTRACT.md`](SKILL_CONTRACT.md).

---

## Hard rules (do not violate)

```
Source  → the repo root is canonical and holds EVERYTHING worth keeping. Edit it directly.
Scratch → /tmp for drafts, probes, one-shot scripts, audits, harness runs (ephemeral).
Safety  → risky edit? branch + validate + commit.
Keys    → llm_client only, never any other service.
```

Worth-keeping agent docs live in the repo by plain name (`AGENT_QUICKSTART.md`,
`AGENTS.md`, `SKILL_CONTRACT.md`, `QUALITY_DIRECTIVES.md`, `docs/`). Git history is
the auditable record. [`AGENTS.md`](AGENTS.md) is the cross-harness entry: it carries
the instruction-precedence ladder (what wins when rules conflict) and the ownership
discipline, so read it when an instruction collides with another.

---

## Where things live

| What | Path |
|---|---|
| Ontology beacon (root) | `SKILL.html` |
| Web surface hub | `web/SKILL.html` |
| Course brain | `web/nemoclaw/SKILL.html` |
| Release picker (student) | `web/index.html` |
| CPU surface hub (services) | `cpu/SKILL.html` |
| Shared services | `cpu/services/` |
| Companion essays (course-scoped) | `web/nemoclaw/mats/` |
| Vendored reference repos | `repos/` |
| Tooling | `scripts/` |
| Localization workflow | `scripts/translate/SKILL.html` |
| Locale language contracts | `scripts/translate/locales/<locale>/SKILL.html` (`pt-BR`, `es-ES`) |
| Same-branch drift Studio | `web/nemoclaw/localization.html` |
| Test runner + service build infra | `workspace/` |
| Agent reference docs | `docs/` |
| SKILL contract spec | `SKILL_CONTRACT.md` |
| Quality directives | `QUALITY_DIRECTIVES.md` |
| Deployment surface | `deploy/` compose overlays + nginx route config |
| Scratch / drafts / probes | `/tmp` (ephemeral, never committed) |

---

## Layout

```
.                          ← repository root (the release)
├── AGENT_QUICKSTART.md     ← this file
├── SKILL_CONTRACT.md       ← per-directory brain schema
├── QUALITY_DIRECTIVES.md   ← pedagogical-harm checks
├── SKILL.html              ← ontology beacon for the whole repo
├── docs/                   ← agent reference docs
├── web/                    ← browser frontends (remote-services-only)
│   ├── index.html          ← release picker
│   ├── SKILL.html          ← web surface hub
│   └── nemoclaw/           ← the released browser course (SKILL.html per directory)
│       └── mats/           ← course-scoped companion essays + vendored reference packets
├── cpu/                    ← shared services as notebooks + code
│   ├── SKILL.html          ← cpu surface hub
│   └── services/           ← the service stack the course runs against
├── repos/                  ← vendored reference repos
├── scripts/                ← tooling (validators, link engine, hooks, bundler)
└── workspace/              ← test runner + service build infra
```

Scratch work goes to `/tmp` (ephemeral, never committed).

---

## The course

One released course: **Securing Agents** at `web/nemoclaw/`. Browser-only,
remote-services-only. Sample `web/SKILL.html` for the surface contract and
`web/nemoclaw/SKILL.html` for the course brain.

Each page IS the narrative and ends in a live interactive artifact, with no
companion notebook track. The later modules paste a live OpenClaw URL into the
browser to drive the lab's sandboxed agent directly. No API keys live in static
files; the browser reaches services through nginx routes.

The course-scoped reference layer is `web/nemoclaw/mats/`, cited by the external URLs
its essays share with course pages, never linked as files.

---

## Docker stack

Six services. Compose and nginx config live in `deploy/`. The compose project name is set by `COMPOSE_PROJECT_NAME`, so
container names are `<project>-<service>-1`. Do not hardcode it; discover the
lab container:

```bash
LAB=$(docker ps --format '{{.Names}}' | grep -- '-lab-1' | head -1)   # the lab container
network:  nvidia-llm
```

The shared `dli` named volume is mounted by both lab and openclaw at
`/sandbox/dli`. In dev it is a bind to the repo root. In prod it is a real named
volume seeded from a baked-in copy in the lab image.

| Service | Address | Role |
|---|---|---|
| `lab` | `:8888` | JupyterLab |
| `llm_client` | `:9000` | OpenAI-compatible chat/embed/rerank gateway (SOLE keyholder) |
| `openclaw` | `:8995` | Sandboxed agent runtime inside the OpenShell sandbox |
| `sandbox-admin` | `:8099` | Hot-swaps the OpenClaw policy |
| `docker_router` | `:8070` | Bounded container lifecycle (holds the Docker socket) |
| `nginx` | `:80` | Reverse proxy |

The live key file is injected **only** into `llm_client` via `env_file:` in the
local or production deploy overlay. No other service ever receives keys.

---

## Validate

The static gate runs with no lab, GPU, or browser (the link engine runs headless
under node):

```bash
python3 scripts/validation/validate_layout.py --quiet      # layout + link glue
python3 scripts/validation/html_structure_audit.py --self-test  # prove browser-repair detector
python3 scripts/validation/html_structure_audit.py         # EN + locale HTML structure
python3 scripts/validation/security_architecture_audit.py --self-test # prove architecture drift detectors
python3 scripts/validation/security_architecture_audit.py       # release/runtime trust-boundary graph
python3 scripts/build/project_docs_explorer.py --self-test # prove rendered-doc artifact projection
python3 scripts/validation/release_evidence_audit.py --self-test # prove design/test evidence detectors
python3 scripts/validation/release_evidence_audit.py             # product design + release test plan
python3 scripts/skills/skill_consistency.py             # skill-meta vs the real tree
python3 scripts/build/assemble_locale_overlay.py --self-test  # stale translations cannot publish
python3 scripts/validation/localization_audit.py --self-test  # locale detector mutations
for locale in pt-BR es-ES; do python3 scripts/validation/localization_audit.py --locale "$locale"; done  # drift + language contracts
python3 scripts/validation/course_dependency_integrity.py --self-test # prove browser package/inventory detectors
python3 scripts/validation/course_dependency_integrity.py # exact packages, licenses, hashes, references, same-origin delivery
python3 scripts/validation/cell_audit.py --self-test      # prove bundled and split editor-asset detection
python3 scripts/validation/cell_audit.py                  # runnable-cell and CodeMirror delivery contract
python3 scripts/security/audit_python_dependencies.py    # declared floors/pins have no known PyPI/OSV vulns
python3 scripts/security/audit_vulnerability_waivers.py  # accepted vuln exceptions are owned + unexpired
python3 scripts/security/audit_dependency_locks.py --self-test  # lock detector rejects stale/unpinned mutations
python3 scripts/security/audit_dependency_locks.py        # runtime/material/SCA locks match direct manifests
python3 scripts/security/audit_sbom_policy.py --self-test # SBOM completeness/retired-component detector
python3 scripts/build/package_release.py --self-test     # archive/manifest/checksum determinism
bash    scripts/runtime/run_engine.sh --self-test        # link-engine self-test
python3 scripts/validation/validate_bundle.py --scope ship  # grounding, reachability, page audit, em-dash
```

When a change affects Studio, runnable cells, browser modules, OpenClaw pages, or
page rendering, do not stop at the static gate. Host `node`, Chromium, and
Playwright are optional because the browser harness carries them in a small
Podman/Docker image:

```bash
scripts/runtime/browser_env_probe.sh                       # proves container Node + Playwright + Chromium
CONTAINER_ENGINE=podman scripts/runtime/lab_runtime_test.sh --render-only
```

Stateful browser fixes need transition coverage, not one successful screenshot. Exercise
state entry, successful exit, error exit, remount, and reload/navigation against source and
built output. Pair the browser workflow with a static contract that catches cheap source drift.
For learner-facing code visibility or interaction-state changes, run both halves of the
shared contract:

```bash
python3 scripts/validation/learner_flow_audit.py
python3 scripts/validation/learner_flow_audit.py --self-test
CONTAINER_ENGINE=podman python3 scripts/validation/learner_flow_runtime_audit.py --site-root web
```

The static gate discovers course directories rather than assuming a GPU/runtime shape. It
requires focus prose before default-open implementation, visible prerequisites before live
launchable input, and stable Run/Stop/Reset/error states. The browser gate performs those
transitions against the real shared components.
For the OpenClaw probe frame lifecycle, run:

```bash
python3 scripts/validation/openclaw_fallback_audit.py
CONTAINER_ENGINE=podman python3 scripts/validation/openclaw_probe_frame_runtime_audit.py --site-root web
BUILD_PAGES_LANGS=0 bash scripts/build/build_pages.sh /tmp/nemoclaw_frame_preview
CONTAINER_ENGINE=podman python3 scripts/validation/openclaw_probe_frame_runtime_audit.py --site-root /tmp/nemoclaw_frame_preview
```

When a change touches an image, SVG, diagram, canvas figure, screenshot-like
asset, or page placement of an image, preview the rendered result through the
current agent host before you call the work done. Use Codex image preview,
Claude/browser screenshot, Cursor/browser preview, `cell_ui_runtime_audit.py`
screenshots, the Playwright runtime harness, or a local Pages/browser smoke.
Then show that preview to the requester in the status/final response, either as
an embedded image/screenshot or as the concrete preview artifact path. If no
host preview can run, report the exact harness blocker. Static checks such as
`figure_audit.py`, `source_gate.py`, and `validate_bundle.py` are still required,
but they do not replace seeing the rendered image.

Course-authored or provided SVGs under `assets/figures/` should be mounted with
`<div class="fig-embed" data-svg-src="..."></div>` so the shared theme variables
and click-to-expand lightbox work. Plain `<img>` is only for fixed-white paper
conversions documented as `connection: "conversion"` in asset provenance.

Visual first-touch checklist:

```bash
# 1. Read the local image contract and validator surface.
sed -n '1,140p' web/nemoclaw/assets/SKILL.html
sed -n '1,220p' scripts/validation/SKILL.html

# 2. Build the current page bundle and produce rendered screenshots.
BUILD_PAGES_LANGS=0 bash scripts/build/build_pages.sh /tmp/nemoclaw_visual_preview
python3 scripts/validation/cell_ui_runtime_audit.py \
  --site-root /tmp/nemoclaw_visual_preview \
  --page /nemoclaw/02b-rag.html \
  --screenshots /tmp/nemoclaw_visual_audit

# 3. Run the visual/static gates before pushing.
python3 scripts/validation/figure_audit.py
python3 scripts/compliance/source_gate.py
python3 scripts/validation/validate_bundle.py --no-write --scope ship
```

Inspect the screenshots in the active harness and show the relevant image or
crop to the requester. Check both light and dark theme screenshots. If the
browser harness cannot run, report the exact blocker and still run the static
gates above. Keep diagram labels that carry meaning; remove only caption-like
prose, provenance, or process shorthand from SVG source.

At narrow width, inspect both the inline overview and the enlarged state. The
mobile zoom badge must stay visible; activating it must preserve readable label
size, allow horizontal panning, keep the close control reachable, and close on
Escape. `cell_ui_runtime_audit.py` exercises that interaction.

If Codex tool calls fail before the requested command starts with
`bubblewrap is unavailable`, the missing dependency is in the host Codex
execution environment, not in NemoClaw's microservice containers. Run:

```bash
scripts/dev/codex_sandbox_probe.sh
```

The durable fix is to add `bubblewrap` to the Codex environment spec/base image.
The script also documents a rootless `--repair-user` fallback for the current
host; do not copy an arbitrary binary into `codex-resources/bwrap`, because
Codex hash-checks bundled resources.

For full lab-network browser tests, start the stack first with the compose
frontend reported by `scripts/runtime/browser_env_probe.sh`. Docker may be
installed without the Compose v2 plugin, and Podman may work while
`podman compose` is absent. On this host, use `python3 -m podman_compose`; do
not stop after `docker compose` or `podman compose` is missing if the probe
reports `podman-compose-via-python: yes`.

```bash
COMPOSE_PROJECT_NAME=task1 HOST_PROJECT_DIR=$PWD \
  python3 -m podman_compose -f deploy/docker-compose.yml -f deploy/docker-compose.override.yml up -d --build
CONTAINER_ENGINE=podman scripts/runtime/lab_runtime_test.sh http://nginx/lab/static/nemoclaw/01a-loop.html
```

Install the hooks so the gate runs locally:

```bash
bash scripts/build/install-hooks.sh
```

This symlinks `scripts/git-hooks/{pre-commit,pre-push}` into `.git/hooks/`.
pre-commit covers notebook-corruption, canvas-HTML, and page-runtime guards.
pre-push runs the rebase guard, skill_consistency, dependency vulnerability
floor audit, validate_layout, and the link-projection gate.

CI: `.gitlab-ci.yml` and `.github/workflows/pages.yml` run the same gate, then
`scripts/build/build_pages.sh` publishes a fully client-side site to GitLab Pages
(private / pre-release) and GitHub Pages (external release). GitLab also exposes
manual `security_sca` and `security_deep_sca` jobs; run the deep job when the
workspace dependency graph changes. See [`docs/pages_deploy.md`](docs/pages_deploy.md)
and [`docs/dependency_security.md`](docs/dependency_security.md).

For GitLab branch staging, play `pages` only after the blocking `test` job passes.
Done means the job SHA still matches the remote branch head, the live branch course
returns 200, both root and branch `branches.json` files pass
`branch_preview_manifest_audit.py`, and every selector option survives its same-origin
HEAD probe. Classic Pages keeps only the latest combined preview artifact, so never
claim an older branch remains staged after publishing another one. The automatic,
blocking `pages_smoke` job performs the same checks after Pages propagation.
For a local production-shaped browser check, run
`CONTAINER_ENGINE=podman python3 scripts/validation/branch_preview_runtime_audit.py --site-root /tmp/<combined-artifact>`;
it injects a ghost preview and requires both foyers to hide it.

---

## Working in the lab container

The browser course has no notebook track. The only notebooks are the service
docs under `cpu/services/`, exercised by the test runner below.

```bash
LAB=$(docker ps --format '{{.Names}}' | grep -- '-lab-1' | head -1)
docker exec "$LAB" bash -lc '<command>'

# Convert + execute a service notebook (cwd matters)
docker exec "$LAB" bash -lc '
  cwd=/sandbox/dli/cpu/services/<svc>
  jupytext --from md --to ipynb -o ${cwd}/._test.ipynb ${cwd}/<nb>.md
  PYTHONPATH="${cwd}:${cwd}/ocstart" \
    jupyter nbconvert --to notebook --execute --inplace --allow-errors \
      --ExecutePreprocessor.timeout=180 ${cwd}/._test.ipynb
'
```

**PYTHONPATH rule:** `${DIR}:${DIR}/ocstart` for every nbconvert.
**CWD rule:** `cd` into the notebook's directory before nbconvert.
`--ExecutePreprocessor.cwd=` is silently ignored in nbconvert 7.17.

---

## Test runner

The runner exercises the service-stack notebooks under `cpu/services/`. The
browser course needs no notebook track.

```bash
cd workspace
python3 run_tests.py --list                       # discover all notebooks
python3 run_tests.py services --notebook <nb>     # single
python3 run_tests.py services                     # the whole service stack
python3 run_tests.py --jobs 3                      # parallel
```

Output → `workspace/export/services/<nb>.ipynb` (gitignored runtime).

Buckets: clean | soft (<=2 errors or infra) | hard (>=3) | 0exec | skip.

---

## Known execution quirks

| Issue | Fix |
|---|---|
| `CellTimeoutError` writes nothing | Longer `--timeout`; wrap `demo.launch()` / `uvicorn.run()` with `try/except KeyboardInterrupt` |
| `--ExecutePreprocessor.cwd=` ignored | `cd` into the notebook's dir first |
| `walk_corpus()` already consumed | Materialise with `list(generator)` |
| Starlette `Router.__init__() on_startup` | Local-scope shim before `gr.ChatInterface().queue()` |
| `fitz.fitz.FileDataError` | `if not hasattr(fitz, "fitz"): fitz.fitz = fitz` |
| `policy_swap` ModuleNotFoundError | PYTHONPATH must include the notebook dir's `ocstart` |

---

## Audit + fix cycle

```
1. run_tests.py services                          → workspace/export/services/
2. inspect the exported .ipynb
3. fix the notebook in cpu/services/<svc>/<nb>.md directly
4. verify: docker cp the .md to lab:/tmp/ + nbconvert (scratch in /tmp)
5. commit (on a branch for risky work)
```

---

## Forbidden moves

- Leaving a stale `SKILL.md` beacon (fold it into the directory's SKILL.html and delete)
- `env_file:` with the live key on any service except `llm_client`
- `--ExecutePreprocessor.cwd=` (silently ignored)
- Mounting the live key file into lab or openclaw
- Creating `.ipynb` directly (always jupytext from `.md`)
- Committing `workspace/export/` (it is gitignored)
- Running long-lived servers without `try/except KeyboardInterrupt`
- Global Starlette shim (breaks IPykernel; use local-scope only)

---

## Adding or removing material (keep isolation clean)

This repo is the isolated single-course standalone. It is the root of the release and has
no parent project. What keeps an insertion or removal surgical:

**Reference nothing that is not in this repo.** Not in prose, not in a code comment, not in
a guard that hedges against it. The leaks to watch for:
- serving-wrapper context (a CI pipeline, a validation watcher, a course code) that belongs
  to whatever hosts this repo, not to the repo itself
- another course's pages or notebooks (only this course ships here)
- a service or skill you removed (grep the WHOLE tree for its name: compose, nginx, policy,
  SKILL beacons, agent skills, docs, not just the directory you deleted)
- a retired mechanism or a path from an older layout

**When you remove something, sweep its class.** A skill you delete often stays named in a
notebook, a SKILL beacon, or another skill, and those references dangle until you remove
them. A renamed service leaves a hook or policy pointing at a name that no longer answers,
which sends an agent to a dead host. Grep the whole tree first, then delete, then fix every
hit or name the ones you keep and why.

**Decide what propagates.** If this repo is maintained alongside a larger source it was
extracted from, a genuine bug usually exists in that source too, so keep the shared service
code byte-identical and let a real fix copy across. Wrapper-context and course-specific
files are expected to differ between the two: do not push a standalone-only cleanup back
into that source, and do not pull its wrapper context into here.
