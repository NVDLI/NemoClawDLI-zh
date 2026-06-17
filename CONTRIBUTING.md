# Contributing

This repository is the open-source release of NVIDIA DLI's Securing Agents course.
Content is organized by execution surface: `web/` holds the browser course and its
course-scoped reference packets under `web/nemoclaw/mats/`, and `cpu/` holds the service
stack it runs against, with shared `scripts/` and `workspace/`.

Most of the work here is curation and projection: you shape and re-express knowledge into
the source under `web/` and `cpu/`, and the generators turn it into the formats the lab
serves, so a fix to the source reaches every format. Contributing is meant to be easy to
start, and the content bar that submissions are held to is documented rather than implicit.
[`PHILOSOPHY.md`](PHILOSOPHY.md) explains the approach and
[`QUALITY_DIRECTIVES.md`](QUALITY_DIRECTIVES.md) sets the content bar.

## Orientation

Read [`AGENT_QUICKSTART.md`](AGENT_QUICKSTART.md) first; it covers the layout, the
services, and the conventions. Every directory carries a `SKILL.html` whose
`skill-meta` JSON block is the machine-readable brain for that directory.
[`SKILL_CONTRACT.md`](SKILL_CONTRACT.md) specifies that format and
[`QUALITY_DIRECTIVES.md`](QUALITY_DIRECTIVES.md) sets the content bar.

## Install the hooks (once)

```
bash scripts/install-hooks.sh
```

This symlinks two hooks into `.git/hooks/`:

- `pre-commit`: corruption guard (`nb_audit.py`), canvas-HTML validation, and a
  page-runtime smoke check.
- `pre-push`: rebase guard, SKILL consistency, surface-layout and link-glue validation,
  and the projection link gate.

## Validate before pushing

The pre-push gates, on demand:

```
python3 scripts/validate_layout.py                # surface layout + link glue
python3 scripts/skill_consistency.py              # skill-meta vs the real tree
bash    scripts/run_engine.sh --self-test         # link-engine self-test
python3 scripts/validate_bundle.py --scope ship   # grounding, reachability, page audit
python3 scripts/tenets.py --check                 # core-tenets projection present
```

The service-stack notebooks need the lab services running (no GPU required):

```
python3 workspace/run_tests.py services --notebook <notebook>
```

## Conventions

The full operating creed (assumptions, practices, cadences, creeds) is projected into the
root `SKILL.html` skill-meta, not a separate agent-config file. Run `python3 scripts/tenets.py`
to read it with the gate that enforces each. The highlights:

- Edit content in place. Scratch work goes to `/tmp` and is never committed.
- Authored prose avoids em-dashes; rewrite the sentence rather than swap the punctuation.
- The browser course under `web/` stays remote-services-only, with no keys in static files.
- Do not commit lab-generated runtime output (`artifacts/`, `export/`, caches, the
  `public/` Pages build). `.gitignore` covers these classes.
