# Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from scripts.validation import cfx11_course_audit


ROOT = Path(__file__).resolve().parents[2]
IMPORTER_PATH = ROOT / "scripts/notebook-import/import_course.py"
SPEC = importlib.util.spec_from_file_location("notebook_course_importer", IMPORTER_PATH)
IMPORTER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(IMPORTER)


class NotebookCourseImporterTests(unittest.TestCase):
    def fixture(self, root: Path) -> Path:
        source = root / "source"
        source.mkdir()
        notebook = {
            "nbformat": 4,
            "nbformat_minor": 5,
            "metadata": {},
            "cells": [
                {"cell_type": "markdown", "metadata": {}, "source": ["# Exact prose\n", "Two spaces stay.  \n"]},
                {"cell_type": "code", "metadata": {}, "execution_count": 9, "outputs": [{"output_type": "stream", "text": "not imported"}], "source": ["value = 6\n", "value * 7"]},
            ],
        }
        (source / "01-Exact.ipynb").write_text(json.dumps(notebook), encoding="utf-8")
        (source / "asset.json").write_text('{"reviewed": true}\n', encoding="utf-8")
        return source

    def test_import_is_deterministic_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.fixture(root)
            destination = root / "course"
            first = IMPORTER.import_course(source, destination, "a" * 64)
            first_markdown = (destination / "content/01-Exact.md").read_bytes()
            first_manifest = (destination / "course.json").read_bytes()
            second = IMPORTER.import_course(source, destination, "a" * 64)
            self.assertEqual(first, second)
            self.assertEqual(first_markdown, (destination / "content/01-Exact.md").read_bytes())
            self.assertEqual(first_manifest, (destination / "course.json").read_bytes())
            markdown = first_markdown.decode()
            self.assertIn("# Exact prose\nTwo spaces stay.  \n", markdown)
            self.assertIn("value = 6\nvalue * 7", markdown)
            self.assertNotIn("not imported", markdown)

    def test_audit_detects_cell_and_support_file_mutations(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.fixture(root)
            course = root / "course"
            IMPORTER.import_course(source, course, "b" * 64)
            runtime_contract = (
                "source license is unresolved\n"
                "https://integrate.api.nvidia.com/v1\n"
                "new CoursePythonRunner\n"
                "buildXBlocks\n"
                "courseNvidiaChat\n"
                "fetch(`${NVIDIA_BASE}/chat/completions`\n"
                "primary product category\n"
                "counterfactual product category\n"
                "input sensitivity\n"
                "cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/\n"
                'PYODIDE_VERSION = "0.27.7"\n'
                "application/x-course-chat+json\n"
                "coursePublicJson\n"
                "draw_mermaid_png\n"
                "additional_kwargs\n"
                '_install_module("wikipediaapi"\n'
            )
            for required in (
                "index.html", "course.css", "course.js", "SOURCE_PROVENANCE.md",
                "runtime/runner.js", "runtime/worker.js", "runtime/course_compat.py",
            ):
                target = course / required
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(runtime_contract, encoding="utf-8")
            with (course / "index.html").open("a", encoding="utf-8") as index:
                index.write('"../shared/vendor/codemirror-5.65.21.js"\n')
            self.assertEqual([], cfx11_course_audit.audit(course))
            markdown = course / "content/01-Exact.md"
            markdown.write_text(markdown.read_text().replace("value * 7", "value * 8"), encoding="utf-8")
            findings = cfx11_course_audit.audit(course)
            self.assertTrue(any("digest differs" in finding or "source differs" in finding for finding in findings), findings)
            IMPORTER.import_course(source, course, "b" * 64)
            (course / "asset.json").write_text("not used", encoding="utf-8")
            support = course / "content/asset.json"
            support.write_text("mutated", encoding="utf-8")
            findings = cfx11_course_audit.audit(course)
            self.assertTrue(any("supporting file differs" in finding for finding in findings), findings)


class CommittedCourseTests(unittest.TestCase):
    def test_committed_course_contract(self):
        self.assertEqual([], cfx11_course_audit.audit())

    def test_dynamic_content_keeps_a_strict_url_and_theme_boundary(self):
        client = (ROOT / "web/cfx11/course.js").read_text(encoding="utf-8")
        styles = (ROOT / "web/cfx11/course.css").read_text(encoding="utf-8")
        compatibility = (ROOT / "web/cfx11/runtime/course_compat.py").read_text(encoding="utf-8")
        self.assertIn('if (!["http:", "https:"].includes(url.protocol)) return "";', client)
        self.assertIn('name.endsWith(":href")', client)
        self.assertIn('"srcset"', client)
        self.assertIn(".graph-output rect", styles)
        self.assertIn(".graph-output text", styles)
        self.assertIn(".graph-output marker path", styles)
        self.assertNotIn("<style>rect", compatibility)

    def test_model_stream_consumes_the_response_body_incrementally(self):
        worker = (ROOT / "web/cfx11/runtime/worker.js").read_text(encoding="utf-8")
        self.assertIn("response.body.getReader()", worker)
        self.assertIn("await reader.read()", worker)
        self.assertIn("await parseEventStream(response)", worker)
        self.assertNotIn("parseEventStream(await response.text())", worker)


if __name__ == "__main__":
    unittest.main()
