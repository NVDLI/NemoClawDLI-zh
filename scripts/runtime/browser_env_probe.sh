#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
ENGINE=${CONTAINER_ENGINE:-}

have() { command -v "$1" >/dev/null 2>&1; }

choose_engine() {
  if [[ -n "$ENGINE" ]]; then
    have "$ENGINE" || { echo "FAIL: CONTAINER_ENGINE=$ENGINE not found" >&2; exit 2; }
    echo "$ENGINE"
    return
  fi
  for c in podman docker; do
    if have "$c" && "$c" info >/dev/null 2>&1; then
      echo "$c"
      return
    fi
  done
  echo "FAIL: no working podman or docker engine found" >&2
  echo "Need one container engine; host Node.js, Chromium, and Playwright are not required." >&2
  exit 2
}

ENGINE=$(choose_engine)
export CONTAINER_ENGINE="$ENGINE"

echo "browser_env_probe"
echo "  repo: $ROOT"
echo "  engine: $ENGINE"
if python3 -m podman_compose --help >/dev/null 2>&1; then
  echo "  podman-compose-via-python: yes"
else
  echo "  podman-compose-via-python: no"
fi
echo "  host node: $(have node && echo yes || echo no)"
echo "  host chromium: $(have chromium && echo yes || have chromium-browser && echo yes || echo no)"
echo "  note: browser runtime uses container Node.js + playwright-core + Chromium"
echo

"$ROOT/scripts/runtime/lab_runtime_test.sh" --smoke

cat <<EOF

NEXT:
  no-lab browser render:
    CONTAINER_ENGINE=$ENGINE scripts/runtime/lab_runtime_test.sh --render-only

  start podman lab stack with Python compose:
    COMPOSE_PROJECT_NAME=task1 HOST_PROJECT_DIR=\$PWD python3 -m podman_compose -f docker-compose.yml -f docker-compose.override.yml up -d --build

  full lab-network browser check:
    CONTAINER_ENGINE=$ENGINE scripts/runtime/lab_runtime_test.sh http://nginx/lab/static/nemoclaw/01a-loop.html
EOF
