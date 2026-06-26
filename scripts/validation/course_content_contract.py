#!/usr/bin/env python3
"""Course-specific content contracts that should not drift silently.

These are narrow regression guards for course promises that generic link, figure,
and prose validators cannot infer from first principles.
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

ROOT = find_repo_root(Path(__file__).resolve())
COURSE = ROOT / "web" / "nemoclaw"
ASSETS = COURSE / "assets"


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8", errors="replace")


def _has_all(text: str, tokens: tuple[str, ...]) -> bool:
    low = text.lower()
    return all(t.lower() in low for t in tokens)


def run(verbose: bool = True) -> list[tuple[str, str]]:
    findings: list[tuple[str, str]] = []
    p02b = _read("web/nemoclaw/02b-rag.html")
    p04a = _read("web/nemoclaw/04a-safety.html")
    svg02b = _read("web/nemoclaw/assets/figures/02b-retrieval-boundaries.svg")
    svg04a = _read("web/nemoclaw/assets/figures/lethal-trifecta.svg")
    askill = _read("web/nemoclaw/assets/SKILL.html")

    if "assets/figures/02b-retrieval-boundaries.svg" not in p02b:
        findings.append(("web/nemoclaw/02b-rag.html", "missing retrieval boundary figure"))
    if not _has_all(p02b, ("MCP", "A2A", "skills", "runtime", "generated UX")):
        findings.append(("web/nemoclaw/02b-rag.html", "retrieval boundary section must define MCP/A2A/skills/runtime/UX roles"))
    if re.search(r"Zenodia|@zcharpy|issue #\d+|issue-title|GitLab issue", p02b, re.I):
        findings.append(("web/nemoclaw/02b-rag.html", "learner-facing retrieval prose must not leak contributor or issue-thread shorthand"))
    if not _has_all(svg02b, ("Provenance", "MCP", "A2A", "Agent Skills", "Generative UX")):
        findings.append(("web/nemoclaw/assets/figures/02b-retrieval-boundaries.svg", "retrieval boundary SVG lost provenance or core boundary labels"))

    if "assets/figures/lethal-trifecta.svg" not in p04a:
        findings.append(("web/nemoclaw/04a-safety.html", "missing real lethal trifecta figure"))
    if not _has_all(p04a, ("Untrusted input", "private data", "external communication", "full-duplex")):
        findings.append(("web/nemoclaw/04a-safety.html", "lethal trifecta prose must define all three terms and the full-duplex risk"))
    fig_idx = p04a.find("assets/figures/lethal-trifecta.svg")
    fig_tail = p04a[fig_idx:fig_idx + 1200] if fig_idx >= 0 else ""
    if "Prompt rules and application guardrails shape the agent before kernel containment" in fig_tail:
        findings.append(("web/nemoclaw/04a-safety.html", "lethal trifecta caption regressed to the old sandbox-boundary caption"))
    if not _has_all(fig_tail + p04a, ("network allowlist", "allowed connection", "private data", "untrusted input")):
        findings.append(("web/nemoclaw/04a-safety.html", "lethal trifecta caption/prose must explain why an allowlist alone is insufficient"))
    if not _has_all(svg04a, ("Lethal Trifecta", "Access to Secrets", "Protected Private Data", "Untrusted Input", "A Way Out", "Permitted Egress Path")):
        findings.append(("web/nemoclaw/assets/figures/lethal-trifecta.svg", "real lethal trifecta SVG lost its core labels"))
    if "Simon Willison" not in p04a or "simonwillison.net/2025/Jun/16/the-lethal-trifecta" not in p04a:
        findings.append(("web/nemoclaw/04a-safety.html", "lethal trifecta section must keep canonical Simon Willison reference"))

    process_ref = re.compile(r"Zenodia|@zcharpy|GitLab issue|issue #\d+|MR !?\d+|PR #?\d+", re.I)
    for rel, text in (
        ("web/nemoclaw/assets/SKILL.html", askill),
        ("web/nemoclaw/assets/figures/02b-retrieval-boundaries.svg", svg02b),
        ("web/nemoclaw/assets/figures/lethal-trifecta.svg", svg04a),
    ):
        if process_ref.search(text):
            findings.append((rel, "course assets must not expose issue-thread, MR/PR, or user-handle provenance"))
    if not _has_all(askill, ("02b-retrieval-boundaries.svg", "course-provided boundary map", "lethal-trifecta.svg", "Simon Willison")):
        findings.append(("web/nemoclaw/assets/SKILL.html", "asset provenance must document retrieval-boundary and lethal-trifecta figure sources"))

    if verbose:
        if findings:
            print("course_content_contract: FAIL")
            for path, detail in findings:
                print(f"  - {path}: {detail}")
        else:
            print("course_content_contract: OK")
    return findings


if __name__ == "__main__":
    raise SystemExit(1 if run() else 0)
