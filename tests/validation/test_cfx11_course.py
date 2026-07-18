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
BUNDLE_PATH = ROOT / "scripts/notebook-import/build_content_bundle.py"
BUNDLE_SPEC = importlib.util.spec_from_file_location("notebook_content_bundle", BUNDLE_PATH)
BUNDLE = importlib.util.module_from_spec(BUNDLE_SPEC)
assert BUNDLE_SPEC.loader
BUNDLE_SPEC.loader.exec_module(BUNDLE)
VIDEO_IMPORT_PATH = ROOT / "scripts/notebook-import/import_video_supplements.py"
VIDEO_IMPORT_SPEC = importlib.util.spec_from_file_location("notebook_video_supplements", VIDEO_IMPORT_PATH)
VIDEO_IMPORT = importlib.util.module_from_spec(VIDEO_IMPORT_SPEC)
assert VIDEO_IMPORT_SPEC.loader
VIDEO_IMPORT_SPEC.loader.exec_module(VIDEO_IMPORT)


class NotebookCourseImporterTests(unittest.TestCase):
    def install_runtime_shell(self, destination: Path) -> None:
        source = ROOT / "web/cfx11"
        for relative in ("index.html", "course.css", "course.js", "SOURCE_PROVENANCE.md"):
            shutil.copy2(source / relative, destination / relative)
        shutil.copytree(source / "runtime", destination / "runtime", dirs_exist_ok=True)
        (destination / "content-bundle.json").write_text(BUNDLE.encoded(BUNDLE.build(destination)), encoding="utf-8")
        (destination / "video-supplements.json").write_text(json.dumps({
            "schema": "dli-course-video-supplements/1.0",
            "source": {
                "repository": "https://gitlab.com/nvidia/dli/content/s-fx-12-v2",
                "commit": "8dc3b253e9ccb015470cd3b35d907b0fada38452",
            },
            "entries": [],
            "source_audit": {"invoked_widget_count": 0, "unused_helper_functions": []},
        }), encoding="utf-8")

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
            contract = destination / "content/SKILL.html"
            contract.write_text("<html><body>generated explorer contract</body></html>\n", encoding="utf-8")
            second = IMPORTER.import_course(source, destination, "a" * 64)
            self.assertEqual(first, second)
            self.assertEqual(first_markdown, (destination / "content/01-Exact.md").read_bytes())
            self.assertEqual(first_manifest, (destination / "course.json").read_bytes())
            self.assertEqual("<html><body>generated explorer contract</body></html>\n", contract.read_text(encoding="utf-8"))
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

    def test_video_import_uses_notebook_invocations_and_classifies_orphans(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            target = root / "target"
            (source / "videos").mkdir(parents=True)
            target.mkdir()
            (source / "videos/walkthroughs.py").write_text(
                'def walkthrough_00():\n    video_url = "https://d36m44n9vdbmda.cloudfront.net/assets/s-fx-12-v2/walkthrough_00.mp4"\n\n'
                'def walkthrough_99():\n    video_url = "https://d36m44n9vdbmda.cloudfront.net/assets/s-fx-12-v2/walkthrough_99.mp4"\n',
                encoding="utf-8",
            )
            notebook = {
                "cells": [
                    {"cell_type": "markdown", "source": ["# Intro"]},
                    {"cell_type": "markdown", "source": ["Watch first."]},
                    {"cell_type": "code", "source": ["from videos.walkthroughs import walkthrough_00 as walkthrough"]},
                    {"cell_type": "code", "source": ["walkthrough()"]},
                ]
            }
            (source / "Workshop-Intro.ipynb").write_text(json.dumps(notebook), encoding="utf-8")
            (target / "course.json").write_text(json.dumps({
                "lessons": [{"id": "Workshop-Intro", "title": "Workshop Intro", "cells": [{"index": 1}]}],
            }), encoding="utf-8")
            payload = VIDEO_IMPORT.build(source, target, "a" * 40)
            self.assertEqual(["walkthrough_00"], [entry["id"] for entry in payload["entries"]])
            self.assertEqual(["videos/walkthroughs.py#walkthrough_99"], payload["source_audit"]["unused_helper_functions"])
            self.assertEqual("referenced-not-copied", payload["entries"][0]["distribution"])

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

    def test_pages_delivery_bundle_and_runtime_controls_fail_closed(self):
        mutations = [
            ("content-bundle.json", '"schema":"dli-markdown-delivery/1.0"', '"schema":"removed"', "schema"),
            ("index.html", 'data-variable-view="focused"', 'data-variable-view="removed"', "focus-aware"),
            ("course.js", '"X-BILLING-INVOKE-ORIGIN"', '"X-REMOVED-INVOKE-ORIGIN"', "client billing attribution"),
            ("course.js", "function mermaidImageUrl", "function removedMermaidImageUrl", "Mermaid"),
        ]
        for relative, before, after, expected in mutations:
            with self.subTest(relative=relative, expected=expected), tempfile.TemporaryDirectory() as temporary:
                course = Path(temporary) / "cfx11"
                shutil.copytree(ROOT / "web/cfx11", course)
                path = course / relative
                source = path.read_text(encoding="utf-8")
                self.assertIn(before, source)
                path.write_text(source.replace(before, after), encoding="utf-8")
                findings = cfx11_course_audit.audit(course)
                self.assertTrue(any(expected in finding for finding in findings), findings)

    def test_async_workflow_contract_rejects_silent_or_unbounded_work(self):
        mutations = [
            ("course.js", 'signal,\n          headers: modelHeaders(key, route)', 'headers: modelHeaders(key, route)', "abortable model probe"),
            ("runtime/runner.js", "this.armTimeout(job, this.queueTimeoutMs", "this.removedTimeout(job, this.queueTimeoutMs", "queue-wait deadline"),
            ("runtime/runner.js", 'new CustomEvent("job-state"', 'new CustomEvent("hidden-state"', "complete job lifecycle"),
            ("index.html", 'data-runtime-panel="activity"', 'data-runtime-panel="hidden"', "visible workflow activity"),
            ("course.js", 'message.textContent = `Refresh failed:', 'message.textContent = `Silent refresh:', "observable variable refresh failure"),
            ("course.js", 'progress.setAttribute("role", "status")', 'progress.setAttribute("role", "presentation")', "accessible execution progress"),
            ("course.js", 'note.textContent = "Completed without output."', 'note.textContent = ""', "explicit no-output completion"),
            ("course.css", ".wb-cell-artifact { min-height: 0; }", ".wb-cell-artifact { min-height: 9rem; }", "compact result pane"),
            ("course.css", "prefers-reduced-motion: reduce", "removed-reduced-motion", "reduced-motion execution progress"),
            ("index.html", 'id="model-choice"', 'id="removed-model-choice"', "visible lesson model choice"),
            ("course.js", 'const MODEL_CHOICE_STORAGE_KEY = "cfx11-model-choice:v1"', 'const REMOVED_MODEL_CHOICE_STORAGE_KEY = "removed"', "session-scoped lesson model choice"),
            ("course.css", ".cm-s-default .cm-builtin", ".cm-s-default .cm-removed-builtin", "complete editor token palette"),
            ("course.css", "contain: inline-size layout paint", "contain: none", "responsive editor containment"),
            ("course.css", ".CodeMirror textarea { width: 1px !important;", ".CodeMirror textarea { width: 1000px !important;", "narrow WebKit editor input containment"),
            ("course.css", ".lesson-body :is(p, li, blockquote) { min-width: 0; overflow-wrap: anywhere; }", ".lesson-body :is(p, li, blockquote) { min-width: auto; overflow-wrap: normal; }", "unbounded lesson prose containment"),
            ("course.css", ".lesson-body pre { box-sizing: border-box; max-width: 100%; overflow-x: auto; }", ".lesson-body pre { overflow-x: visible; }", "lesson preformatted content containment"),
            ("course.js", "if (window.scrollX) window.scrollTo(0, window.scrollY)", "if (false) window.scrollTo(0, window.scrollY)", "responsive document scroll recovery"),
            ("course.js", 'section.className = "course-nav-section"', 'section.className = "removed-course-nav-section"', "collapsible section navigation"),
            ("course.js", "nav-lesson-number", "removed-lesson-number", "numbered lesson navigation"),
            ("index.html", 'class="header-lesson-nav"', 'class="removed-header-lesson-nav"', "header lesson navigation"),
            ("index.html", 'id="kernel-scope"', 'id="removed-kernel-scope"', "visible kernel scope control"),
            ("runtime/runner.js", "switchContext(configuration", "removedSwitchContext(configuration", "lesson kernel switch boundary"),
            ("course.js", 'recovery.className = "model-recovery"', 'recovery.className = "removed-model-recovery"', "actionable transient model recovery"),
            ("runtime/worker.js", 'const value = String(configuration.modelOverride || "").trim();', 'const value = "";', "runtime lesson model override"),
        ]
        for relative, before, after, expected in mutations:
            with self.subTest(relative=relative, expected=expected), tempfile.TemporaryDirectory() as temporary:
                course = Path(temporary) / "cfx11"
                shutil.copytree(ROOT / "web/cfx11", course)
                path = course / relative
                source = path.read_text(encoding="utf-8")
                self.assertIn(before, source)
                path.write_text(source.replace(before, after, 1), encoding="utf-8")
                findings = cfx11_course_audit.audit(course)
                self.assertTrue(any(expected in finding for finding in findings), findings)

    def test_lesson_prose_rejects_character_width_hedges(self):
        for rule in (".lesson-body > .lesson-lead { max-width: 80ch; }", ".lesson-body p { max-width: 92ch; }"):
            with self.subTest(rule=rule), tempfile.TemporaryDirectory() as temporary:
                course = Path(temporary) / "cfx11"
                shutil.copytree(ROOT / "web/cfx11", course)
                styles = course / "course.css"
                styles.write_text(styles.read_text(encoding="utf-8") + f"\n{rule}\n", encoding="utf-8")
                findings = cfx11_course_audit.audit(course)
                self.assertTrue(any("character-width hedges" in finding for finding in findings), findings)

    def test_model_probe_requires_the_reviewed_compatibility_set(self):
        with tempfile.TemporaryDirectory() as temporary:
            course = Path(temporary) / "cfx11"
            shutil.copytree(ROOT / "web/cfx11", course)
            client = course / "course.js"
            source = client.read_text(encoding="utf-8")
            source = source.replace(
                '  "nvidia/nemotron-3-nano-30b-a3b",\n',
                "",
                1,
            )
            client.write_text(source, encoding="utf-8")
            findings = cfx11_course_audit.audit(course)
            self.assertTrue(any("compatibility set" in finding for finding in findings), findings)

    def test_walkthrough_manifest_and_renderer_fail_closed(self):
        mutations = [
            ("video-supplements.json", "referenced-not-copied", "copied-without-evidence", "distribution relationship"),
            ("video-supplements.json", "d36m44n9vdbmda.cloudfront.net", "example.invalid", "NVIDIA MP4 boundary"),
            ("course.js", "video.controls = true", "video.controls = false", "accessible walkthrough controls"),
            ("course.js", 'video.preload = "none"', 'video.preload = "auto"', "learner-initiated walkthrough loading"),
            ("course.js", "source.dataset.src = reviewedVideoUrl(record)", "source.src = reviewedVideoUrl(record)", "deferred walkthrough source"),
            ("course.js", 'preview.className = "lesson-video-preview"', 'preview.className = "video-placeholder"', "contextual walkthrough preview"),
            ("course.js", 'const codeCellCount = lesson.cells.filter(cell => cell.type === "code").length;', "const codeCellCount = lesson.cells.length;", "code-only lesson cell count"),
        ]
        for relative, before, after, expected in mutations:
            with self.subTest(relative=relative, expected=expected), tempfile.TemporaryDirectory() as temporary:
                course = Path(temporary) / "cfx11"
                shutil.copytree(ROOT / "web/cfx11", course)
                path = course / relative
                source = path.read_text(encoding="utf-8")
                self.assertIn(before, source)
                path.write_text(source.replace(before, after, 1), encoding="utf-8")
                findings = cfx11_course_audit.audit(course)
                self.assertTrue(any(expected in finding for finding in findings), findings)

    def test_documentation_only_global_settings_dialog_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            course = Path(temporary) / "cfx11"
            shutil.copytree(ROOT / "web/cfx11", course)
            shell = course / "index.html"
            source = shell.read_text(encoding="utf-8")
            shell.write_text(source.replace("</body>", '<dialog id="settings-dialog"><p>Runtime documentation.</p></dialog></body>'), encoding="utf-8")
            findings = cfx11_course_audit.audit(course)
            self.assertTrue(any("documentation-only global settings dialog" in finding for finding in findings), findings)

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
