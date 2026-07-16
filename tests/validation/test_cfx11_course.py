# Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
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
    def install_runtime_shell(self, destination: Path) -> None:
        source = ROOT / "web/cfx11"
        for relative in ("index.html", "course.css", "course.js", "SOURCE_PROVENANCE.md"):
            shutil.copy2(source / relative, destination / relative)
        shutil.copytree(source / "runtime", destination / "runtime", dirs_exist_ok=True)

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
                {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": ["from langchain_nvidia_ai_endpoints import ChatNVIDIA"]},
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

    def test_reviewed_source_patches_fail_closed_on_upstream_drift(self):
        relative = Path("3-Prompting-With-Messages/36-Chatbots.ipynb")
        patch = IMPORTER.SOURCE_PATCHES[(relative.as_posix(), 76)]
        source = f"Read [the helper]{patch['before']}"
        patch["upstream_source_sha256"] = IMPORTER.sha256_text(source)
        try:
            projected, record = IMPORTER.project_source(relative, 76, "markdown", source)
            self.assertIn("https://gitlab.com/nvidia/dli/content/c-fx-11-v1", projected)
            self.assertEqual(IMPORTER.sha256_text(source), record["upstream_source_sha256"])
            with self.assertRaisesRegex(ValueError, "no longer matches"):
                IMPORTER.project_source(relative, 76, "markdown", source + " drift")
        finally:
            patch["upstream_source_sha256"] = "36fbbf2de0109959505aa56a5bc701e41977d17c33105601ac7efd6fb8a2873e"

    def test_audit_detects_cell_and_support_file_mutations(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.fixture(root)
            course = root / "course"
            IMPORTER.import_course(source, course, "b" * 64)
            self.install_runtime_shell(course)
            self.assertEqual([], cfx11_course_audit.audit(course))
            markdown = course / "content/01-Exact.md"
            markdown.write_text(markdown.read_text().replace("value * 7", "value * 8"), encoding="utf-8")
            findings = cfx11_course_audit.audit(course)
            self.assertTrue(any("digest differs" in finding or "source differs" in finding for finding in findings), findings)
            IMPORTER.import_course(source, course, "b" * 64)
            self.install_runtime_shell(course)
            (course / "asset.json").write_text("not used", encoding="utf-8")
            support = course / "content/asset.json"
            support.write_text("mutated", encoding="utf-8")
            findings = cfx11_course_audit.audit(course)
            self.assertTrue(any("supporting file differs" in finding for finding in findings), findings)


class CommittedCourseTests(unittest.TestCase):
    def test_committed_course_contract(self):
        self.assertEqual([], cfx11_course_audit.audit())

    def test_every_preview_requires_human_and_agent_discovery_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for relative in ("web/index.html", "SKILL.html", "web/cfx11/SKILL.html"):
                destination = root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative, destination)
            self.assertEqual([], cfx11_course_audit.audit_discovery(root))
            foyer = root / "web/index.html"
            foyer.write_text(foyer.read_text(encoding="utf-8").replace("/lab/static/cfx11/index.html", "/missing-preview"), encoding="utf-8")
            findings = cfx11_course_audit.audit_discovery(root)
            self.assertTrue(any("web/index.html" in finding for finding in findings), findings)

    def test_runtime_contract_detects_removed_input_and_kernel_controls(self):
        with tempfile.TemporaryDirectory() as temporary:
            course = Path(temporary) / "cfx11"
            shutil.copytree(ROOT / "web/cfx11", course)
            client = course / "course.js"
            client.write_text(client.read_text(encoding="utf-8").replace('addEventListener("input-request"', 'addEventListener("removed-input"'), encoding="utf-8")
            findings = cfx11_course_audit.audit(course)
            self.assertTrue(any("in-cell Python input" in finding for finding in findings), findings)

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
        self.assertIn("applyEventBlock(pending.slice", worker)
        self.assertIn("decoder.decode(value, { stream: !done })", worker)
        self.assertNotIn("await response.text()", worker)

    def test_upstream_packages_cannot_be_replaced_by_course_shims(self):
        compatibility = (ROOT / "web/cfx11/runtime/course_compat.py").read_text(encoding="utf-8")
        for package in ("langchain", "langchain_core", "langgraph", "openai", "wikipediaapi", "contractions"):
            self.assertNotIn(f'_owned_module("{package}"', compatibility)
            self.assertNotIn(f'types.ModuleType("{package}"', compatibility)
        self.assertIn('_owned_module("assessment_helper"', compatibility)
        self.assertIn('_owned_module(\n    "chat_helpers.gradio_interface"', compatibility)

    def test_every_repository_wheel_is_locked(self):
        from scripts.pyodide.verify_cfx11_wheels import audit

        self.assertEqual([], audit())

    def test_browser_wheel_build_patch_is_digest_bound(self):
        from scripts.pyodide.verify_cfx11_wheels import audit

        with tempfile.TemporaryDirectory() as temporary:
            runtime = Path(temporary) / "runtime"
            shutil.copytree(ROOT / "web/cfx11/runtime", runtime)
            lock_path = runtime / "wheels.lock.json"
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            patched = next(package for package in lock["packages"] if package.get("patch"))
            patched["patch_sha256"] = "0" * 64
            lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
            findings = audit(runtime)
            self.assertTrue(any("build patch hash differs" in finding for finding in findings), findings)

    def test_source_patch_must_bind_a_distinct_upstream_cell(self):
        with tempfile.TemporaryDirectory() as temporary:
            course = Path(temporary) / "cfx11"
            shutil.copytree(ROOT / "web/cfx11", course)
            manifest_path = course / "course.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            patched = next(
                cell
                for lesson in manifest["lessons"]
                for cell in lesson["cells"]
                if "source_patch" in cell
            )
            patched["source_patch"]["upstream_source_sha256"] = patched["source_sha256"]
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            findings = cfx11_course_audit.audit(course)
            self.assertTrue(any("distinct upstream digest" in finding for finding in findings), findings)

    def test_unlicensed_helper_source_remains_an_upstream_link(self):
        manifest = json.loads((ROOT / "web/cfx11/course.json").read_text(encoding="utf-8"))
        self.assertFalse(any(str(row["path"]).endswith(".py") for row in manifest["supporting_files"]))
        lesson = ROOT / "web/cfx11/content/3-Prompting-With-Messages/36-Chatbots.md"
        text = lesson.read_text(encoding="utf-8")
        self.assertNotIn("](chat_helpers/gradio_interface.py)", text)
        self.assertIn(
            "](https://gitlab.com/nvidia/dli/content/c-fx-11-v1/-/blob/main/"
            "task1/dli/3-Prompting-With-Messages/chat_helpers/gradio_interface.py)",
            text,
        )


if __name__ == "__main__":
    unittest.main()
