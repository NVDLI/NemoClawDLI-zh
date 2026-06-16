#!/usr/bin/env bash
# Run the SINGLE JS link engine (scripts/engine.js) headless, for CI and the python shims.
#
# Node resolution order:
#   1. a `node` on PATH (host install): fastest, validates the host working tree directly.
#   2. the lab container's node, since `dli` is bind-mounted to the host tree (everything is
#      volume-mounted to host, by requirement), so the container sees the exact files being
#      pushed. This is why no host install is strictly required.
# If neither is reachable, FAIL loudly (never silently skip; a graph gate that cannot run is
# a real "unverified" state, not a pass).
#
# All arguments are forwarded to engine.js verbatim (e.g. --check, --self-test, --reach,
# --check-json, --foyer-json, --graph-json, --embed). JSON modes print to stdout.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"

if command -v node >/dev/null 2>&1; then
  exec node "$HERE/engine.js" "$@"
fi

LAB="$(docker ps --format '{{.Names}}' 2>/dev/null | grep -iE '(^|[-_])lab([-_]|$)|jupyter' | head -1 || true)"
if [ -n "${LAB:-}" ]; then
  exec docker exec "$LAB" node /sandbox/dli/scripts/engine.js "$@"
fi

echo "run_engine: no node found (host PATH or a running lab container)." >&2
echo "  install node on the host, or start the lab so its node can run the engine." >&2
exit 2
