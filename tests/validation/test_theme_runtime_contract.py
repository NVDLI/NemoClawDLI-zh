"""Standard-library contracts for browser-theme coverage and its CI triggers."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.skills import skill_renderer_runtime_audit as theme_runtime


ROOT = Path(__file__).resolve().parents[2]


def ci_job(name: str) -> str:
    source = (ROOT / ".gitlab/ci/sca.yml").read_text(encoding="utf-8")
    start = source.index(f"{name}:\n")
    next_job = source.find("\nsecurity_", start + len(name) + 2)
    return source[start : next_job if next_job >= 0 else len(source)]


def core_job(name: str, next_name: str) -> str:
    source = (ROOT / ".gitlab/ci/core.yml").read_text(encoding="utf-8")
    start = source.index(f"{name}:\n")
    end = source.index(f"\n{next_name}:\n", start)
    return source[start:end]


class ThemeRuntimeContractTests(unittest.TestCase):
    def test_discovery_includes_every_nested_html_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = [root / "index.html", root / "nested" / "SKILL.html", root / "vendor" / "page.html"]
            for path in paths:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("<!doctype html><title>fixture</title>", encoding="utf-8")
            self.assertEqual(
                theme_runtime.discover_html(root),
                ["index.html", "nested/SKILL.html", "vendor/page.html"],
            )

    def test_runtime_has_dark_light_dependency_detection(self) -> None:
        source = theme_runtime.RUNTIME_JS
        for token in ("themeSnapshot('dark')", "themeSnapshot('light')", "colorDependencies", "themeChanged"):
            with self.subTest(token=token):
                self.assertIn(token, source)

    def test_preview_audits_the_branch_owned_tree(self) -> None:
        source = (ROOT / ".gitlab/ci/core.yml").read_text(encoding="utf-8")
        self.assertIn('THEME_SITE_ROOT="public/$CI_COMMIT_REF_SLUG"', source)
        self.assertIn('skill_renderer_runtime_audit.py --site-root "$THEME_SITE_ROOT"', source)

    def test_runtime_keeps_universal_narrow_layout_coverage(self) -> None:
        source = theme_runtime.RUNTIME_JS
        for token in (
            "setViewportSize({ width:390, height:844 })",
            "narrow theme-dependent contrast",
            "narrow layout overflows 390px viewport",
            "documentWidth:document.documentElement.scrollWidth",
        ):
            with self.subTest(token=token):
                self.assertIn(token, source)

    def test_runtime_requires_useful_linked_sbom_rendering(self) -> None:
        source = theme_runtime.RUNTIME_JS
        for token in (
            "sbomEvidenceReady",
            "linked SBOM rendered no component licenses",
            "security_deep_sca",
            "security_image_sca",
        ):
            with self.subTest(token=token):
                self.assertIn(token, source)

    def test_runtime_executes_the_pyodide_skill_contract(self) -> None:
        source = theme_runtime.RUNTIME_JS
        for token in (
            "scripts/pyodide/SKILL.html",
            "new Function(globalThis.__pyodideWorkerSource)",
            "editorCount !== runtimeContract.count + 1",
            "syntaxTokens < runtimeContract.count",
            "CodeMirror surfaces are not consistently theme-aware",
            "Shift+Enter did not run the cell and focus the next editor",
            "scratch REPL did not preserve namespace or execution order",
            "final expression did not render as notebook output",
            "Pyodide background process did not register and complete across cells",
            "Pyodide artifact did not preserve a highlighted preview and exact downloadable bytes",
            "playground.runAll()",
            "Pyodide chat did not preserve repeated user input",
            "Pyodide intentional error did not render its traceback",
            "Pyodide traceback did not highlight the failing source line",
            "Pyodide display pipeline did not render highlighted JSON/code, Markdown, HTML, and tables",
            "Pyodide syntax output is hard-wrapped or artificially narrow",
            "Pyodide helper menu did not preview, edit, and apply the live helper source",
            "Pyodide rich output sanitizer admitted executable or network-active HTML",
            "Pyodide build.nvidia.com path did not consume streamed SSE tokens",
            "Pyodide WebSocket round trip did not connect, send, and receive",
            "Pyodide rendered a model credential into page output",
            "Pyodide Reset did not clear cell state",
        ):
            with self.subTest(token=token):
                self.assertIn(token, source)


class ScaTriggerContractTests(unittest.TestCase):
    def test_pages_does_not_wait_on_an_unplayed_manual_sca_job(self) -> None:
        pages = core_job("pages", "pages_smoke")
        header = pages.split("  script:\n", 1)[0]
        self.assertIn('needs: ["test"]', header)
        self.assertNotIn("optional: true", header)
        self.assertIn('if [ -z "${DEEP_SCA_JOB_ID:-}" ]', pages)
        self.assertIn("- job: security_deep_sca\n          artifacts: true", pages)

    def test_pages_deep_sca_override_tracks_scanner_inputs(self) -> None:
        pages = core_job("pages", "pages_smoke")
        scanner = ci_job("security_deep_sca")
        for path in (
            "workspace/requirements.lock",
            "scripts/security/requirements-sca.lock",
            "scripts/compliance/sbom_evidence.py",
            ".gitlab/ci/sca.yml",
        ):
            with self.subTest(path=path):
                self.assertIn(f"- {path}", scanner)
                self.assertIn(f"- {path}", pages)

    def test_expensive_scans_are_automatic_only_for_relevant_inputs(self) -> None:
        cases = {
            "security_browser_sca": "scripts/browser-vendor/package-lock.json",
            "security_deep_sca": "workspace/requirements.lock",
        }
        for job_name, relevant_input in cases.items():
            with self.subTest(job=job_name):
                job = ci_job(job_name)
                self.assertIn(relevant_input, job)
                self.assertIn("- .gitlab/ci/sca.yml", job)
                self.assertNotIn("- .gitlab-ci.yml", job)
                self.assertNotIn("- .gitlab/ci/core.yml", job)

    def test_expensive_scans_remain_optional_in_unrelated_merge_requests(self) -> None:
        optional_rule = """- if: '$CI_PIPELINE_SOURCE == "merge_request_event"'
      when: manual
      allow_failure: true"""
        for job_name in ("security_browser_sca", "security_deep_sca"):
            with self.subTest(job=job_name):
                self.assertIn(optional_rule, ci_job(job_name))

    def test_image_scan_requires_an_explicit_immutable_digest(self) -> None:
        job = ci_job("security_image_sca")
        self.assertIn("$SBOM_IMAGE =~", job)
        self.assertIn("@sha256:[0-9a-f]{64}", job)
        self.assertIn("when: manual", job)
        self.assertIn("- when: never", job)
        self.assertNotIn("schedule", job)
        self.assertNotIn("when: on_success", job)

if __name__ == "__main__":
    unittest.main()
