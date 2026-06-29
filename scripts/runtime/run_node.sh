#!/usr/bin/env bash
# Run a repo node script headless against the REAL host tree (CI + python shims).
# Resolution, each running the script against THIS repo's files:
#   1. explicit NODE_BIN, including a Windows node.exe reached from WSL.
#   2. host `node` on PATH.
#   3. `node` in a throwaway container with the host repo mounted (correct by construction).
#   4. a running lab container's node -- ONLY if /sandbox/dli matches this tree (guarded; that
#      mount can be a named volume diverged from the host, which would run against a stale tree).
# Fails LOUD if none reachable. Usage: run_node.sh <script> [args...]  (script abs or repo-relative)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
SCRIPT="${1:?usage: run_node.sh <script> [args...]}"; shift
case "$SCRIPT" in /*) ABS="$SCRIPT";; *) ABS="$REPO/$SCRIPT";; esac
REL="${ABS#"$REPO"/}"

if [ -n "${NODE_BIN:-}" ]; then
  if [ ! -x "$NODE_BIN" ]; then
    echo "run_node: NODE_BIN is not executable: $NODE_BIN" >&2
    exit 2
  fi
  case "$NODE_BIN" in
    *.exe)
      if ! command -v wslpath >/dev/null 2>&1; then
        echo "run_node: NODE_BIN points to node.exe but wslpath is unavailable." >&2
        exit 2
      fi
      exec "$NODE_BIN" "$(wslpath -w "$ABS")" "$@"
      ;;
    *) exec "$NODE_BIN" "$ABS" "$@" ;;
  esac
fi

if command -v node >/dev/null 2>&1; then
  exec node "$ABS" "$@"
fi

ENGINE="${CONTAINER_ENGINE:-}"
if [ -z "$ENGINE" ]; then
  for c in podman docker; do
    if command -v "$c" >/dev/null 2>&1 && "$c" info >/dev/null 2>&1; then ENGINE="$c"; break; fi
  done
fi

if [ -n "$ENGINE" ] && command -v "$ENGINE" >/dev/null 2>&1; then
  IMG=""
  for c in node:20-slim node:20-bookworm-slim node:20 node:lts-slim node:lts node:20-alpine; do
    if "$ENGINE" image inspect "$c" >/dev/null 2>&1; then IMG="$c"; break; fi
  done
  [ -z "$IMG" ] && IMG="node:20-slim"   # none local: pull it (small) -- correctness over speed
  run_user=()
  if [ "$ENGINE" = "podman" ]; then run_user+=(--userns=keep-id); else run_user+=(-u "$(id -u):$(id -g)"); fi
  exec "$ENGINE" run --rm "${run_user[@]}" -v "$REPO":/work -w /work "$IMG" node "/work/$REL" "$@"
fi

LAB="$(docker ps --format '{{.Names}}' 2>/dev/null | grep -iE '(^|[-_])lab([-_]|$)|jupyter' | head -1 || true)"
if [ -n "${LAB:-}" ]; then
  host_n="$(find "$REPO/web" -name '*.html' 2>/dev/null | wc -l | tr -d ' ')"
  lab_n="$(docker exec "$LAB" sh -c 'find /sandbox/dli/web -name "*.html" 2>/dev/null | wc -l' 2>/dev/null | tr -d ' ' || echo 0)"
  if [ "$host_n" = "$lab_n" ] && [ "$host_n" != "0" ]; then
    exec docker exec "$LAB" node "/sandbox/dli/$REL" "$@"
  fi
  echo "run_node: lab /sandbox/dli ($lab_n html pages) != host ($host_n) -- diverged volume; refusing." >&2
  exit 3
fi

echo "run_node: no node found (host PATH, a node docker image, or a matching lab container)." >&2
exit 2
