# Building Agents · NVIDIA DLI open-source replicable release

An open-source, replicable release of an NVIDIA DLI course. The repository carries the
course narrative, its assets, the deployment that runs it, and the verification the CI
checks against, packaged so that a person or an agent can stand the whole thing up,
navigate it, and confirm it works.

The repository holds a curated source and the machinery that projects it into each format
the lab serves: the browser course, the standalone bundle, and the client-side Pages site.
The released **Securing Agents** course is one such projection. [`PHILOSOPHY.md`](PHILOSOPHY.md)
explains the reasoning behind the design; this README covers how to run and navigate it.

**This directory is the root of the release.** Everything needed to run, navigate, and
verify the course lives here. Deployment and the CI that gates every change are documented
in [`docs/`](docs/).

## The shape

Content is organized by **execution surface**, so every piece declares what it needs to
run before you try to run it. Stating that requirement up front is what lets someone else
reproduce the environment a given piece assumes.

| Surface | What it assumes | What's there |
|---|---|---|
| [`web/`](web/) | a browser + the lab proxy (remote services only) | the browser course, the foyer, and the course-scoped reference packets under [`web/nemoclaw/mats/`](web/nemoclaw/mats/) |
| [`cpu/`](cpu/) | a CPU lab box | the shared microservice stack the course runs against |

The course mats ([`web/nemoclaw/mats/`](web/nemoclaw/mats/)) are curated reference packets,
joined to pages by the external URLs they cite, never linked as files. Shared peers:
[`docs/`](docs/) operating docs and [`scripts/`](scripts/) the tooling.

## The released course

Students enter through the **release foyer** ([`web/index.html`](web/index.html)), which
surfaces exactly the released browser course and nothing else:

- **Securing Agents** lives in [`web/nemoclaw/`](web/nemoclaw/).

It runs live against the lab.

## Deployment

The lab (JupyterLab, the OpenAI-compatible model gateway, the sandboxed agent, tracing,
and on-demand services) comes up from this directory:

```bash
# from this directory (docker-compose.yml lives here; run compose from here, not the parent)
cp /path/to/.env-dev .env-dev          # NVIDIA_API_KEY (reaches llm_client only)
docker compose up -d
# JupyterLab: http://localhost/lab   ·   student entry: http://localhost/ (-> the foyer)
```

The only key any service holds is the model gateway's. The course is API-based, so it runs
on a CPU lab box with no GPU required.

## Agent-friendly by construction

Every directory carries a `SKILL.html` whose `<script type="application/json"
id="skill-meta">` block is the machine-readable contract for that directory. The root
[`SKILL.html`](SKILL.html) is the **ontology beacon** for the whole bundle. An agent reads
[`AGENT_QUICKSTART.md`](AGENT_QUICKSTART.md), then the relevant `SKILL.html`.

## Automatic verification

The bundle verifies itself. One link-graph engine, [`scripts/engine.js`](scripts/engine.js),
runs in **both** the browser viewer ([`scripts/link_graph.html`](scripts/link_graph.html))
and headless `node`, so what a human sees and what CI gates on are the same computation:

```bash
bash scripts/run_engine.sh --check        # link resolution + reachability + the release contract
bash scripts/run_engine.sh --self-test    # pin the engine to known projection facts
python3 scripts/validate_bundle.py --scope ship   # the full cadence (links + grounding + foyer)
```

It resolves every written link through the deploy "compiler" (nginx routes, Jupyter
`extra_static_paths`, the `dli` bind, compose topology) to a real file or service; reports
which pages reach a SKILL hub; and enforces that the foyer surfaces only the released course.
The same gate runs at pre-push and in CI.

## Source and licensing governance

The repository license is [Apache-2.0](LICENSE.md), and inbound contributions are handled under the Apache-2.0 contribution language unless a submission is clearly marked `Not a Contribution`.

New course assets, mats, datasets, cached references, generated files, or copied examples must carry source and license disposition before they are committed. Start with [`scripts/compliance/docs/open_source_readiness.md`](scripts/compliance/docs/open_source_readiness.md) and [`scripts/compliance/docs/vendor_policy.md`](scripts/compliance/docs/vendor_policy.md), then run:

```bash
python3 scripts/source_gate.py
```

## Layout

```
.                      ← the release root (DLI serves it through the wrapper above this dir)
├── web/ cpu/          ← the browser course and the services it runs against, by surface
├── mats/              ← curated reference packets (cited by URL)
├── docs/              ← operating docs
├── scripts/           ← engine.js + run_engine.sh + validators + SKILL generator
├── workspace/         ← lab runtime (entrypoint, llm_client, services code)
├── docker-compose.yml · nginx.conf   ← the deployment
├── SKILL.html         ← the ontology beacon (served at /lab/static/SKILL.html)
└── AGENT_QUICKSTART.md · SKILL_CONTRACT.md · QUALITY_DIRECTIVES.md
```

## Contributors

- Vadim Kudlay ([@vkudlay](mailto:vkudlay@nvidia.com))

## License

Released under the [Apache License 2.0](LICENSE.md).
