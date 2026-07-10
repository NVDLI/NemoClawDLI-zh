# Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Contracts for exhaustive, provenance-derived figure theme validation."""
from __future__ import annotations

import unittest
from pathlib import Path

from scripts.validation import color_theme, figure_audit
from scripts.validation.figure_provenance import fixed_white_figures, svg_modes


ROOT = Path(__file__).resolve().parents[2]


class FigureProvenanceThemeTests(unittest.TestCase):
    def test_every_canonical_svg_is_classified(self) -> None:
        actual = {
            f"figures/{path.name}"
            for path in (ROOT / "web/nemoclaw/assets/figures").glob("*.svg")
        }
        self.assertEqual(actual, set(svg_modes()))

    def test_fixed_white_set_is_derived_without_filename_allowlist(self) -> None:
        source = (ROOT / "scripts/validation/color_theme.py").read_text(encoding="utf-8")
        self.assertEqual(
            fixed_white_figures(),
            frozenset(name for name, mode in svg_modes().items() if mode == "fixed-white"),
        )
        self.assertNotIn("PAPER_ONLY_FIGURES", source)
        self.assertNotIn('{"fig2_react.svg", "fig2_rewoo.svg"}', source)

    def test_theme_contract_rejects_bypass_attempts(self) -> None:
        safe = '<svg class="gfx-dark"><rect fill="var(--gfx-bg)"/></svg>'
        cases = [
            (
                {"figures/probe.svg": "theme-aware"},
                {"figures/probe.svg": '<svg class="other"></svg>'},
                {"probe.html": '<div data-svg-src="assets/figures/probe.svg"></div>'},
                "gfx-dark",
            ),
            (
                {"figures/probe.svg": "theme-aware"},
                {"figures/probe.svg": safe},
                {"probe.html": '<div data-figure-mode="fixed-white" data-svg-src="assets/figures/probe.svg"></div>'},
                "cannot be relabeled",
            ),
            (
                {"figures/probe.svg": "fixed-white"},
                {"figures/probe.svg": "<svg></svg>"},
                {"probe.html": '<div data-svg-src="assets/figures/probe.svg"></div>'},
                "data-figure-mode",
            ),
        ]
        for modes, figures, pages, expected in cases:
            with self.subTest(expected=expected):
                findings = figure_audit._provenance_theme_findings(modes, figures, pages)
                self.assertTrue(any(expected in message for _path, message in findings), findings)

    def test_current_tree_satisfies_required_figure_contract(self) -> None:
        self.assertEqual([], figure_audit._provenance_theme_contract())


if __name__ == "__main__":
    unittest.main()
