#!/usr/bin/env python3
"""Guardrail for the scripts/ hierarchy.

The scripts/ root is intentionally sparse so the repository browser shows the grouped
layout. Implementations and runnable entrypoints live under named subdirectories with
their own SKILL.html beacon. New root-level scripts are a regression.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"

GROUP_SKILLS = (
    "browser-vendor", "build", "compliance", "cors-proxy", "dev", "edx", "figures",
    "git-hooks", "materials", "runtime", "security", "skills", "translate",
    "validation",
)
ROOT_ALLOW = {".gitkeep", "SKILL.html", "_bootstrap.py"}
SKIP_DIRS = {"__pycache__", ".figtools", "grounding_cache"}
REQUIRED_RUNTIME_ASSETS = ("runtime/lab-runtime/Containerfile",)


def findings() -> list[str]:
    out: list[str] = []
    for dirname in GROUP_SKILLS:
        if not (SCRIPTS / dirname / "SKILL.html").is_file():
            out.append(f"missing scripts/{dirname}/SKILL.html")
    for rel in REQUIRED_RUNTIME_ASSETS:
        if not (SCRIPTS / rel).is_file():
            out.append(f"missing required runtime asset scripts/{rel}")
    for p in SCRIPTS.iterdir():
        if p.is_dir():
            if p.name not in GROUP_SKILLS and p.name not in SKIP_DIRS:
                out.append(f"unexpected root scripts/ directory {p.name}; add a SKILL.html or classify it")
            continue
        if p.name not in ROOT_ALLOW:
            out.append(f"unexpected root scripts/ file {p.name}; move it into a grouped subdirectory")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="validate scripts/ hierarchy")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rows = findings()
    if args.json:
        print(json.dumps({"findings": rows}, indent=2))
    elif rows:
        print("scripts_hierarchy: FAIL")
        for row in rows:
            print(f"  - {row}")
    else:
        print("scripts_hierarchy: OK")
    return 1 if rows else 0


if __name__ == "__main__":
    raise SystemExit(main())
