# CI/CD and client-side delivery

This documents how the course tests itself and ships as a fully client-side site.
This is the standalone repository, so `.gitlab-ci.yml` and
`.github/workflows/pages.yml` at the root are the live CI for this repo. Both run
the same static gate and then build the same client-side site. GitLab Pages serves
it as the private pre-release preview (access-controlled even on a private repo),
and GitHub Pages is the first-class external delivery mechanism. The planned
`docs.nvidia.com/learning/nemoclaw` integration will provide the NVIDIA learning
front door without changing the client-side course boundary.

Build and preview the site locally any time:

```
bash scripts/build/build_pages.sh public
python3 -m http.server -d public 8000      # then open http://localhost:8000
```

## The static site

`scripts/build/build_pages.sh` assembles a `public/` directory that runs entirely in a
browser, with no server logic:

| Path | What it is |
|---|---|
| `public/index.html` | the release picker, with Pages-relative links |
| `public/nemoclaw/` | the course as a self-contained standalone bundle |
| `public/link-graph.html` + `engine.js` | the link-graph viewer (engine runs in-browser; offline uses the embedded snapshot) |
| `public/tests.html` | the client-side test runner (below) |
| `public/validation.html` + `gate.json` | the CI gate report, rendered from `docs/validation/latest.json` |

The course pages inline their own CSS and JS and use relative links, so the course
dir is browsable from a Pages subpath. Live model calls use the student's own NVIDIA
key and call NVIDIA model services directly by default. An explicitly enabled iframe
mode uses the NVIDIA API CORS relay. Pages-hosted NemoClaw traffic uses the OpenClaw
relay because the browser cannot attach the required Access header to its WebSocket;
a launchable-vendored course beside its NemoClaw runtime uses the same-origin direct
route. The launchable supplies the startup NVIDIA API key through its approved bootstrap
path and populates the same browser `localStorage` entry used by the course key panel;
it does not introduce another credential channel. Lab-only
steps badge themselves and short-circuit off-lab.

## What gets tested, and where

The **static gate** runs in CI on every push, with no lab, GPU, or browser (the link
engine runs headless under node):

```
python3 scripts/validation/validate_layout.py --quiet     # surface-first layout + link glue
python3 scripts/skills/skill_consistency.py            # skill-meta vs the real tree
bash    scripts/runtime/run_engine.sh --self-test       # link-engine self-test (resolution, picker contract)
python3 scripts/validation/validate_bundle.py --scope ship # grounding, reachability, page audit, em-dash
```

The **client-side test runner** (`tests.html`) covers three layers in the browser:

1. an engine smoke test (loads `engine.js`, asserts the public surface used by the viewer and CI),
2. the course **SKILL self-tests**, which auto-run on load and badge their own pass/fail,
3. the CI gate summary, surfaced from `gate.json`.

**Notebook execution tests** (`workspace/run_tests.py`) exercise the service stack and
need the lab services running (no GPU required). They are not part of the static gate;
they run on the lab.

## Deployment

The deployment path has four ordered stages. Security SCA jobs also run in the test
stage when their rules select them.

1. **Static gate** runs on every selected branch or merge-request pipeline. It writes
   the gate report to `docs/validation/` as a build artifact.
2. **Pages build** is manual. Production refs publish the root site; ordinary branches
   publish an isolated preview path beside a root rebuilt from an approved production ref.
   The job calls `scripts/build/build_pages.sh public` and publishes the `public/` artifact.
3. **Pages smoke** verifies the deployed manifest and every advertised course URL.
4. **Human review** becomes available only after the exact commit passes the static gate
   and live deployment smoke test.

### GitLab Pages (private pre-release)

`.gitlab-ci.yml` defines `test`, `deploy`, `verify`, and `review` stages. The manual
`pages` job builds `public/` and publishes either a production ref or a branch preview.
GitLab Pages serves the private pre-release review surface under repository access
controls. `pages_smoke` checks the live result before `human_review` can be played.

### GitHub Pages (external release)

`.github/workflows/pages.yml` runs the identical gate, then builds `public/` and
deploys via the official GitHub Pages actions on pushes to the default branch. This
is the first-class public course. A future `docs.nvidia.com/learning/nemoclaw` entry
will route learners into this low-friction static experience.

### NemoClaw launchable (same-origin alternative)

The second supported interaction path is assembled by the production NemoClaw GitHub
repository. Its release selects a version or tag of this course repository, vendors the
resulting static tree, and registers it as a new-tab kickstart option beside the TUI,
consoles, and other launchable surfaces. The NemoClaw deployment already serves its
landing page and microservices from one origin, so course-to-runtime traffic is
same-origin and does not use the OpenClaw relay. Its approved startup interface also
receives the NVIDIA API key and seeds the existing browser `localStorage` entry consumed
by `getKey()` and the key panel. This repository supplies the versioned course input;
the NemoClaw repository owns the production launchable integration and deployment.

Both providers call the same `scripts/build/build_pages.sh`, so the GitLab pre-release and
the GitHub external site are byte-identical builds. Only one course ships: the
`web/nemoclaw/` browser course, bundled into `public/nemoclaw/`.
