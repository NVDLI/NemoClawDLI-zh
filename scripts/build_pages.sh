#!/usr/bin/env bash
# Compatibility entrypoint for scripts/build_pages.sh. Implementation lives in scripts/build/build_pages.sh.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$SCRIPT_DIR/build/build_pages.sh" "$@"
