#!/usr/bin/env bash
# Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

# Run the DOM-backed figure audit with the same pinned host Node dependencies as
# the browser validators. No image or lab fallback is owned by this repository.
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
NODE_PATH=${NODE_PATH:-$ROOT/scripts/runtime/node_modules}
export NODE_PATH
exec "$ROOT/scripts/runtime/run_node.sh" "$ROOT/scripts/figures/check_figures.mjs" "$@"
