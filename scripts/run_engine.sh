#!/usr/bin/env bash
# Compatibility entrypoint for scripts/run_engine.sh. Implementation lives in scripts/runtime/run_engine.sh.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$SCRIPT_DIR/runtime/run_engine.sh" "$@"
