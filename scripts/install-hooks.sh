#!/usr/bin/env bash
# Compatibility entrypoint for scripts/install-hooks.sh. Implementation lives in scripts/build/install-hooks.sh.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$SCRIPT_DIR/build/install-hooks.sh" "$@"
