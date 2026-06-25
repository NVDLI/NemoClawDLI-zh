#!/usr/bin/env bash
# Run scripts/figures/check_figures.mjs with jsdom available (mountPolicyMap needs a DOM).
# Resolves node like run_node.sh (host / docker node:20 / guarded lab) and installs jsdom
# once into scripts/.figtools/ (gitignored, persists across runs via the host mount).
# All args forward to check_figures.mjs (e.g. --json).
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
TOOLS="$HERE/.figtools"

if command -v node >/dev/null 2>&1; then
  if [ ! -d "$TOOLS/node_modules/jsdom" ]; then
    mkdir -p "$TOOLS"; ( cd "$TOOLS" && npm i jsdom >/dev/null 2>&1 ) || true
  fi
  exec env FIG_JSDOM="$TOOLS/node_modules/jsdom" node "$HERE/check_figures.mjs" "$@"
fi

if command -v docker >/dev/null 2>&1; then
  IMG=""
  for c in node:20-slim node:20-bookworm-slim node:20 node:lts-slim node:lts; do
    if docker image inspect "$c" >/dev/null 2>&1; then IMG="$c"; break; fi
  done
  [ -z "$IMG" ] && IMG="node:20-slim"
  exec docker run --rm -u "$(id -u):$(id -g)" -e HOME=/tmp -e npm_config_cache=/tmp/.npm \
    -v "$REPO":/work -w /work "$IMG" sh -c '
      T=/work/scripts/.figtools
      if [ ! -d "$T/node_modules/jsdom" ]; then mkdir -p "$T"; ( cd "$T" && npm i jsdom >/dev/null 2>&1 ) || true; fi
      FIG_JSDOM="$T/node_modules/jsdom" node /work/scripts/figures/check_figures.mjs "$@"
    ' _ "$@"
fi

LAB="$(docker ps --format '{{.Names}}' 2>/dev/null | grep -iE '(^|[-_])lab([-_]|$)|jupyter' | head -1 || true)"
if [ -n "${LAB:-}" ]; then
  host_n="$(find "$REPO/web" -name '*.html' 2>/dev/null | wc -l | tr -d ' ')"
  lab_n="$(docker exec "$LAB" sh -c 'find /sandbox/dli/web -name "*.html" 2>/dev/null | wc -l' 2>/dev/null | tr -d ' ' || echo 0)"
  if [ "$host_n" = "$lab_n" ] && [ "$host_n" != "0" ]; then
    exec docker exec "$LAB" sh -c 'NODE_PATH=$(npm root -g 2>/dev/null) node /sandbox/dli/scripts/figures/check_figures.mjs '"$*"
  fi
fi

echo "run_figcheck: no node found (host PATH, a node docker image, or a matching lab container)." >&2
exit 2
