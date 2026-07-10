# Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Mutation tests for repository legal files and authored-source headers."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.compliance import source_license_contract as contract


class SourceLicenseContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="source-license-contract-")
        self.root = Path(self.temp.name)
        (self.root / "scripts").mkdir()
        (self.root / "web/nemoclaw/vendor").mkdir(parents=True)
        (self.root / "tests").mkdir()
        (self.root / "LICENSE").write_text(
            contract.COPYRIGHT + "\n\nApache License\nVersion 2.0\n", encoding="utf-8",
        )
        (self.root / "DCO.md").write_text(contract.DCO_1_1 + "\n", encoding="utf-8")
        (self.root / "THIRD-PARTY-NOTICES.md").write_text(
            "\n".join(contract.NOTICE_LINKS) + "\nmodified_from_upstream\n", encoding="utf-8",
        )
        (self.root / "scripts/check.py").write_text(
            "# " + contract.COPYRIGHT + "\n# " + contract.SPDX + "\n\nprint('ok')\n",
            encoding="utf-8",
        )
        (self.root / "tests/check.mjs").write_text(
            "#!/usr/bin/env node\n// " + contract.COPYRIGHT + "\n// " + contract.SPDX + "\n\nexport {};\n",
            encoding="utf-8",
        )
        self.manifest = self.root / "web/nemoclaw/vendor/browser-dependencies.json"
        self.manifest.write_text(json.dumps({"assets": [{
            "file": "library.js",
            "distribution_form": "transformed-bundle",
            "modified_from_upstream": True,
            "transformation": "bundled and minified with esbuild",
            "source_files": ["node_modules/library/index.js"],
        }]}), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def audit(self) -> list[str]:
        files = [path for path in self.root.rglob("*") if path.is_file()]
        failures, _ = contract.audit(self.root, files)
        return failures

    def assert_rejected(self, fragment: str) -> None:
        self.assertTrue(any(fragment in item for item in self.audit()), self.audit())

    def test_complete_fixture_passes(self) -> None:
        self.assertEqual([], self.audit())

    def test_license_copyright_mutation_is_rejected(self) -> None:
        (self.root / "LICENSE").write_text("Apache License\nVersion 2.0\n", encoding="utf-8")
        self.assert_rejected("root license")

    def test_dco_mutation_is_rejected(self) -> None:
        (self.root / "DCO.md").write_text(contract.DCO_1_1.replace("indefinitely", "temporarily"), encoding="utf-8")
        self.assert_rejected("DCO")

    def test_notice_link_mutation_is_rejected(self) -> None:
        path = self.root / "THIRD-PARTY-NOTICES.md"
        path.write_text(path.read_text(encoding="utf-8").replace(contract.NOTICE_LINKS[0], ""), encoding="utf-8")
        self.assert_rejected("third-party notices")

    def test_python_header_mutation_is_rejected(self) -> None:
        path = self.root / "scripts/check.py"
        path.write_text(path.read_text(encoding="utf-8").replace("# " + contract.SPDX + "\n", ""), encoding="utf-8")
        self.assert_rejected("scripts/check.py")

    def test_shebang_javascript_header_mutation_is_rejected(self) -> None:
        path = self.root / "tests/check.mjs"
        path.write_text(path.read_text(encoding="utf-8").replace("// " + contract.COPYRIGHT + "\n", ""), encoding="utf-8")
        self.assert_rejected("tests/check.mjs")

    def test_vendor_classification_mutation_is_rejected(self) -> None:
        data = json.loads(self.manifest.read_text(encoding="utf-8"))
        data["assets"][0].pop("modified_from_upstream")
        self.manifest.write_text(json.dumps(data), encoding="utf-8")
        self.assert_rejected("browser vendor")

    def test_vendor_form_and_modification_boolean_must_agree(self) -> None:
        data = json.loads(self.manifest.read_text(encoding="utf-8"))
        data["assets"][0]["modified_from_upstream"] = False
        self.manifest.write_text(json.dumps(data), encoding="utf-8")
        self.assert_rejected("browser vendor")

    def test_header_fixer_preserves_shebang(self) -> None:
        target = self.root / "tests/unlicensed.js"
        target.write_text("#!/usr/bin/env node\nconsole.log('ok');\n", encoding="utf-8")
        changed = contract.apply_headers(self.root, [target])
        self.assertEqual(["tests/unlicensed.js"], changed)
        lines = target.read_text(encoding="utf-8").splitlines()
        self.assertEqual("#!/usr/bin/env node", lines[0])
        self.assertEqual("// " + contract.COPYRIGHT, lines[1])
        self.assertEqual("// " + contract.SPDX, lines[2])


if __name__ == "__main__":
    unittest.main()
