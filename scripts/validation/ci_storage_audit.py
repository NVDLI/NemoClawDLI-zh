#!/usr/bin/env python3
"""Guard the GitLab Pages storage contract.

This GitLab instance still uses classic Pages: only the job literally named
`pages` can publish. Branch previews therefore share the production Pages job and
produce large downloadable artifacts. This audit keeps the retention controls in
place without depending on PyYAML in the minimal runner image.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


def _root() -> Path:
    for p in (Path(__file__).resolve(), *Path(__file__).resolve().parents):
        if (p / ".gitlab-ci.yml").exists():
            return p
    raise SystemExit("ci_storage_audit: could not find repo root")


def _job_block(text: str, job: str) -> str:
    m = re.search(rf"(?ms)^{re.escape(job)}:\n(?P<body>.*?)(?=^[A-Za-z0-9_.-]+:\n|\Z)", text)
    return m.group("body") if m else ""


def main() -> int:
    ci = _root() / ".gitlab-ci.yml"
    text = ci.read_text(encoding="utf-8")
    findings: list[str] = []

    pages = _job_block(text, "pages")

    if not pages:
        findings.append("missing pages job")

    checks = [
        (pages, r"build_branch_preview\(\)", "pages job must still build branch previews"),
        (pages, r"build_production_root_from_ref\(\)", "preview path must rebuild production root from a protected ref"),
        (pages, r"artifacts:\n(?:[ ]{2,}.*\n)*?[ ]{4}expire_in:\s*3 days", "pages artifacts must expire"),
        (pages, r"environment:\n(?:[ ]{2,}.*\n)*?[ ]{4}name:\s*[\"']?\$PAGES_ENVIRONMENT_NAME", "pages environment must be rule-scoped"),
        (pages, r"environment:\n(?:[ ]{2,}.*\n)*?[ ]{4}auto_stop_in:\s*[\"']?\$PAGES_AUTO_STOP_IN", "pages environment must use rule-scoped auto_stop_in"),
        (pages, r"PAGES_ENVIRONMENT_NAME:\s*[\"']?review/\$CI_COMMIT_REF_SLUG", "branch previews must use review environments"),
        (pages, r"PAGES_ENVIRONMENT_URL:\s*[\"']?\$CI_PAGES_URL/\$CI_COMMIT_REF_SLUG/web/nemoclaw/", "branch previews must keep their review URL"),
        (pages, r"PAGES_AUTO_STOP_IN:\s*[\"']?3 days", "branch previews must auto-stop"),
        (pages, r"PAGES_ENVIRONMENT_NAME:\s*[\"']?production", "production must use production environment"),
        (pages, r"PAGES_AUTO_STOP_IN:\s*[\"']?never", "production environment must not auto-stop"),
    ]
    for block, pattern, msg in checks:
        if block and not re.search(pattern, block):
            findings.append(msg)

    if _job_block(text, "pages_preview"):
        findings.append("classic GitLab Pages instance must not use pages_preview; only job name 'pages' can publish")
    if re.search(r"(?ms)^pages:\n(?P<body>.*?)(?=^[A-Za-z0-9_.-]+:\n|\Z)", text):
        if re.search(r"(?m)^[ ]{2}pages:", pages) or re.search(r"(?m)^[ ]{2}pages:\s*true", pages):
            findings.append("classic pages job must not use the newer pages: keyword on this GitLab instance")
    if re.search(r"pages:\n(?:[ ]{2,}.*\n)*?[ ]{4}path_prefix:", pages):
        findings.append("classic pages job must not use pages.path_prefix on this GitLab instance")
    if "expire_in: 3 days" not in pages:
        findings.append("pages job must keep 3-day downloadable artifact expiry")

    if findings:
        print("ci_storage_audit: FAIL")
        for item in findings:
            print(f"  - {item}")
        return 1

    print("ci_storage_audit: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
