#!/usr/bin/env bash
# Run a repo node script headless against the REAL host tree (CI + python shims).
# Resolution, each running the script against THIS repo's files:
#   1. host `node` on PATH.
#   2. `node` in a throwaway container with the host repo mounted (correct by construction).
#   3. a running lab container's node -- ONLY if /sandbox/dli matches this tree (guarded; that
#      mount can be a named volume diverged from the host, which would run against a stale tree).
# Fails LOUD if none reachable. Usage: run_node.sh <script> [args...]  (script abs or repo-relative)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
SCRIPT="${1:?usage: run_node.sh <script> [args...]}"; shift
case "$SCRIPT" in /*) ABS="$SCRIPT";; *) ABS="$REPO/$SCRIPT";; esac
REL="${ABS#"$REPO"/}"

if command -v node >/dev/null 2>&1; then
  exec node "$ABS" "$@"
fi

if command -v docker >/dev/null 2>&1; then
  IMG=""
  for c in node:20-slim node:20-bookworm-slim node:20 node:lts-slim node:lts node:20-alpine; do
    if docker image inspect "$c" >/dev/null 2>&1; then IMG="$c"; break; fi
  done
  [ -z "$IMG" ] && IMG="node:20-slim"   # none local: pull it (small) -- correctness over speed
  exec docker run --rm -u "$(id -u):$(id -g)" -v "$REPO":/work -w /work "$IMG" node "/work/$REL" "$@"
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
