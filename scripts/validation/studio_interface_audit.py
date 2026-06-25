#!/usr/bin/env python3
"""Audit the course studio interface contract.

This is a static gate for the authoring studio. It checks that studio.html remains
self-hosted, that studio_main.js still supports lab writes plus static read-only
preview, exposes automated-test commands, and that the scripts SKILL documents those modes.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

for _p in (Path(__file__).resolve(), *Path(__file__).resolve().parents):
    if (_p / "scripts" / "_bootstrap.py").exists():
        sys.path.insert(0, str(_p / "scripts"))
        break
from _bootstrap import find_repo_root

HERE = Path(__file__).resolve()
ROOT = find_repo_root(HERE)
COURSE = ROOT / "web" / "nemoclaw"
STUDIO_HTML = COURSE / "studio.html"
STUDIO_JS = COURSE / "scripts" / "studio_main.js"
SCRIPT_SKILL = COURSE / "scripts" / "SKILL.html"
RUNTIME_SKILL = ROOT / "scripts" / "runtime" / "SKILL.html"
ROOT_SCRIPT_SKILL = ROOT / "scripts" / "SKILL.html"
LAB_RUNTIME_DOC = ROOT / "docs" / "lab_runtime_testing.md"
BROWSER_PROBE = ROOT / "scripts" / "runtime" / "browser_env_probe.sh"

REQUIRED_IDS = {
    "mod-sel", "url-bar", "reload-btn", "sidebar-btn", "comment-btn",
    "edit-btn", "run-btn", "block-edit-btn", "lite-btn", "tb-status",
    "sidebar", "poll-on", "poll-secs", "lm-row", "jump-btn", "cmt-list",
    "cmt-badge", "ref-list", "autorun-on", "autoannotate-on", "run-note",
    "editmode-on", "write-note", "chg-list", "save-sel-btn", "studio-frame",
    "loading", "pick-ov", "block-editor", "be-ta", "studio-pop",
}

REQUIRED_JS = {
    "lab contents api candidate": "/lab/api/contents/web/nemoclaw/",
    "legacy contents api candidate": "/lab/api/contents/nemoclaw/",
    "static page URL resolver": "function directPageUrl",
    "static read-only fallback": "Read-only preview: Jupyter contents API not available",
    "local comment fallback": "localStorage.setItem(commentStorageKey()",
    "reference inspector": "function renderReferences",
    "light export CSS": "styles/_lite_overlay.css",
    "run-all selector": ".cf-btn-run,.cell-run",
    "block editor locator": "function _locateBlockInFile",
    "no stale lite CSS path": "styles/styles/_lite_overlay.css",
}

REQUIRED_SKILL = {
    "audit command": "python3 scripts/validation/studio_interface_audit.py",
    "lab authoring mode": "Lab authoring",
    "static review mode": "Read-only static preview",
    "light export mode": "Light export review",
    "openclaw mode": "OpenClaw controls",
    "studio testing split": "operator console for running or copying checks",
    "browser env probe": "scripts/runtime/browser_env_probe.sh",
    "browser smoke harness": "CONTAINER_ENGINE=podman scripts/runtime/lab_runtime_test.sh --smoke",
    "render-only harness": "CONTAINER_ENGINE=podman scripts/runtime/lab_runtime_test.sh --render-only",
    "python podman compose": "python3 -m podman_compose",
    "full lab harness": "CONTAINER_ENGINE=podman scripts/runtime/lab_runtime_test.sh http://nginx/lab/static/nemoclaw/01a-loop.html",
}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def html_ids(raw: str) -> set[str]:
    return set(re.findall(r'\bid=["\']([^"\']+)["\']', raw))


def lesson_pages() -> set[str]:
    return {p.name for p in COURSE.glob("[0-9][0-9][a-z]-*.html")}


def module_pages(js: str) -> set[str]:
    return set(re.findall(r"file:\s*['\"]([^'\"]+\.html)['\"]", js))


def audit() -> list[str]:
    findings: list[str] = []
    html = read(STUDIO_HTML)
    js = read(STUDIO_JS)
    skill = read(SCRIPT_SKILL)
    runtime_skill = read(RUNTIME_SKILL)
    root_script_skill = read(ROOT_SCRIPT_SKILL)
    lab_doc = read(LAB_RUNTIME_DOC)

    missing_ids = sorted(REQUIRED_IDS - html_ids(html))
    for item in missing_ids:
        findings.append(f"studio.html missing required id #{item}")

    external_assets = re.findall(r'<(?:script|link)\b[^>]*(?:src|href)=["\']https?://[^"\']+', html, re.I)
    for item in external_assets:
        findings.append(f"studio.html imports external asset: {item}")
    if "cdnjs" in html.lower():
        findings.append("studio.html still references cdnjs")
    if 'href="styles/_style.css"' not in html:
        findings.append("studio.html does not use local styles/_style.css")

    pages = lesson_pages()
    modules = module_pages(js)
    for item in sorted(pages - modules):
        findings.append(f"studio_main.js MODULES omits lesson page {item}")
    for item in sorted(modules - pages):
        findings.append(f"studio_main.js MODULES references non-lesson page {item}")

    for label, token in REQUIRED_JS.items():
        if label == "no stale lite CSS path":
            if token in js:
                findings.append("studio_main.js still has stale styles/styles/_lite_overlay.css path")
            continue
        if token not in js:
            findings.append(f"studio_main.js missing {label}: {token}")


    required_studio_tokens = {
        "test command model": "const TEST_COMMANDS",
        "test command renderer": "function renderTestCommands",
        "static audit command": "python3 scripts/validation/studio_interface_audit.py",
        "render-only test command": "CONTAINER_ENGINE=podman scripts/runtime/lab_runtime_test.sh --render-only",
        "python podman compose command": "python3 -m podman_compose",
        "full lab test command": "CONTAINER_ENGINE=podman scripts/runtime/lab_runtime_test.sh http://nginx/lab/static/nemoclaw/01a-loop.html",
    }
    for label, token in required_studio_tokens.items():
        if token not in js:
            findings.append(f"studio_main.js missing {label}: {token}")

    for label, token in REQUIRED_SKILL.items():
        if token not in skill:
            findings.append(f"web/nemoclaw/scripts/SKILL.html missing {label}: {token}")

    runtime_tokens = {
        "probe file": "browser_env_probe.sh",
        "probe command": "scripts/runtime/browser_env_probe.sh",
        "browser smoke": "CONTAINER_ENGINE=podman scripts/runtime/lab_runtime_test.sh --smoke",
        "host deps optional": "host Node, Chromium, and Playwright are optional",
        "python compose": "python3 -m podman_compose",
    }
    for label, token in runtime_tokens.items():
        if token not in runtime_skill:
            findings.append(f"scripts/runtime/SKILL.html missing {label}: {token}")

    for label, token in {
        "scripts beacon probe": "scripts/runtime/browser_env_probe.sh",
        "scripts beacon browser note": "browser smoke is unavailable",
    }.items():
        if token not in root_script_skill:
            findings.append(f"scripts/SKILL.html missing {label}: {token}")

    for label, token in {
        "lab doc probe": "scripts/runtime/browser_env_probe.sh",
        "lab doc optional host deps": "Host Node.js, Playwright, and Chromium are not",
        "lab doc python compose": "python3 -m podman_compose",
    }.items():
        if token not in lab_doc:
            findings.append(f"docs/lab_runtime_testing.md missing {label}: {token}")

    if not BROWSER_PROBE.is_file():
        findings.append("scripts/runtime/browser_env_probe.sh missing")
    elif not (BROWSER_PROBE.stat().st_mode & 0o111):
        findings.append("scripts/runtime/browser_env_probe.sh is not executable")

    if "Write access: Jupyter contents API" not in js or "Read-only static preview" not in js:
        findings.append("studio_main.js must surface lab-write versus static-read-only state")

    return findings


def main() -> int:
    findings = audit()
    if findings:
        print("studio_interface_audit: FAIL")
        for row in findings:
            print(f"  - {row}")
        return 1
    print("studio_interface_audit: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
