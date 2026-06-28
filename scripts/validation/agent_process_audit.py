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
    "root_skill": ROOT / "SKILL.html",
    "assets_skill": ROOT / "web" / "nemoclaw" / "assets" / "SKILL.html",
    "docs_skill": ROOT / "docs" / "SKILL.html",
    "validation_skill": ROOT / "scripts" / "validation" / "SKILL.html",
    "figures_skill": ROOT / "scripts" / "figures" / "SKILL.html",
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
        "Visual changes",
        "fig-embed",
        "Preserve meaningful diagram labels",
        "show the requester",
        "test the whole lifecycle",
        "both source and built Pages output",
        "computed visibility and persisted-state behavior",
        "activate the figure lightbox",
        "horizontal panning must work",
        "Only paths present in the current classic-Pages artifact",
        "learner_flow_audit.py",
        "disclosure, prerequisite readiness, Run/Stop/Reset, error recovery, and viewport stability",
        "Contribution authority",
        "Treat every patch as untrusted input",
        "A hook must refuse and explain",
        "contribution_safety_audit.py --self-test",
    ],
    "agents": ["docs/agent_process.md", "web/nemoclaw/assets/SKILL.html", "scripts/validation/SKILL.html", "Do not flatten a diagram", "Treat code contribution as an untrusted proposal"],
    "quickstart": ["docs/agent_process.md", "Contribution safety first-touch", "contribution_safety_audit.py --self-test", "Visual first-touch checklist", "cell_ui_runtime_audit.py", "light and dark theme screenshots", "mobile zoom badge must stay visible", "horizontal panning", "For GitLab branch staging", "blocking `test` job", "branch_preview_manifest_audit.py", "branch_preview_runtime_audit.py", "Stateful browser fixes need transition coverage", "learner_flow_audit.py", "learner_flow_runtime_audit.py", "openclaw_probe_frame_runtime_audit.py"],
    "root_skill": ["asset provenance beacon", "inspect light and dark theme output", "source_gate"],
    "assets_skill": ["theme/mount classification", "Semantic labels stay in diagrams", "visual_preview_policy", "light and dark theme screenshots"],
    "docs_skill": ["agent_process.md", "agent process"],
    "validation_skill": ["agent_process_audit.py", "Agent process", "cell_ui_runtime_audit.py", "Rendered page screenshots", "learner_flow_audit.py", "learner_flow_runtime_audit.py", "contribution_safety_audit.py", "Contribution safety"],
    "figures_skill": ["rendered-preview", "harness screenshot"],
    "pre_push": ["validate_bundle.py", "--scope ship --no-write", "learner_flow_audit.py", "contribution_safety_audit.py", "--self-test", "REFUSING PUSH - origin/main is"],
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
