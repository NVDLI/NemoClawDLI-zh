# Lab runtime browser testing

Use this path when host Node.js, Playwright, or Chromium are missing. The test
runtime is a separate Podman/Docker image that carries Node.js, `playwright-core`,
and Chromium. The repository is mounted read-only into that image, so the test can
exercise the same page code without copying source into a mutable container. Use
`--smoke` for the container itself, `--render-only` for a real static page without
the lab stack, and a normal URL run for the full lab-network path.
The change-to-test mapping lives in [`agent_process.md`](agent_process.md); generated
Pages behavior lives in [`pages_deploy.md`](pages_deploy.md).

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

## Exercise Course Assistant artifacts

Use the live artifact mode after changing the page assistant, its prompt, tool
schemas, or sandbox. It submits three representative requests, requires accepted
artifact-tool results, opens each preview, and verifies that a control changes the
rendered state. The local static origin uses the repository's configured model
relay because the direct service admits deployed course origins, not localhost.

```bash
NVIDIA_API_KEY=$NVIDIA_API_KEY \
  scripts/runtime/lab_runtime_test.sh --assistant-artifacts
```

Pass a deployed course page URL to validate its real origin and exact branch
artifact. The harness reports statuses and counts, not credentials or generated
source.

```bash
NVIDIA_API_KEY=$NVIDIA_API_KEY \
  scripts/runtime/lab_runtime_test.sh --no-build --assistant-artifacts \
  https://pages.example/course-branch/web/nemoclaw/02b-rag.html
```

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

Use the focused check before a full agent run. It loads Module 3a, discovers the
complete gateway token through the hosted HTTP relay, authenticates the hosted
WebSocket relay, and calls one read-only gateway method.

```bash
CLAW_URL=$NEMOCLAW_URL CLAW_CF=$CF_AUTHORIZATION \
  scripts/runtime/lab_runtime_test.sh --gateway-only
```

Add `--terminal-contract` to exercise the launchable's `/ws/terminal` route. It tries
the authenticated direct PTY used by the browser, retains the configured relay as a
fallback, runs `openshell sandbox list`, and requires a non-empty transcript. Add
`--cron-contract` to create a temporary structured cron job, query its run history,
and remove it; each opt-in check cleans up before exit.

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
it runs each canvas `Run all` flow sequentially, waits for the flow's real running state
to settle, and requires authenticated `/cli/gateway` response activity from flows whose
visible source uses the gateway. Tool calls are required by the focused `--chat-contract`
instead of every gateway flow because valid course flows may be chat-only or RPC-only.
`--gateway-only` isolates HTTP discovery, course token parsing, WebSocket
authentication, and a read-only gateway call without starting an agent turn.
`--gateway-only --terminal-contract` also exercises the operator PTY used by Modules
3c and 4b, so a healthy gateway cannot mask a broken direct or fallback terminal route.
`--assistant-artifacts` uses the live Course Assistant to generate and interact
with representative browser artifacts; it is credentialed and therefore opt-in.
