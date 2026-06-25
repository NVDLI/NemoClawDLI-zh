#!/usr/bin/env bash
# Compatibility entrypoint for scripts/lab_runtime_test.sh. Implementation lives in scripts/runtime/lab_runtime_test.sh.
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
exec "$ROOT/scripts/runtime/lab_runtime_test.sh" "$@"
