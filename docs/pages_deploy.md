# CI/CD and client-side Pages

This documents how the course tests itself and ships as a fully client-side site.
This is the standalone repository, so `.gitlab-ci.yml` and
`.github/workflows/pages.yml` at the root are the live CI for this repo. Both run
the same static gate and then build the same client-side site. GitLab Pages serves
it as the private pre-release preview (access-controlled even on a private repo),
and GitHub Pages serves it as the external public release.

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
key through the public CORS proxy; lab-only steps badge themselves and short-circuit
off-lab.

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

The pipeline has two jobs, defined once and shared by both CI providers.

1. **Static gate** runs on every push to any branch: layout, skill-meta consistency,
   the link-engine self-test, and the grounding/bundle audit. It writes the gate
   report to `docs/validation/` as a build artifact.
2. **Pages build** runs only on the default branch after the gate passes. It calls
   `scripts/build/build_pages.sh public` and publishes the `public/` artifact.

### GitLab Pages (private pre-release)

`.gitlab-ci.yml` defines a `test` stage and a `pages` stage. The `pages` job builds
`public/` and publishes to GitLab Pages from the default branch. GitLab Pages serves
the site even when the repo is private, so the team gets the pre-external-release
experience behind the same access control as any internal Pages site.

### GitHub Pages (external release)

`.github/workflows/pages.yml` runs the identical gate, then builds `public/` and
deploys via the official GitHub Pages actions on pushes to the default branch. This
is the public external release.

Both providers call the same `scripts/build/build_pages.sh`, so the GitLab pre-release and
the GitHub external site are byte-identical builds. Only one course ships: the
`web/nemoclaw/` browser course, bundled into `public/nemoclaw/`.
