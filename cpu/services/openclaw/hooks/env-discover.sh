#!/usr/bin/env bash
# env-discover.sh. Injects the system spec into SOUL.md.
# Standalone hook, called from entrypoint (not from ocstack)
set -euo pipefail

WORKSPACE="${WORKSPACE:-/home/ocuser/.openclaw/workspace}"
AGENT_DIR="${AGENT_DIR:-/home/ocuser/.openclaw/agents/main/agent}"

# Find env_discover.sh
DISCOVER=""
for candidate in \
  "${WORKSPACE}/hooks/env_discover.sh" \
  "/tmp/openclaw/env_discover.sh"; do
  if [[ -x "$candidate" ]]; then
    DISCOVER="$candidate"
    break
  fi
done

if [[ -z "$DISCOVER" ]]; then
  echo "[hook:env-discover] env_discover.sh not found, skipping"
  exit 0
fi

echo "[hook:env-discover] Running: $DISCOVER"
bash "$DISCOVER" "$@" || true
echo "[hook:env-discover] Done."
