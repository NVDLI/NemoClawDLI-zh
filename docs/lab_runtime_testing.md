# Lab runtime browser testing

Use this path when host Node.js, Playwright, or Chromium are missing. The test
runtime is a separate Podman/Docker image that carries Node.js, `playwright-core`,
and Chromium. The repository is mounted read-only into that image, so the test can
exercise the same page code without copying source into a mutable container. Use
`--smoke` for the container itself, `--render-only` for a real static page without
the lab stack, and a normal URL run for the full lab-network path.

## Security contract

- The web course calls `https://integrate.api.nvidia.com/v1` directly with the learner browser key.
  The harness mirrors that path with an explicit `NVIDIA_API_KEY` environment variable; do not mount `.env-dev` into the browser-test container.
- The browser-test container receives only the explicit environment variables needed
  for a run, such as `NVIDIA_API_KEY`, `CLAW_URL`, `CLAW_TOKEN`, `CLAW_CF`, or `CLAW_ORIGIN`.
- The repo mount is read-only: `/workspace:ro`.
- Full page tests run on the lab network (`nvidia-llm` by default) and reach static lab pages through `nginx` plus OpenClaw when those nodes are under test; model calls still go to `integrate.api.nvidia.com` directly.

## Verify the runtime image

Start with the discovery probe. It is the one-command check for agents: it finds
Podman or Docker, reports whether `python3 -m podman_compose` is available, and
runs the browser smoke test. Host Node.js, Playwright, and Chromium are not
required.

```bash
scripts/runtime/browser_env_probe.sh
```

The underlying smoke command launches Node.js, Playwright, and Chromium inside
the container and loads a `data:` page. It does not need the lab stack or network
access.

```bash
scripts/runtime/lab_runtime_test.sh --smoke
```

```bash
scripts/runtime/lab_runtime_test.sh --render-only
```

The render-only check starts a tiny static server inside the browser-test
container, opens `web/nemoclaw/01a-loop.html`, counts canvas controls, and reports
page errors. It is the fastest guard for agents that changed static assets or page
glue but do not need model calls yet.

## Run against the lab stack

Start the dev stack with the compose frontend reported by `scripts/runtime/browser_env_probe.sh`.
On this course host, `python3 -m podman_compose` is the reliable path. Docker may
be installed without the Compose v2 plugin, and Podman may work while
`podman compose` is absent. The deploy compose files name the shared network
`nvidia-llm`, which is the wrapper default.

```bash
COMPOSE_PROJECT_NAME=task1 HOST_PROJECT_DIR=$PWD \
  python3 -m podman_compose -f deploy/docker-compose.yml -f deploy/docker-compose.override.yml up -d --build
```

If your host has native Compose, the same files also work with `docker compose`
or `podman compose`. Do not stop after a missing native Compose subcommand when
the probe reports `podman-compose-via-python: yes`.

Then run a browser-page test on the same container network:

```bash
NVIDIA_API_KEY=$NVIDIA_API_KEY scripts/runtime/lab_runtime_test.sh http://nginx/lab/static/nemoclaw/01a-loop.html
```

For OpenClaw gateway pages, pass the local gateway URL and token explicitly:

```bash
NVIDIA_API_KEY=$NVIDIA_API_KEY CLAW_URL=http://openclaw:8995 CLAW_TOKEN=dli-openclaw-token scripts/runtime/lab_runtime_test.sh http://nginx/lab/static/nemoclaw/03a-kickstart.html
```

For a remote launchable behind Cloudflare Access, also pass `CLAW_CF` and, when the
gateway enforces an allowlisted origin, `CLAW_ORIGIN`.

## Useful knobs

- `CONTAINER_ENGINE=podman|docker`: force one engine.
- `LAB_RUNTIME_NETWORK=nvidia-llm`: choose the network containing `nginx` and
  `openclaw`.
- `LAB_RUNTIME_IMAGE=nemoclaw/lab-runtime-test:local`: override the image tag.
- `PLAYWRIGHT_VERSION=1.55.0`: override the Playwright image/package version.
- `--no-build`: reuse the existing test image.

## What the test checks

`scripts/runtime/test_page_runtime.js` opens the page, records JavaScript console/page
errors, and in `--render-only` mode stops after static page inspection. In full mode
it clicks every canvas `Run all` button, watches `/cli/gateway` WebSocket frames,
and reports whether tool/command frames were observed when gateway credentials were
provided.
