# Agent quickstart: Building Agents

Read this once per session. Then sample `SKILL.html` in the directory you're working in. For issue, MR, taxonomy, or broad prose work, read [`docs/agent_process.md`](docs/agent_process.md) before editing. The English course title, abstract, and learning objectives live in [`web/nemoclaw/COURSE_CANON.md`](web/nemoclaw/COURSE_CANON.md) and are immutable.

This is the standalone open-source release of NVIDIA's Building Agents course. Every
path is relative to the repository root. The repo IS the release.

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
python3 scripts/skills/skill_consistency.py             # skill-meta vs the real tree
python3 scripts/security/audit_python_dependencies.py    # declared floors/pins have no known PyPI/OSV vulns
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
(private / pre-release) and GitHub Pages (external release). See
[`docs/pages_deploy.md`](docs/pages_deploy.md).

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
