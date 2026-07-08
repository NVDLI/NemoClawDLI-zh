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
    if name == "security_deep_sca":
        next_job = source.find("\npages:\n", start)
    return source[start : next_job if next_job >= 0 else len(source)]


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


class ScaTriggerContractTests(unittest.TestCase):
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

if __name__ == "__main__":
    unittest.main()
