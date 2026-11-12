#!/usr/bin/env bash
# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

# Run the SINGLE JS link engine (scripts/runtime/engine.js) headless, for CI and the python shims.
# Thin wrapper over run_node.sh. All args forward to engine.js verbatim.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
exec bash "$HERE/run_node.sh" "$HERE/engine.js" "$@"
