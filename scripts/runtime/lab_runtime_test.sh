#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
IMAGE=${LAB_RUNTIME_IMAGE:-nemoclaw/lab-runtime-test:local}
NETWORK=${LAB_RUNTIME_NETWORK:-nvidia-llm}
ENGINE=${CONTAINER_ENGINE:-}
BUILD=1
SMOKE=0
RENDER_ONLY=0
URL=""

usage() {
  cat <<'USAGE'
Usage: scripts/runtime/lab_runtime_test.sh [--smoke] [--render-only] [--no-build] [URL]

Builds a small browser-test image with Node.js, playwright-core, and Chromium,
then runs scripts/runtime/test_page_runtime.js from the repo bind-mounted read-only.
Host Node.js, Chromium, and Playwright are not required. For one-command
discovery, run scripts/runtime/browser_env_probe.sh first.

Examples:
  scripts/runtime/browser_env_probe.sh
  scripts/runtime/lab_runtime_test.sh --smoke
  scripts/runtime/lab_runtime_test.sh --render-only
  scripts/runtime/lab_runtime_test.sh http://nginx/lab/static/nemoclaw/01a-loop.html
  CLAW_URL=http://openclaw:8995 CLAW_TOKEN=dli-openclaw-token \
    scripts/runtime/lab_runtime_test.sh http://nginx/lab/static/nemoclaw/03a-kickstart.html
  CLAW_URL=https://nemoclaw-<id>.brevlab.com CLAW_TOKEN=<gateway-token> CLAW_CF=<CF_Authorization> \
    scripts/runtime/lab_runtime_test.sh http://nginx/lab/static/nemoclaw/03a-kickstart.html

Environment:
  CONTAINER_ENGINE=podman|docker     Force engine; default prefers podman.
  LAB_RUNTIME_IMAGE=name:tag         Override image tag.
  LAB_RUNTIME_NETWORK=nvidia-llm     Network for full lab tests; default matches docker-compose.yml.
  CLAW_URL=url                       OpenClaw base URL. Use Brev URL if local OpenClaw fails or shows EPERM.
  CLAW_TOKEN=token                   OpenClaw gateway bearer token.
  CLAW_CF=jwt                        CF_Authorization value for remote Brev launchables.
  PLAYWRIGHT_VERSION=1.55.0          Override build arg for the runtime image.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --help|-h) usage; exit 0 ;;
    --smoke) SMOKE=1; shift ;;
    --render-only) RENDER_ONLY=1; shift ;;
    --no-build) BUILD=0; shift ;;
    --) shift; break ;;
    -*) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
    *) URL="$1"; shift ;;
  esac
done

choose_engine() {
  if [[ -n "$ENGINE" ]]; then
    command -v "$ENGINE" >/dev/null || { echo "container engine not found: $ENGINE" >&2; exit 2; }
    echo "$ENGINE"
    return
  fi

  for c in podman docker; do
    if command -v "$c" >/dev/null && "$c" info >/dev/null 2>&1; then
      echo "$c"
      return
    fi
  done

  echo "no working podman or docker engine found" >&2
  exit 2
}

ENGINE=$(choose_engine)
echo "ENGINE: $ENGINE"

if [[ "$BUILD" == "1" ]]; then
  "$ENGINE" build \
    --build-arg "PLAYWRIGHT_VERSION=${PLAYWRIGHT_VERSION:-1.55.0}" \
    -f "$ROOT/scripts/runtime/lab-runtime/Containerfile" \
    -t "$IMAGE" "$ROOT"
fi

run_args=(run --rm -v "$ROOT:/workspace:ro" -w /workspace -e NODE_PATH=/opt/nemoclaw-runtime/node_modules)
test_cmd=(--entrypoint node "$IMAGE" scripts/runtime/test_page_runtime.js)
for env_name in NVIDIA_API_KEY CLAW_URL CLAW_TOKEN CLAW_CF CLAW_ORIGIN DEBUG_WS CHROME_BIN PLAYWRIGHT_BROWSERS_PATH; do
  if [[ -n "${!env_name:-}" ]]; then
    run_args+=(-e "$env_name=${!env_name}")
  fi
done

if [[ "$SMOKE" == "1" ]]; then
  exec "$ENGINE" "${run_args[@]}" --network none "${test_cmd[@]}" --smoke
fi

node_args=()
if [[ "$RENDER_ONLY" == "1" ]]; then
  node_args+=(--render-only --serve-static)
fi

if [[ -z "$URL" && "$RENDER_ONLY" == "1" ]]; then
  URL="http://127.0.0.1:4173/nemoclaw/01a-loop.html"
fi

URL=${URL:-http://nginx/lab/static/nemoclaw/01a-loop.html}

case "$URL" in
  file://*|data:*)
    exec "$ENGINE" "${run_args[@]}" --network none "${test_cmd[@]}" "${node_args[@]}" "$URL"
    ;;
  http://127.0.0.1:*|http://localhost:*)
    exec "$ENGINE" "${run_args[@]}" "${test_cmd[@]}" "${node_args[@]}" "$URL"
    ;;
esac

if [[ "$RENDER_ONLY" == "1" ]]; then
  exec "$ENGINE" "${run_args[@]}" "${test_cmd[@]}" "${node_args[@]}" "$URL"
fi

if ! "$ENGINE" network inspect "$NETWORK" >/dev/null 2>&1; then
  cat >&2 <<EOF
FATAL: container network '$NETWORK' not found.
Start the lab stack first, for example:
  COMPOSE_PROJECT_NAME=task1 HOST_PROJECT_DIR=$ROOT podman compose -f docker-compose.yml -f docker-compose.override.yml up -d --build
or, with podman-compose-via-python:
  COMPOSE_PROJECT_NAME=task1 HOST_PROJECT_DIR=$ROOT python3 -m podman_compose -f docker-compose.yml -f docker-compose.override.yml up -d --build
or set LAB_RUNTIME_NETWORK to the network that contains nginx/openclaw.
EOF
  exit 2
fi

exec "$ENGINE" "${run_args[@]}" --network "$NETWORK" "${test_cmd[@]}" "${node_args[@]}" "$URL"
