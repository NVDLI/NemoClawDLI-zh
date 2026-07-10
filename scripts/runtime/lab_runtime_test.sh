#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
IMAGE=${LAB_RUNTIME_IMAGE:-nemoclaw/lab-runtime-test:local}
NETWORK=${LAB_RUNTIME_NETWORK:-nvidia-llm}
ENGINE=${CONTAINER_ENGINE:-}
BUILD=1
SMOKE=0
RENDER_ONLY=0
GATEWAY_ONLY=0
CRON_CONTRACT=0
TERMINAL_CONTRACT=0
CHAT_CONTRACT=0
ASSISTANT_ARTIFACTS=0
URL=""

usage() {
  cat <<'USAGE'
Usage: scripts/runtime/lab_runtime_test.sh [--smoke] [--render-only] [--gateway-only] [--cron-contract] [--terminal-contract] [--chat-contract] [--assistant-artifacts] [--no-build] [URL]

Builds a small browser-test image with Node.js, playwright-core, and Chromium,
then runs scripts/runtime/test_page_runtime.js from the repo bind-mounted read-only.
Host Node.js, Chromium, and Playwright are not required. For one-command
discovery, run scripts/runtime/browser_env_probe.sh first.

Examples:
  scripts/runtime/browser_env_probe.sh
  scripts/runtime/lab_runtime_test.sh --smoke
  scripts/runtime/lab_runtime_test.sh --render-only
  CLAW_URL=https://<launchable-host> CLAW_ACCESS_PROVIDER=cloudflare|pomerium CLAW_ACCESS_SESSION=<cookie-value> \
  scripts/runtime/lab_runtime_test.sh --gateway-only
  scripts/runtime/lab_runtime_test.sh --gateway-only --cron-contract
  scripts/runtime/lab_runtime_test.sh --gateway-only --terminal-contract
  scripts/runtime/lab_runtime_test.sh --gateway-only --chat-contract
  NVIDIA_API_KEY=$NVIDIA_API_KEY scripts/runtime/lab_runtime_test.sh --assistant-artifacts
  scripts/runtime/lab_runtime_test.sh http://nginx/lab/static/nemoclaw/01a-loop.html
  CLAW_URL=http://openclaw:8995 CLAW_TOKEN=dli-openclaw-token \
    scripts/runtime/lab_runtime_test.sh http://nginx/lab/static/nemoclaw/03a-kickstart.html
  CLAW_URL=https://<launchable-host> CLAW_TOKEN=<gateway-token> CLAW_ACCESS_PROVIDER=cloudflare|pomerium CLAW_ACCESS_SESSION=<cookie-value> \
    scripts/runtime/lab_runtime_test.sh http://nginx/lab/static/nemoclaw/03a-kickstart.html

Environment:
  CONTAINER_ENGINE=podman|docker     Force engine; default prefers podman.
  LAB_RUNTIME_IMAGE=name:tag         Override image tag.
  LAB_RUNTIME_NETWORK=nvidia-llm     Network for full lab tests; default matches deploy/docker-compose.yml.
  CLAW_URL=url                       OpenClaw base URL. Use Brev URL if local OpenClaw fails or shows EPERM.
  CLAW_TOKEN=token                   OpenClaw gateway bearer token; optional for Brev when /api/agent can discover it.
  CLAW_ACCESS_PROVIDER=name          cloudflare or pomerium; inferred from approved Brev hosts when omitted.
  CLAW_ACCESS_SESSION=value          Cloudflare relay session, or a Pomerium cookie injected only into the harness's ephemeral browser context.
  CLAW_CF=jwt                        Legacy alias for a Cloudflare access session.
  OPENCLAW_CORS_PROXY_BASE=url       Override the OpenClaw relay for an explicit test deployment.
  PLAYWRIGHT_VERSION=1.55.0          Override build arg for the runtime image.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --help|-h) usage; exit 0 ;;
    --smoke) SMOKE=1; shift ;;
    --render-only) RENDER_ONLY=1; shift ;;
    --gateway-only) GATEWAY_ONLY=1; shift ;;
    --cron-contract) CRON_CONTRACT=1; shift ;;
    --terminal-contract) TERMINAL_CONTRACT=1; shift ;;
    --chat-contract) CHAT_CONTRACT=1; shift ;;
    --assistant-artifacts) ASSISTANT_ARTIFACTS=1; shift ;;
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
for env_name in NVIDIA_API_KEY NVIDIA_API_URL CLAW_URL CLAW_TOKEN CLAW_ACCESS_PROVIDER CLAW_ACCESS_SESSION CLAW_CF CLAW_ORIGIN OPENCLAW_CORS_PROXY_BASE DEBUG_WS CHROME_BIN PLAYWRIGHT_BROWSERS_PATH; do
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
if [[ "$GATEWAY_ONLY" == "1" ]]; then
  node_args+=(--gateway-only --serve-static)
fi
if [[ "$CRON_CONTRACT" == "1" ]]; then
  [[ "$GATEWAY_ONLY" == "1" ]] || { echo "--cron-contract requires --gateway-only" >&2; exit 2; }
  node_args+=(--cron-contract)
fi
if [[ "$TERMINAL_CONTRACT" == "1" ]]; then
  [[ "$GATEWAY_ONLY" == "1" ]] || { echo "--terminal-contract requires --gateway-only" >&2; exit 2; }
  node_args+=(--terminal-contract)
fi
if [[ "$CHAT_CONTRACT" == "1" ]]; then
  [[ "$GATEWAY_ONLY" == "1" ]] || { echo "--chat-contract requires --gateway-only" >&2; exit 2; }
  node_args+=(--chat-contract)
fi
if [[ "$ASSISTANT_ARTIFACTS" == "1" ]]; then
  node_args+=(--assistant-artifacts --serve-static)
fi

if [[ -z "$URL" ]]; then
  if [[ "$GATEWAY_ONLY" == "1" ]]; then
    URL="http://127.0.0.1:4173/nemoclaw/03a-kickstart.html"
  elif [[ "$RENDER_ONLY" == "1" ]]; then
    URL="http://127.0.0.1:4173/nemoclaw/01a-loop.html"
  elif [[ "$ASSISTANT_ARTIFACTS" == "1" ]]; then
    URL="http://127.0.0.1:4173/nemoclaw/02b-rag.html"
  fi
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

if [[ "$RENDER_ONLY" == "1" || "$GATEWAY_ONLY" == "1" || "$ASSISTANT_ARTIFACTS" == "1" ]]; then
  exec "$ENGINE" "${run_args[@]}" "${test_cmd[@]}" "${node_args[@]}" "$URL"
fi

if ! "$ENGINE" network inspect "$NETWORK" >/dev/null 2>&1; then
  cat >&2 <<EOF
FATAL: container network '$NETWORK' not found.
Start the lab stack first with the compose frontend reported by scripts/runtime/browser_env_probe.sh.
On this host the reliable path is podman-compose-via-python:
  COMPOSE_PROJECT_NAME=task1 HOST_PROJECT_DIR=$ROOT python3 -m podman_compose -f deploy/docker-compose.yml -f deploy/docker-compose.override.yml up -d --build
If native Compose is installed, the same files work with docker compose or podman compose.
Or set LAB_RUNTIME_NETWORK to the network that contains nginx/openclaw.
EOF
  exit 2
fi

exec "$ENGINE" "${run_args[@]}" --network "$NETWORK" "${test_cmd[@]}" "${node_args[@]}" "$URL"
