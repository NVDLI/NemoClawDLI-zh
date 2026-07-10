#!/usr/bin/env python3
# Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Read the image-provenance contract without filename allowlists."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROVENANCE_PAGE = ROOT / "web" / "nemoclaw" / "assets" / "SKILL.html"
PROVENANCE_BLOCK = re.compile(
    r'<script type="application/json" id="provenance">(.*?)</script>', re.S
)


@lru_cache(maxsize=1)
def figure_rows() -> tuple[dict[str, object], ...]:
    """Return every declared figure row; malformed or missing provenance is a hard error."""
    raw = PROVENANCE_PAGE.read_text(encoding="utf-8")
    match = PROVENANCE_BLOCK.search(raw)
    if not match:
        raise ValueError(f"missing provenance JSON in {PROVENANCE_PAGE.relative_to(ROOT)}")
    payload = json.loads(match.group(1))
    rows = payload.get("figures")
    if not isinstance(rows, list):
        raise ValueError("image provenance must contain a figures list")
    return tuple(row for row in rows if isinstance(row, dict))


def svg_modes() -> dict[str, str]:
    """Map each declared SVG to its rendering mode."""
    modes: dict[str, str] = {}
    for row in figure_rows():
        name = str(row.get("file", ""))
        if not name.endswith(".svg"):
            continue
        if name in modes:
            raise ValueError(f"duplicate image-provenance row: {name}")
        modes[name] = "fixed-white" if row.get("connection") == "conversion" else "theme-aware"
    return modes


def fixed_white_figures() -> frozenset[str]:
    """Derive paper conversions from provenance instead of maintaining an exception list."""
    return frozenset(name for name, mode in svg_modes().items() if mode == "fixed-white")
