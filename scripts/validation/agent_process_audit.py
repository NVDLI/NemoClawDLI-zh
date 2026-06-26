#!/usr/bin/env python3
"""Audit repo-level agent process guardrails."""
from __future__ import annotations

import sys
from pathlib import Path

for _p in (Path(__file__).resolve(), *Path(__file__).resolve().parents):
    if (_p / "scripts" / "_bootstrap.py").exists():
        sys.path.insert(0, str(_p / "scripts"))
        break
from _bootstrap import find_repo_root

ROOT = find_repo_root(Path(__file__).resolve())
FILES = {
    "process_doc": ROOT / "docs" / "agent_process.md",
    "agents": ROOT / "AGENTS.md",
    "quickstart": ROOT / "AGENT_QUICKSTART.md",
    "docs_skill": ROOT / "docs" / "SKILL.html",
    "validation_skill": ROOT / "scripts" / "validation" / "SKILL.html",
    "pre_push": ROOT / "scripts" / "git-hooks" / "pre-push",
}

REQUIRED = {
    "process_doc": [
        "Addresses #N",
        "Closes #N",
        "NemoClaw is the reference stack",
        "OpenClaw is the agent harness",
        "OpenShell is the sandbox boundary",
        "Brev launchable is the hosted course deployment",
        "Do not print token-bearing environment variables",
        "git credential fill",
        "BUILD_PAGES_LANGS=0 scripts/build/build_pages.sh",
        "`apply_patch` is unavailable",
    ],
    "agents": ["docs/agent_process.md"],
    "quickstart": ["docs/agent_process.md"],
    "docs_skill": ["agent_process.md", "agent process"],
    "validation_skill": ["agent_process_audit.py", "Agent process"],
    "pre_push": ["validate_bundle.py", "--scope ship --no-write"],
}

FORBIDDEN_DOC_PATTERNS = (
    "env | rg TOKEN",
    "printenv | grep TOKEN",
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def audit() -> list[str]:
    findings: list[str] = []
    for key, tokens in REQUIRED.items():
        path = FILES[key]
        if not path.is_file():
            findings.append(f"missing {path.relative_to(ROOT)}")
            continue
        raw = read(path)
        for token in tokens:
            if token not in raw:
                findings.append(f"{path.relative_to(ROOT)} missing {token}")
    raw_doc = read(FILES["process_doc"]) if FILES["process_doc"].is_file() else ""
    for token in FORBIDDEN_DOC_PATTERNS:
        if token in raw_doc:
            line = next((ln for ln in raw_doc.splitlines() if token in ln), "")
            if "Never run" not in line and "Do not" not in line:
                findings.append(f"docs/agent_process.md gives unsafe auth probe without banning it: {token}")
    return findings


def main() -> int:
    findings = audit()
    if findings:
        for item in findings:
            print(item)
        return 1
    print("agent process audit: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
