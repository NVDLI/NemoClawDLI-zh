#!/usr/bin/env bash
# Compatibility entrypoint for scripts/run_figcheck.sh. Implementation lives in scripts/figures/run_figcheck.sh.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$SCRIPT_DIR/figures/run_figcheck.sh" "$@"
