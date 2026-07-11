# Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Comment checks reward compression without punishing readable wrapping."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from scripts.validation import code_hygiene


class CommentHygieneTests(unittest.TestCase):
    @staticmethod
    def findings(source: str) -> list[dict]:
        unit = [("fixture.js", "js", source, 0)]
        with patch.object(code_hygiene, "units", return_value=unit):
            code_hygiene._ANALYZE_CACHE.clear()
            return code_hygiene.comment_findings("ship")

    def test_short_wrapped_comment_is_readable(self) -> None:
        rows = self.findings(
            "// The first line introduces a constraint that continues naturally\n"
            "// on the next line without forcing an excessively wide source line.\n"
            "const value = 1;\n"
        )
        self.assertEqual([], rows)

    def test_long_comment_block_still_requires_compression(self) -> None:
        rows = self.findings("// one\n// two\n// three\n// four\nconst value = 1;\n")
        self.assertEqual(["comment-block-too-long"], [row["kind"] for row in rows])


if __name__ == "__main__":
    unittest.main()
