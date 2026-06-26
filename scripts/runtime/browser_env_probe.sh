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

docker_compose=no
if have docker && docker compose version >/dev/null 2>&1; then docker_compose=yes; fi
podman_compose_native=no
if have podman && podman compose version >/dev/null 2>&1; then podman_compose_native=yes; fi
python_compose=no
if python3 -m podman_compose --help >/dev/null 2>&1; then python_compose=yes; fi

echo "browser_env_probe"
echo "  repo: $ROOT"
echo "  engine: $ENGINE"
echo "  native docker compose: $docker_compose"
echo "  native podman compose: $podman_compose_native"
echo "  podman-compose-via-python: $python_compose"
echo "  host node: $(have node && echo yes || echo no)"
echo "  host chromium: $(have chromium && echo yes || have chromium-browser && echo yes || echo no)"
echo "  note: browser runtime uses container Node.js + playwright-core + Chromium"
if [[ "$docker_compose" == "no" && "$podman_compose_native" == "no" && "$python_compose" == "yes" ]]; then
  echo "  escalation: native Compose missing; use python3 -m podman_compose and do not stop at docker compose or podman compose failure"
fi
echo

"$ROOT/scripts/runtime/lab_runtime_test.sh" --smoke

cat <<EOF

NEXT:
  no-lab browser render:
    CONTAINER_ENGINE=$ENGINE scripts/runtime/lab_runtime_test.sh --render-only

  start lab stack with Python compose when native Compose is absent:
    COMPOSE_PROJECT_NAME=task1 HOST_PROJECT_DIR=\$PWD python3 -m podman_compose -f deploy/docker-compose.yml -f deploy/docker-compose.override.yml up -d --build

  full lab-network browser check:
    CONTAINER_ENGINE=$ENGINE scripts/runtime/lab_runtime_test.sh http://nginx/lab/static/nemoclaw/01a-loop.html
EOF
