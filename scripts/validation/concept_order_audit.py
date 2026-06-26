#!/usr/bin/env python3
"""Required first-use concept order checks for the early agent curriculum.

This gate is intentionally narrow. It does not grade style and it does not create hover glossaries.
It protects the pages where reviewers flagged vocabulary arriving before the learner has a usable definition.
"""
from __future__ import annotations

import argparse
import json
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

CHECKS = [
    {
        "page": "01a-loop.html",
        "label": "tool introduced before action examples lean on it",
        "before": "code exposed to the model a <strong>tool</strong>",
        "after": "Calling a tool",
    },
    {
        "page": "01b-react.html",
        "label": "tool mechanics before ReAct tool-call discussion",
        "before": "A <strong>tool</strong> is code your harness can run for the model",
        "after": "offered a tool and asked",
    },
    {
        "page": "01c-tools.html",
        "label": "MCP acronym expanded before shorthand",
        "before": "Model Context Protocol (MCP)",
        "after": "Fetching tools from a separate server with MCP",
    },
    {
        "page": "01c-tools.html",
        "label": "MCP positioned as one serving interface",
        "required": "Use MCP when tool discovery and transport need a shared",
    },
    {
        "page": "02a-routing.html",
        "label": "workflow agent defined before pattern details",
        "before": "A <strong>workflow agent</strong> means an agent system",
        "after": "The model writes the full plan upfront",
    },
    {
        "page": "02a-routing.html",
        "label": "Promise.all explained before use as prerequisite",
        "before": "<code>Promise.all</code> is JavaScript's helper",
        "after": "Every query runs concurrently via <code>Promise.all</code>",
    },
    {
        "page": "02a-routing.html",
        "label": "fixed enum defined before router failure question",
        "before": "A <strong>fixed enum</strong>",
        "after": "The triage router has a fixed enum",
    },
]

BAD_TOKENS = {
    "02a-routing.html": [
        "service-level agreement failure",
        "might never sees",
    ],
    "01c-tools.html": [
        "the production standard for serving tools",
    ],
}


def read(page: str) -> str:
    return (COURSE / page).read_text(encoding="utf-8")


def norm(raw: str) -> str:
    return re.sub(r"\s+", " ", raw)


def audit() -> list[str]:
    findings: list[str] = []
    cache: dict[str, str] = {}
    for check in CHECKS:
        page = check["page"]
        raw = cache.setdefault(page, read(page))
        text = norm(raw)
        label = check["label"]
        if "required" in check:
            if check["required"] not in text:
                findings.append(f"{page}: missing required concept framing: {label}")
            continue
        before = check["before"]
        after = check["after"]
        b = text.find(before)
        a = text.find(after)
        if b < 0:
            findings.append(f"{page}: missing concept definition token for {label}: {before}")
        if a < 0:
            findings.append(f"{page}: missing downstream use token for {label}: {after}")
        if b >= 0 and a >= 0 and b > a:
            findings.append(f"{page}: concept appears after first use: {label}")
    for page, tokens in BAD_TOKENS.items():
        text = cache.setdefault(page, read(page))
        for token in tokens:
            if token in text:
                findings.append(f"{page}: stale confusing wording remains: {token}")
    return findings


run = audit


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate first-use definitions for the early agent curriculum.")
    ap.add_argument("--json", action="store_true", help="print machine-readable findings")
    args = ap.parse_args()
    findings = audit()
    if args.json:
        print(json.dumps({"ok": not findings, "findings": findings}, indent=2))
    elif findings:
        for finding in findings:
            print(f"[concept-order] {finding}")
    else:
        print("concept_order_audit: OK")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
